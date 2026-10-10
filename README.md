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
| sql-wasm | ~1.5 MB | MIT | 完整 SQLite 引擎 |
| wasmley | ~200 KB | MIT | 官方 Lua 5.4 |
| quickjs | ~500 KB | MIT | ES2025 引擎，用于隔离沙箱 |
| pyodide | 6–12 MB | MPL-2.0 | 完整 CPython |

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
