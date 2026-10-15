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

为什么期望值从 Code 仓库的 api/runtimes.json 取，而不是问 assets 的 Release API：
    试过两条路，都不通：
      · gh api + GITHUB_TOKEN  → 404（临时 token 读不了 Release）
      · 匿名 curl              → 200，但返回的是"API rate limit exceeded"
                                 （Actions 机房是共享 IP，匿名限额一小时 60 次，早被用光了）
    第二版脚本还把限流的错误 JSON 当成了合法响应，
    于是得到"资产 0 个"却不报错 —— 这正是最坏的一种：看起来正常，实际什么都没做。

    Code 仓库的 api/runtimes.json 是同源、公开、且本来就有 size 与 sha256，
    拿它当期望值既不需要 API 配额，也不需要任何 token。

为什么用 Python 而不是 shell：
    第一版 shell 失败时日志没落盘，只看到 job failure 不知为什么。
    Python 版保证日志一定写进 _diag/mirror.log 并推回仓库。
"""

import json
import os
import subprocess
import sys
import hashlib
from datetime import datetime, timezone

REPO = "liuyiming2024/assets"
# 期望值来源：Code 仓库的清单（公开、同源、无需 API 配额）
SPEC_URL = "https://raw.githubusercontent.com/liuyiming2024/Code/main/api/runtimes.json"
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


def load_spec():
    """返回 {文件名: {size, sha256}}。拿不到就返回空 dict。"""
    r = run(["curl", "-sS", "-L", "--max-time", "90",
             "-H", "User-Agent: asset-mirror", SPEC_URL])
    if r.returncode != 0:
        log("  取清单失败（curl 退出码 %d）: %s" % (r.returncode, (r.stderr or "")[:200]))
        return {}
    try:
        j = json.loads(r.stdout)
    except Exception as e:
        log("  清单不是合法 JSON: %s" % e)
        log("  前 200 字符: %s" % (r.stdout or "")[:200])
        return {}
    # ⚠ 限流/错误响应也是合法 JSON，必须显式识别，
    #   否则会得到"看似成功、实则空"的结果 —— 第二版就栽在这里。
    if not isinstance(j, dict) or "runtimes" not in j:
        log("  清单结构不对（没有 runtimes 键），可能是错误响应:")
        log("  前 200 字符: %s" % (r.stdout or "")[:200])
        return {}
    spec = {}
    for rt in j.get("runtimes", []):
        for f in rt.get("files", []):
            if f.get("name"):
                spec[f["name"]] = {"size": f.get("size", 0), "sha256": f.get("sha256", "")}
    return spec


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fp:
        for chunk in iter(lambda: fp.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(DIAG, exist_ok=True)

    target = os.environ.get("TARGET", "sqlite")
    files = NEED.get(target)
    if not files:
        log("未知 target: %s" % target)
        return 1
    log("target = %s，共 %d 个文件" % (target, len(files)))

    log("")
    log("--- 取期望值（来自 Code 的 api/runtimes.json）---")
    spec = load_spec()
    log("清单里有 %d 个文件的期望值" % len(spec))
    if not spec:
        log("拿不到期望值，放弃（没有期望值就无法校验，宁可不做）")
        return 1

    log("")
    log("--- 下载 ---")
    ok = skip = fail = 0
    for f in files:
        s = spec.get(f)
        if not s or not s.get("size"):
            log("  ⚠ %-20s 清单里没有它的期望值" % f)
            fail += 1
            continue
        want = s["size"]
        dst = os.path.join(OUT, f)

        if os.path.isfile(dst) and os.path.getsize(dst) == want:
            log("  ⏭ %-20s 已存在且体积一致（%d 字节）" % (f, want))
            skip += 1
            continue

        log("  ⬇ %-20s 期望 %d 字节" % (f, want))
        # 匿名直链 + 跟随 302。curl 不做 CORS 检查，所以不受那个问题影响 ——
        # 这正是"地址栏能下、fetch 下不了"的同一个原因。
        dl = "https://github.com/%s/releases/download/latest/%s" % (REPO, f)
        d = run(["curl", "-sS", "-L", "--max-time", "900", "-o", dst,
                 "-w", "%{http_code} %{size_download}", dl])
        if d.returncode != 0:
            log("     ❌ curl 失败（退出码 %d）: %s" % (d.returncode, (d.stderr or "")[:200]))
            fail += 1
            continue
        if not os.path.isfile(dst):
            log("     ❌ 返回 0 但文件不在")
            fail += 1
            continue

        got = os.path.getsize(dst)
        if got != want:
            log("     ❌ 体积不符：实得 %d，期望 %d（HTTP: %s）"
                % (got, want, (d.stdout or "").strip()))
            try:
                os.remove(dst)
            except Exception:
                pass
            fail += 1
            continue

        # SHA-256 校验：体积一样不代表内容对（代理替换、截断都可能体积巧合）
        if s.get("sha256"):
            real = sha256_of(dst)
            if real != str(s["sha256"]).lower():
                log("     ❌ SHA-256 不符")
                log("        实得 %s" % real)
                log("        期望 %s" % s["sha256"])
                try:
                    os.remove(dst)
                except Exception:
                    pass
                fail += 1
                continue
            log("     ✅ %d 字节，SHA-256 一致" % got)
        else:
            log("     ✅ %d 字节（清单未给 SHA-256，仅校体积）" % got)
        ok += 1

    log("")
    log("下载 %d，跳过 %d，失败 %d" % (ok, skip, fail))

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
        h = sha256_of(p)
        manifest["files"][n] = {"size": os.path.getsize(p), "sha256": h}
        log("  %-24s %10d  %s…" % (n, os.path.getsize(p), h[:16]))

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
