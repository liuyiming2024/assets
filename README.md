# assets · 大体积运行时资源

一个**只存大文件**的仓库，给聊天室和 Code 项目用。

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

清单在 `manifest.json`，列了每个文件的大小、SHA-256 与许可证。

## 怎么更新

Actions → 「抓取运行时资源」→ 选目标 → 运行。

会依次做三件事：抓文件 → 发成 Release 资产 → 更新 `manifest.json`。

标签固定用 `latest`，**可重复运行**，重跑不会撞「tag 已存在」。

## 现有资源

按「体积 ÷ 价值」排序，小的先加：

| 资源 | 体积 | 许可证 | 说明 |
| --- | --- | --- | --- |
| php-web.mjs | 0.0 MB | Apache-2.0 | PHP 运行时加载器 |
| pyodide.js | 0.0 MB | MPL-2.0 | Pyodide 加载器 |
| sql-wasm.js | 0.0 MB | MIT | sql.js 的 JS 包装 |
| lua.js | 0.2 MB | MIT | Wasmley 胶水代码 |
| quickjs.wasm | 0.5 MB | MIT | ES2025 引擎，用于隔离沙箱 |
| sql-wasm.wasm | 0.6 MB | MIT | 完整 SQLite 引擎 |
| lua.wasm | 1.2 MB | MIT | 官方 PUC-Rio Lua 5.4 |
| python_stdlib.zip | 2.2 MB | MPL-2.0 | Python 标准库 |
| **pyodide.asm.wasm** | **9.6 MB** | MPL-2.0 | **CPython 核心** |
| php-web.mjs.wasm | 16.5 MB | Apache-2.0 | Zend 引擎本体 |
| ruby+stdlib.wasm | 33.6 MB | MIT | CRuby 3.3 + 标准库 |

合计 **64.5 MB**，11 个文件，全部已发布。

详细的运行时资料（含各语言对比与接入顺序）在
https://github.com/liuyiming2024/Code/blob/main/docs/runtimes.md

## 两条硬约束

1. **只发 Release，不提交进 git。** 二进制进 git 就再也删不干净了。
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
