# assets · 大体积运行时资源

一个**只存大文件**的仓库，给聊天室和 Code 项目用。

> ℹ 2026-10-14：人物档案项目源码**已迁出**到独立仓库 `liuyiming2024/Archive`
> （https://liuyiming2024.github.io/Archive/ ），本仓不再暂存。
> 本仓重新回到「只存大文件」的单一职责。

## 为什么单独开一个库

主仓库的约束是「零依赖、拿到就能跑、离线可用」。
而 WASM 运行时动辄几 MB 到几十 MB —— 混进去会直接破坏那条约束：

| 放哪 | 后果 |
| --- | --- |
| 提交进主仓库 | git 里二进制只增不减，clone 一次就再也快不起来 |
| 主仓库的 Release | 跟客户端安装包混在一起，找不着 |
| **单独一个库 + Release** | ✅ 主仓库保持干净，资源各自独立、可单独更新 |

## 怎么取文件

全部走 Release 资产，**文件直链**：

```
https://github.com/liuyiming2024/assets/releases/latest/download/<文件名>
```

清单在 `manifest.json`，列了每个文件的大小、SHA-256 与文件直链。
`rt/manifest.json` 是抓取产物的完整校验表（只有 size / sha256），
是 `scripts/manifest.py` 的输入之一，**不是**对外的下载清单。

## 怎么更新

Actions → 「抓取运行时资源」→ 选目标 → 运行。

会依次做三件事：抓文件 → 发成 Release 资产 → 更新 `manifest.json`。

标签固定用 `latest`，**可重复运行**，重跑不会撞「tag 已存在」。

## 现有资源

按「体积 ÷ 价值」排序，小的先加：

### C / C++（browsercc）

| 文件 | 体积 | 说明 |
| --- | --- | --- |
| cpp-index.js | 0.01 MB | browsercc 主入口（含 compile 函数） |
| clang.js | 0.07 MB | Clang 的胶水代码 |
| lld.js | 0.07 MB | LLD 链接器的胶水代码 |
| wasi-shim.js | 0.03 MB | **运行编译产物必需** |
| lld.wasm | 22.1 MB | 链接器 |
| sysroot.tar | 27.3 MB | C/C++ 标准库与头文件 |
| clang.wasm | 40.6 MB | Clang 编译器本体 |

**用法**（browsercc 官方示例）：

```js
import { compile } from 'browsercc';
import { WASI, File, OpenFile, ConsoleStdout } from '@bjorn3/browser_wasi_shim';

const { module, compileOutput } = await compile({
  source: '#include <iostream>\nint main(){ std::cout << "hi\n"; }',
  fileName: 'main.cpp',
  flags: []
});
let output = '';
const fds = [new OpenFile(new File([])),
  new ConsoleStdout(d => { output += new TextDecoder().decode(d); }),
  new ConsoleStdout(d => { output += new TextDecoder().decode(d); })];
const wasi = new WASI([], [], fds);
const inst = await WebAssembly.instantiate(module, { wasi_snapshot_preview1: wasi.wasiImport });
wasi.start(inst);
```

**已知限制**：WASI 不支持 C++ 异常和多线程。

### 其余资源

| 资源 | 体积 | 许可证 | 说明 |
| --- | --- | --- | --- |
| php-web.js | 0.2 MB | Apache-2.0 | PHP 运行时加载器 |
| pyodide.js | 0.0 MB | MPL-2.0 | Pyodide 加载器 |
| sql-wasm.js | 0.0 MB | MIT | sql.js 的 JS 包装 |
| lua.js | 0.2 MB | MIT | Wasmley 胶水代码 |
| quickjs.wasm | 0.5 MB | MIT | ES2025 引擎，用于隔离沙箱 |
| sql-wasm.wasm | 0.6 MB | MIT | 完整 SQLite 引擎 |
| lua.wasm | 1.2 MB | MIT | 官方 PUC-Rio Lua 5.4 |
| python_stdlib.zip | 2.2 MB | MPL-2.0 | Python 标准库 |
| **pyodide.asm.wasm** | **9.6 MB** | MPL-2.0 | **CPython 核心** |
| php-web.js.wasm | 16.5 MB | Apache-2.0 | Zend 引擎本体 |
| ruby+stdlib.wasm | 33.6 MB | MIT | CRuby 3.3 + 标准库 |

**上表列的是大体积资源。** 完整清单以 `manifest.json` 的 `files` 为准，
共 21 项（含各运行时的胶水 JS），每项都带 `size` / `sha256` / 文件直链。

详细的运行时资料（含各语言对比与接入顺序）在
https://github.com/liuyiming2024/Code/blob/main/docs/runtimes.md

## 两条硬约束

1. **大体积资源默认只发 Release，不提交进 git。** 二进制进 git
   就再也删不干净了。例外是 `sync-to-git.yml`：浏览器 Worker 用 `fetch`
   取 Release 直链会被 CORS 挡（下载端点不带 `Access-Control-Allow-Origin`），
   所以按需把资源搬一份进 `rt/`，从 `raw.githubusercontent.com` 取。
   这条取舍写在那个 workflow 的注释里，不是偷偷破坏约束。
2. **清单里的地址必须是文件直链。** 网页地址会下到 HTML，
   文件不到 1KB 却显示"成功" —— 这种假成功最难查。

## 关于版权

这些资源都是开源项目，用的是宽松许可证（MIT / MPL-2.0 / Apache-2.0）。
**版权从来不是障碍** —— 唯一的约束是主仓库自己定的「零依赖」。
使用时保留各自的版权声明即可。


## 抓资源时的三个坑（都踩过）

1. **文件名猜错，重试再多次也没用。**
   Pyodide 的核心叫 `pyodide.asm.wasm`，不是 `pyodide.wasm` ——
   四个候选全 404 才暴露这点。

2. **不钉版本号会拿到错误页。**
   `php-wasm/PhpWeb.mjs` 返回 996 字节的 HTML。
   必须写 `php-wasm@0.0.8/PhpWeb.mjs`。

3. **管道里的 tee 不会自己建目录。**
   `python3 ... | tee dist/x.log` 在 `dist` 不存在时直接失败，
   而且失败得很隐蔽 —— 先 `mkdir -p dist`。

所以：每个资源配**多个候选地址**，抓完校验**大小**（小于 1KB 视为错误页）。


## 诊断日志怎么留

`fetch.yml` 成功时只把 `manifest.json` 与聚合 `LICENSE` 写回仓库；
失败时额外由 `scripts/diag.py` 写一份 `_diag/last-run.txt`，
**固定路径、覆盖式**，仓库里永远只留最后一次失败，不会越堆越多。

另一个固定文件是 `_diag/mirror.log`，由 `scripts/mirror_assets.py`
（「资产搬进 git 目录」workflow）覆盖写入，记录最近一次搬运。
`sync-to-git.yml` 只 `git add` 这一个诊断文件，不再 `-f` 整个 `_diag/`
—— 那样会绕过上面的 `.gitignore`，把日志整目录塞回仓库。

成功那次的输出没有留存价值 —— 早期每次抓取都写一份 `_log.txt`，
根目录堆了一堆一次性日志，2026-11 已清理。要看成功时的输出，
去对应 Actions run 的日志即可。
