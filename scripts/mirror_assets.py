#!/usr/bin/env python3
"""把 Release 资产搬进 git 目录。

为什么必须搬（实测证据，不是推测）：
    浏览器地址栏能瞬间下载，Worker 里的 fetch 却报 NetworkError。
    两者规则的差别：
      · 地址栏 = 顶层导航，不做 CORS 检查 → 能下
      · fetch  = CORS 模式，且直链 302 跳到另一个域名 → 被挡
    实测响应头：
      github.com/.../releases/download/  → ACAO: （无）
      raw.githubusercontent.com/...      → ACAO: *
      cdn.jsdelivr.net/gh/...            → ACAO: *
    只要文件在 **git 目录**里，就能从后两个域取到且带 ACAO:*。

为什么用 Python 而不是 shell：
    上一版用 shell，失败时日志没落盘（目录没推回仓库），
    只能看到 job failure 却不知道为什么 —— 等于瞎猜。
    Python 版的日志一定会写进 _diag/mirror.log 并推回。
"""

import json
import os
import subprocess
import sys
import hashlib
from datetime import datetime, timezone

REPO = "liuyiming2024/assets"
OUT = "rt"
DIAG = "_diag"
LOG = os.path.join(DIAG, "mirror.log")

NEED = {
    "sqlite":  ["sql-wasm.js", "sql-wasm.wasm"],
    "lua":     ["fengari-web.js", "lua.js", "lua.wasm"],
    "quickjs": ["quickjs.js", "quickjs.wasm"],
    "pyodide": ["pyodide.js", "pyodide.asm.wasm", "python_stdlib.zip"],
    "php":     ["php-web.js", "php-web.js.wasm", "php-web.mjs", "php-web.mjs.wasm"],
    "ruby":    ["ruby-wasi.js", "ruby+stdlib.wasm"],
    "cpp":     ["cpp-index.js", "clang.js", "lld.js", "wasi-shim.js",
                "lld.wasm", "sysroot.tar", "clang.wasm"],
}
NEED["all"] = [f for v in NEED.values() for f in v]

lines = []


def log(msg=""):
    print(msg, flush=True)
    lines.append(str(msg))


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(DIAG, exist_ok=True)

    target = os.environ.get("TARGET", "sqlite")
    files = NEED.get(target)
    if not files:
        log("未知 target: %s" % target)
        return 1
    log("target = %s，共 %d 个文件" % (target, len(files)))

    # 1) 取 Release 清单（含期望体积）
    #
    # ⚠ 不能用 gh api + GITHUB_TOKEN：实测 404 Not Found。
    #   仓库是公开的、Release 也是 published 的 —— 用个人 token 能拿到 23 个资产，
    #   唯独 Actions 里的临时 GITHUB_TOKEN 拿不到。
    #   这是那个 token 的权限边界，不是仓库配置问题。
    #   所以走**匿名** curl：公开 Release 的 API 允许匿名读（60 次/小时）。
    log("")
    log("--- 读取 Release 清单 ---")
    api_url = "https://api.github.com/repos/%s/releases/latest" % REPO
    r = run(["curl", "-sS", "-L", "--max-time", "90",
             "-H", "User-Agent: asset-mirror", api_url])
    rel = None
    if r.returncode == 0:
        try:
            rel = json.loads(r.stdout)
        except Exception as e:
            log("返回不是合法 JSON: %s" % e)
            log("  前 300 字符: %s" % (r.stdout or "")[:300])
    else:
        log("curl 失败（退出码 %d）: %s" % (r.returncode, (r.stderr or "")[:300]))

    if rel is None:
        # 兜底：再试 GITHUB_TOKEN 那条路（万一哪天权限放宽了）
        log("  匿名失败，改用 gh api 重试…")
        r2 = run(["gh", "api", "repos/%s/releases/latest" % REPO])
        if r2.returncode == 0:
            try:
                rel = json.loads(r2.stdout)
                log("  gh api 成功")
            except Exception:
                pass
        if rel is None:
            log("两条路都拿不到清单，放弃")
            return 1

    assets = {a["name"]: a for a in rel.get("assets", [])}
    log("Release: %s，资产 %d 个" % (rel.get("tag_name"), len(assets)))
    if not assets:
        log("⚠ Release 里没有任何资产 —— 请先跑一次「抓取运行时资源」")
        return 1

    # 2) 逐个搬
    log("")
    log("--- 下载 ---")
    ok = skip = fail = 0
    for f in files:
        a = assets.get(f)
        if not a:
            log("  ⚠ %-20s 不在 Release 清单里" % f)
            fail += 1
            continue
        want = a["size"]
        dst = os.path.join(OUT, f)

        if os.path.isfile(dst) and os.path.getsize(dst) == want:
            log("  ⏭ %-20s 已存在（%d 字节）" % (f, want))
            skip += 1
            continue

        log("  ⬇ %-20s 期望 %d 字节" % (f, want))
        # 同样走匿名直链（-L 跟随 302）。
        # 浏览器 fetch 拿不到是因为缺 CORS 头；curl 不做 CORS 检查，不受影响 ——
        # 这一点正是"地址栏能下、fetch 下不了"的同一个原因。
        dl = "https://github.com/%s/releases/download/latest/%s" % (REPO, f)
        d = run(["curl", "-sS", "-L", "--max-time", "900", "-o", dst, dl])
        if d.returncode != 0:
            log("     ❌ curl 下载失败（退出码 %d）" % d.returncode)
            log("     stderr: %s" % (d.stderr or "")[:300])
            fail += 1
            continue
        if not os.path.isfile(dst):
            log("     ❌ 返回 0 但文件不在（URL 未命中？）")
            fail += 1
            continue
        got = os.path.getsize(dst)
        if got != want:
            log("     ❌ 体积不符：实得 %d，期望 %d" % (got, want))
            fail += 1
            continue
        log("     ✅ %d 字节" % got)
        ok += 1

    log("")
    log("下载 %d，跳过 %d，失败 %d" % (ok, skip, fail))

    # 3) 清单
    log("")
    log("--- 生成清单 ---")
    manifest = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "files": {},
    }
    for n in sorted(os.listdir(OUT)):
        p = os.path.join(OUT, n)
        if not os.path.isfile(p):
            continue
        h = hashlib.sha256()
        with open(p, "rb") as fp:
            for chunk in iter(lambda: fp.read(1 << 20), b""):
                h.update(chunk)
        manifest["files"][n] = {"size": os.path.getsize(p), "sha256": h.hexdigest()}
        log("  %-20s %10d  %s…" % (n, os.path.getsize(p), h.hexdigest()[:16]))

    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as fp:
        json.dump(manifest, fp, indent=2, ensure_ascii=False)

    if ok == 0 and skip == 0:
        log("")
        log("全部失败，不提交")
        return 1
    return 0


if __name__ == "__main__":
    code = 0
    try:
        code = main()
    except Exception as e:
        import traceback
        log("未捕获异常: %s" % e)
        log(traceback.format_exc()[:1500])
        code = 1
    finally:
        os.makedirs(DIAG, exist_ok=True)
        with open(LOG, "w", encoding="utf-8") as fp:
            fp.write("\n".join(lines) + "\n")
        print("（日志已写入 %s）" % LOG, flush=True)
    sys.exit(code)
