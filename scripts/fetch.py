#!/usr/bin/env python3
"""抓取运行时资源到本地 dist/。

按「体积 ÷ 价值」排的优先级：小的、性价比高的先抓。
Pyodide 那种几十 MB 的放最后 —— 抓一次要很久，别让它堵住其他。

⚠ 沙箱跑不了这个脚本（出站被网络策略挡住），只有 Actions 能跑。
"""
import os, sys, json, hashlib, urllib.request

# 资源清单。url 必须是**文件直链**，不能是网页地址 ——
# 网页地址会下到 HTML，文件却不到 1KB，看起来"成功了"其实是废的。
RESOURCES = {
    'sqljs': [
        {'name': 'sql-wasm.wasm',
         'url': 'https://cdn.jsdelivr.net/npm/sql.js@1.13.0/dist/sql-wasm.wasm',
         'license': 'MIT', 'desc': 'SQLite 编译到 WASM，完整 SQL 引擎'},
        {'name': 'sql-wasm.js',
         'url': 'https://cdn.jsdelivr.net/npm/sql.js@1.13.0/dist/sql-wasm.js',
         'license': 'MIT', 'desc': 'sql.js 的 JS 包装'},
    ],
    'lua': [
        # 主选 Fengari（Lua VM 的 JS 实现，jsdelivr 上路径稳定）。
        # 之前用 wasmley@latest/dist/lua.wasm —— 那个路径在包里根本不存在，
        # 抓下来是 404 页面，被 <1024 字节的校验挡掉，结果 lua 一项空着。
        {'name': 'fengari-web.js',
         'url': 'https://cdn.jsdelivr.net/npm/fengari-web@0.2.1/dist/fengari-web.js',
         'license': 'MIT', 'desc': 'Fengari：Lua VM 的 JS 实现，约 200KB'},
    ],
    'quickjs': [
        {'name': 'quickjs.wasm',
         'url': 'https://cdn.jsdelivr.net/npm/@jitl/quickjs-wasmfile-release-sync@0.32.0/dist/emscripten-module.wasm',
         'license': 'MIT', 'desc': 'QuickJS ES2025 引擎，约 500KB，用于隔离沙箱'},
    ],
    'php': [
        {'name': 'php-web.mjs',
         'url': 'https://cdn.jsdelivr.net/npm/php-wasm/PhpWeb.mjs',
         'license': 'Apache-2.0', 'desc': 'PHP 8.x 运行时加载器（Zend 引擎编译到 WASM）'},
        {'name': 'php-web.mjs.wasm',
         'url': 'https://cdn.jsdelivr.net/npm/php-wasm/php-web.mjs.wasm',
         'license': 'Apache-2.0', 'desc': 'php-wasm 运行时本体，约 16 MB'},
    ],
    'ruby': [
        {'name': 'ruby+stdlib.wasm',
         'url': 'https://cdn.jsdelivr.net/npm/@ruby/3.3-wasm-wasi@2.4.1/dist/ruby+stdlib.wasm',
         'license': 'MIT', 'desc': 'CRuby 3.3 编译到 WASM（官方 ruby.wasm 项目），约 10 MB'},
        {'name': 'browser.script.iife.js',
         'url': 'https://cdn.jsdelivr.net/npm/@ruby/wasm-wasi@2.4.1/dist/browser.script.iife.js',
         'license': 'MIT', 'desc': 'ruby.wasm 的浏览器直接可用脚本'},
    ],
    'pyodide': [
        {'name': 'pyodide.js',
         'url': 'https://cdn.jsdelivr.net/pyodide/v0.26.2/full/pyodide.js',
         'license': 'MPL-2.0', 'desc': 'CPython 编译到 WASM 的加载器'},
        {'name': 'pyodide.wasm',
         'url': 'https://cdn.jsdelivr.net/pyodide/v0.26.2/full/pyodide.wasm',
         'license': 'MPL-2.0', 'desc': 'CPython 核心，约 6-12 MB'},
        {'name': 'python_stdlib.zip',
         'url': 'https://cdn.jsdelivr.net/pyodide/v0.26.2/full/python_stdlib.zip',
         'license': 'MPL-2.0', 'desc': 'Python 标准库'},
    ],
}

# 体积从小到大。大的放后面 —— 抓一次很久，别让它堵住其他的。
ORDER = ['sqljs', 'lua', 'quickjs', 'pyodide', 'ruby', 'php']


def grab(item, out_dir, tries=3):
    """大文件（pyodide.wasm 十几 MB）一次抓不下来很常见 ——
    直接判失败等于放弃，所以给三次机会。"""
    path = os.path.join(out_dir, item['name'])
    os.makedirs(out_dir, exist_ok=True)
    data = None
    last = ''
    for n in range(tries):
        try:
            req = urllib.request.Request(item['url'], headers={'User-Agent': 'assets-fetch'})
            with urllib.request.urlopen(req, timeout=300) as r:
                data = r.read()
            break
        except Exception as e:
            last = str(e)[:120]
            if n < tries - 1:
                print('    · 第 %d 次失败（%s），重试' % (n + 1, last))
    if data is None:
        print('  ✗ %s → %s' % (item['name'], last))
        return None
    # 基本校验：太小说明拿到的是错误页或重定向页
    if len(data) < 1024:
        print('  ✗ %s 只有 %d 字节，像是错误页' % (item['name'], len(data)))
        return None
    open(path, 'wb').write(data)
    h = hashlib.sha256(data).hexdigest()
    print('  ✓ %s  %.1f MB' % (item['name'], len(data) / 1048576))
    return {'name': item['name'], 'size': len(data), 'sha256': h,
            'license': item['license'], 'desc': item['desc'], 'src': item['url']}


def main():
    target = 'all'
    out_dir = 'dist'
    a = sys.argv
    for i, x in enumerate(a):
        if x == '--target' and i + 1 < len(a): target = a[i + 1]
        if x == '--out' and i + 1 < len(a): out_dir = a[i + 1]

    want = ORDER if target == 'all' else [target]
    if target not in RESOURCES and target != 'all':
        print('未知目标：%s（可选：%s）' % (target, '/'.join(ORDER)))
        return 1

    got = []
    for key in want:
        print('[%s]' % key)
        for item in RESOURCES[key]:
            r = grab(item, out_dir)
            if r: got.append(r)

    meta = os.path.join(out_dir, '_fetched.json')
    json.dump(got, open(meta, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print('\n共 %d 个文件' % len(got))
    return 0


if __name__ == '__main__':
    sys.exit(main())
