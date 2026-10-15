#!/usr/bin/env python3
"""从 manifest.json 生成聚合 LICENSE —— 总规划里的合规底线。

⚠ 为什么必须人工维护 HOLDERS：
   「上游项目归属」和「许可证」**不能靠猜**。
   文件名长得像 lua 不代表它就来自 fengari ——
   而标错归属比不标更糟：那等于把 A 的版权安到 B 头上。
   所以每个组件都得回到上游 LICENSE 逐条核对，再手工登记进来。

⚠ 校验：manifest 里出现、但 HOLDERS 里没登记的文件，会**明确报出来**。
   新增组件最常犯的错就是"抓到了、写进清单了、忘了核归属"——
   没有这条校验，LICENSE 会静默漏掉新组件。
"""
import os, sys, json, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 上游归属：文件名 → (项目名, 许可证, 上游地址)
# 新增组件必须在这里登记，且必须回上游核对过。
HOLDERS = {
    'fengari-web.js': ('fengari', 'MIT', 'https://github.com/fengari-lua/fengari'),
    'lua.wasm':       ('fengari', 'MIT', 'https://github.com/fengari-lua/fengari'),
    'lua.js':         ('fengari', 'MIT', 'https://github.com/fengari-lua/fengari'),
}

# 规划中、尚未抓取的组件（总规划点名要核对的）
PLANNED = [
    ('Clang / LLVM', 'Apache-2.0（含 LLVM 例外）'),
    ('SQLite', 'public domain'),
    ('Ruby', 'Ruby License 或 BSD-2（待定）'),
    ('CPython', 'PSF License'),
]

LICENSE_TEXT = {
    'MIT': """MIT License

Copyright (c) {holder}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.""",
}


def main():
    mp = os.path.join(ROOT, 'manifest.json')
    man = json.load(open(mp, encoding='utf-8'))
    fs = man.get('files', [])

    unknown = [f.get('name', '') for f in fs if f.get('name', '') not in HOLDERS]
    if unknown:
        print('  ⚠ 以下文件在 manifest 里，但 HOLDERS 未登记归属：')
        for u in unknown:
            print('     -', u)
        print('    请回上游核对许可证后登记到 scripts/gen_license.py，'
              '不要凭文件名猜。')
        print('    未登记的将在 LICENSE 里标为「未核对」，不假装已核。')

    o = []
    o.append("# 聚合许可证 / Third-party licenses")
    o.append("")
    o.append("> 本仓库只做**资源分发**：文件由 Actions 从上游开源项目抓取，")
    o.append("> 二进制不进代码主库，每个文件都带 SHA-256 便于校验。")
    o.append("> ")
    o.append("> **版权从来不是障碍** —— 这些都是宽松许可证，")
    o.append("> 唯一约束是主仓库自定的「零依赖」原则。使用时保留各自版权声明即可。")
    o.append("")
    o.append("生成时间：%s（由 `scripts/gen_license.py` 从 manifest.json 生成）"
             % datetime.date.today().isoformat())
    o.append("")
    o.append("---")
    o.append("")
    o.append("## 一、组件清单")
    o.append("")
    o.append("| 文件 | 上游项目 | 许可证 | 上游地址 |")
    o.append("|---|---|---|---|")
    for f in fs:
        n = f.get('name', '')
        proj, lic, url = HOLDERS.get(n, ('**未核对**', '**未核对**', f.get('url', '')))
        o.append("| `%s` | %s | %s | %s |" % (n, proj, lic, url))
    o.append("")
    o.append("---")
    o.append("")
    o.append("## 二、许可证全文")
    o.append("")

    seen = set()
    for f in fs:
        n = f.get('name', '')
        proj, lic, _ = HOLDERS.get(n, ('', '', ''))
        if not lic or lic in seen:
            continue
        seen.add(lic)
        used = [x.get('name', '') for x in fs
                if HOLDERS.get(x.get('name', ''), ('', '', ''))[1] == lic]
        o.append("### %s" % lic)
        o.append("")
        o.append("用于：%s" % ", ".join("`%s`" % u for u in used))
        o.append("")
        o.append("```")
        o.append(LICENSE_TEXT.get(lic, "(许可证原文待补)").format(
            holder="%s contributors" % proj))
        o.append("```")
        o.append("")

    o.append("---")
    o.append("")
    o.append("## 三、待补充（规划中的组件，尚未抓取）")
    o.append("")
    o.append("| 组件 | 预期许可证 | 状态 |")
    o.append("|---|---|---|")
    o.append("| Lua（fengari） | MIT | ✅ 已在册 |")
    for name, lic in PLANNED:
        o.append("| %s | %s | 未抓取 |" % (name, lic))
    o.append("")
    o.append("> ⚠ 「预期许可证」是**待核对**，不是已确认。")
    o.append("> 抓到真实文件后必须回到上游 LICENSE 逐条核对，")
    o.append("> 再登记进 `scripts/gen_license.py` 的 HOLDERS。")
    o.append("> **拿不准就先不抓 —— 合规是底线。**")

    open(os.path.join(ROOT, 'LICENSE'), 'w', encoding='utf-8').write('\n'.join(o))
    print('  LICENSE 已生成：%d 行，覆盖 %d 个组件' % (len(o), len(fs)))
    return 1 if unknown else 0


if __name__ == '__main__':
    sys.exit(main())
