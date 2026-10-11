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
        # fengari：纯 JS 的 Lua VM，UMD，Worker 里 importScripts 直接用。
        # wasmley 只暴露 C API（_luaL_newstate / _lua_pcallk...），
        # 要跑一段代码得手写一堆 ccall 封装，成本高且易错。
        {'name': 'fengari-web.js',
         'url': ['https://cdn.jsdelivr.net/npm/fengari-web@0.2.1/dist/fengari-web.js',
                 'https://cdn.jsdelivr.net/npm/fengari-web/dist/fengari-web.js',
                 'https://unpkg.com/fengari-web@0.2.1/dist/fengari-web.js'],
         'license': 'MIT', 'desc': 'Fengari：纯 JS 的 Lua VM，UMD'},
        {'name': 'fengari.js',
         'url': ['https://cdn.jsdelivr.net/npm/fengari@0.1.5/dist/fengari.js',
                 'https://cdn.jsdelivr.net/npm/fengari/dist/fengari.js'],
         'license': 'MIT', 'desc': 'Fengari 核心（fengari-web 依赖）'},
        # 多候选：npm 包内的实际路径会随版本变，写死一个就等于赌。
        # 依次试，哪个通就用哪个 —— 比事后猜路径省事得多。
        {'name': 'lua.wasm',
         'url': ['https://cdn.jsdelivr.net/npm/wasmley/dist/lua.wasm',
                 'https://cdn.jsdelivr.net/npm/wasmley/lua.wasm',
                 'https://unpkg.com/wasmley/dist/lua.wasm'],
         'license': 'MIT', 'desc': 'Wasmley：官方 PUC-Rio Lua 5.4 编译到 WASM，约 630KB'},
        {'name': 'lua.js',
         'url': ['https://cdn.jsdelivr.net/npm/wasmley/dist/lua.js',
                 'https://cdn.jsdelivr.net/npm/wasmley/lua.js',
                 'https://unpkg.com/wasmley/dist/lua.js'],
         'license': 'MIT', 'desc': 'Wasmley 的 JS 胶水代码，约 142KB'},
    ],
    'quickjs': [
        {'name': 'quickjs.wasm',
         'url': 'https://cdn.jsdelivr.net/npm/@jitl/quickjs-wasmfile-release-sync@0.32.0/dist/emscripten-module.wasm',
         'license': 'MIT', 'desc': 'QuickJS ES2025 引擎，约 500KB，用于隔离沙箱'},
        {'name': 'quickjs.js',
         'url': ['https://cdn.jsdelivr.net/npm/@jitl/quickjs-wasmfile-release-sync@0.32.0/dist/index.js',
                 'https://cdn.jsdelivr.net/npm/@jitl/quickjs-wasmfile-release-sync@0.32.0/+esm',
                 'https://cdn.jsdelivr.net/npm/@jitl/quickjs-wasmfile-release-sync@0.32.0/dist/index.mjs'],
         'license': 'MIT', 'desc': 'QuickJS 的 JS 胶水代码'},
    ],
    'php': [
        # 不钉版本时 jsdelivr 返回 996 字节的错误页（不是真文件）。
        # 这也是为什么"小于 1KB 视为失败"那条校验值得留着。
        {'name': 'php-web.mjs',
         'url': ['https://cdn.jsdelivr.net/npm/php-wasm@0.0.8/PhpWeb.mjs',
                 'https://unpkg.com/php-wasm@0.0.8/PhpWeb.mjs'],
         'license': 'Apache-2.0', 'desc': 'PHP 8.x 运行时加载器（Zend 引擎编译到 WASM）'},
        {'name': 'php-web.mjs.wasm',
         'url': 'https://cdn.jsdelivr.net/npm/php-wasm/php-web.mjs.wasm',
         'license': 'Apache-2.0', 'desc': 'php-wasm 运行时本体（mjs 配套），约 16 MB'},
        # Worker 里用 importScripts 只能加载 UMD，ESM(.mjs) 不行。
        # php-web.mjs 只是 4KB 的 re-export 桩，真身是 php-web.js。
        {'name': 'php-web.js',
         'url': ['https://cdn.jsdelivr.net/npm/php-wasm@0.0.8/php-web.js',
                 'https://cdn.jsdelivr.net/npm/php-wasm/php-web.js'],
         'license': 'Apache-2.0', 'desc': 'php-wasm UMD 版（Worker 内可用）'},
        {'name': 'php-web.js.wasm',
         'url': ['https://cdn.jsdelivr.net/npm/php-wasm@0.0.8/php-web.js.wasm',
                 'https://cdn.jsdelivr.net/npm/php-wasm/php-web.js.wasm'],
         'license': 'Apache-2.0', 'desc': 'php-web.js 配套的运行时本体，约 16 MB'},
    ],
    'ruby': [
        {'name': 'ruby+stdlib.wasm',
         'url': 'https://cdn.jsdelivr.net/npm/@ruby/3.3-wasm-wasi@2.4.1/dist/ruby+stdlib.wasm',
         'license': 'MIT', 'desc': 'CRuby 3.3 编译到 WASM（官方 ruby.wasm 项目），约 10 MB'},
        # 只有 wasm 没有加载器，等于拿到引擎没钥匙 —— 必须把 JS 也抓下来。
        {'name': 'ruby-wasi.js',
         'url': ['https://cdn.jsdelivr.net/npm/@ruby/wasm-wasi@2.4.1/dist/browser/+esm',
                 'https://cdn.jsdelivr.net/npm/@ruby/wasm-wasi@2.4.1/+esm',
                 'https://cdn.jsdelivr.net/npm/@ruby/wasm-wasi@2.4.1/dist/browser.script.iife.js',
                 'https://unpkg.com/@ruby/wasm-wasi@2.4.1/dist/browser.script.iife.js'],
         'license': 'MIT', 'desc': 'ruby.wasm 的浏览器加载器（VM 控制入口）'},
    ],
    # C/C++：browsercc 把 Clang + LLD 编译到 WASM，在浏览器里真编译。
    # 配套需要 WASI shim 才能运行编译产物（@bjorn3/browser_wasi_shim）。
    # 体积代价大（约 95MB），但这是浏览器内跑真 C++ 的唯一现实路径。
    'cpp': [
        {'name': 'cpp-index.js',
         'url': ['https://cdn.jsdelivr.net/npm/browsercc@0.1.1/dist/index.js',
                 'https://cdn.jsdelivr.net/npm/browsercc@0.1.1/index.js',
                 'https://unpkg.com/browsercc@0.1.1/dist/index.js'],
         'license': 'MIT', 'desc': 'browsercc 主入口（含 compile 函数）'},
        {'name': 'clang.js',
         'url': ['https://cdn.jsdelivr.net/npm/browsercc@0.1.1/dist/clang.js',
                 'https://cdn.jsdelivr.net/npm/browsercc@0.1.1/clang.js',
                 'https://unpkg.com/browsercc@0.1.1/dist/clang.js'],
         'license': 'MIT', 'desc': 'Clang 的 Emscripten 胶水代码'},
        {'name': 'lld.js',
         'url': ['https://cdn.jsdelivr.net/npm/browsercc@0.1.1/dist/lld.js',
                 'https://cdn.jsdelivr.net/npm/browsercc@0.1.1/lld.js',
                 'https://unpkg.com/browsercc@0.1.1/dist/lld.js'],
         'license': 'MIT', 'desc': 'LLD 链接器的胶水代码'},
        {'name': 'lld.wasm',
         'url': ['https://cdn.jsdelivr.net/npm/browsercc@0.1.1/dist/lld.wasm',
                 'https://cdn.jsdelivr.net/npm/browsercc@0.1.1/lld.wasm',
                 'https://unpkg.com/browsercc@0.1.1/dist/lld.wasm'],
         'license': 'MIT', 'desc': 'LLD 链接器，23MB'},
        {'name': 'sysroot.tar',
         'url': ['https://cdn.jsdelivr.net/npm/browsercc@0.1.1/dist/sysroot.tar',
                 'https://cdn.jsdelivr.net/npm/browsercc@0.1.1/sysroot.tar',
                 'https://unpkg.com/browsercc@0.1.1/dist/sysroot.tar'],
         'license': 'MIT', 'desc': 'C/C++ 标准库与头文件，29MB'},
        {'name': 'clang.wasm',
         'url': ['https://cdn.jsdelivr.net/npm/browsercc@0.1.1/dist/clang.wasm',
                 'https://cdn.jsdelivr.net/npm/browsercc@0.1.1/clang.wasm',
                 'https://unpkg.com/browsercc@0.1.1/dist/clang.wasm'],
         'license': 'MIT', 'desc': 'Clang 编译器本体，43MB'},
        # 运行编译产物必需。dist/index.js 是 CommonJS 的入口桩（316 字节），
        # 真正能 import 的是 ESM 构建 —— 用 +esm 或 dist/esm/index.js。
        {'name': 'wasi-shim.js',
         'url': ['https://cdn.jsdelivr.net/npm/@bjorn3/browser_wasi_shim@0.4.1/+esm',
                 'https://cdn.jsdelivr.net/npm/@bjorn3/browser_wasi_shim@0.4.1/dist/esm/index.js',
                 'https://cdn.jsdelivr.net/npm/@bjorn3/browser_wasi_shim@0.4.1/dist/browser.js'],
         'license': 'MIT OR Apache-2.0', 'desc': 'WASI shim，运行编译产物必需'},
    ],
    'pyodide': [
        {'name': 'pyodide.js',
         'url': 'https://cdn.jsdelivr.net/pyodide/v0.26.2/full/pyodide.js',
         'license': 'MPL-2.0', 'desc': 'CPython 编译到 WASM 的加载器'},
        # 这是 Python 的核心 —— 没有它 pyodide.js 一个字也跑不起来。
        # 前两个候选都失败过，所以列了更多源。大文件在 CDN 上不稳定是常态。
        # 核心文件的名字是 pyodide.asm.wasm，不是 pyodide.wasm ——
        # 四个候选全 404 才暴露这点。名字猜错时，重试再多次也没用。
        {'name': 'pyodide.asm.wasm',
         'url': ['https://cdn.jsdelivr.net/pyodide/v0.26.2/full/pyodide.asm.wasm',
                 'https://cdn.jsdelivr.net/npm/pyodide@0.26.2/pyodide.asm.wasm',
                 'https://unpkg.com/pyodide@0.26.2/pyodide.asm.wasm'],
         'license': 'MPL-2.0', 'desc': 'CPython 核心（文件名是 asm.wasm，不是 pyodide.wasm）'},
        {'name': 'python_stdlib.zip',
         'url': 'https://cdn.jsdelivr.net/pyodide/v0.26.2/full/python_stdlib.zip',
         'license': 'MPL-2.0', 'desc': 'Python 标准库'},
    ],
}

# 体积从小到大。大的放后面 —— 抓一次很久，别让它堵住其他的。
# 体积从小到大。大的放后面 —— 抓一次很久，别让它堵住其他的。
# cpp 单独放最后：clang.wasm 43MB + lld 23MB + sysroot 29MB ≈ 95MB，
# 比前面所有资源加起来还大，所以它也支持单独 target 触发。
ORDER = ['sqljs', 'lua', 'quickjs', 'pyodide', 'ruby', 'php', 'cpp']


def grab(item, out_dir, tries=3):
    """大文件（pyodide.wasm 十几 MB）一次抓不下来很常见 ——
    直接判失败等于放弃，所以给三次机会。"""
    path = os.path.join(out_dir, item['name'])
    os.makedirs(out_dir, exist_ok=True)
    urls = item['url'] if isinstance(item['url'], list) else [item['url']]
    data = None
    last = ''
    for u in urls:
        for n in range(tries):
            try:
                req = urllib.request.Request(u, headers={'User-Agent': 'assets-fetch'})
                with urllib.request.urlopen(req, timeout=300) as r:
                    data = r.read()
                break
            except Exception as e:
                last = str(e)[:120]
                if n < tries - 1:
                    print('    · %s 第 %d 次失败，重试' % (u, n + 1))
        if data is not None:
            break
    if data is None:
        print('  ✗ %s → %s（已试 %d 个地址）' % (item['name'], last, len(urls)))
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
