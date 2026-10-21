# Qprint 文件格式总索引

本目录集中说明 Qprint 的 TeX、Blueprint、Lean 和 Agda 文件格式。说明使用中文，文档文件名、目录名以及示例路径均使用英文；所有说明文件均为 Markdown，实际源码以代码块提供。

| 文档 | 内容 |
| --- | --- |
| [TeX 格式](tex.md) | 论文结构、节点标记、描述、依赖和完整示例 |
| [Blueprint 格式](blueprint.md) | 节点元数据、链接、项目索引和完整示例 |
| [Lean 格式](lean.md) | Lean 4 源码、Lake 项目配置和节点绑定 |
| [Agda 格式](agda.md) | 模块、类型与证明、项目配置和节点绑定 |

## 统一目录与路径

四份文档共用“自然数上的恒等函数及其取值性质”示例。以下是将代码块保存为实际文件后的工作区结构；这些文件不会仅因阅读文档而自动生成。

```text
examples/format-demo/
  tex/
    Identity/
      main.tex
  blueprint/
    Basics/
      Identity/
        index.md
        results.md
  lean/
    Identity/
      lean-toolchain
      lakefile.toml
      Identity.lean
  agda/
    Identity/
      identity.agda-lib
      .qprint-formal.yaml
      Identity.agda
```

目录层级承担不同职责：`blueprint/Basics/Identity/` 是论文或数学项目，`results.md` 是按数学目标组织的 milestone，文件内每个一级标题是节点。TeX 和形式化项目不必与 Blueprint 目录同构，通过显式绑定关联。

| 引用位置 | 相对根目录 | 示例值 |
| --- | --- | --- |
| Blueprint 节点 ID、完整 wikilink | 工作区的 `blueprint/` | `Basics/Identity/results#identity-value` |
| 节点的 `tex` 字段 | 工作区的 `tex/` | `Identity/main.tex#identity-value` |
| `lean.file` | 工作区的 `lean/` | `Identity/Identity.lean` |
| `agda.file` | 工作区的 `agda/` | `Identity/Identity.agda` |
| 独立验证命令的 `--entry` | 对应形式化项目根目录 | `Identity.agda` |

元数据路径使用 `/`，不重复写 `tex/`、`lean/` 等根目录前缀，不使用绝对路径、反斜杠或 `..`。文件保存为 UTF-8；路径与声明名保持大小写一致。示例统一使用英文名称，这是本说明的命名约定，并非 Qprint 禁止中文正文或标题。

## 示例对应关系

| 数学内容 | TeX 标记 | Blueprint 节点标题 | Lean 声明 | Agda 声明 |
| --- | --- | --- | --- | --- |
| 恒等函数 | `identity-function` | `identity-function` | `Identity.idNat` | `Identity.idNat` |
| 恒等函数取值 | `identity-value` | `identity-value` | `Identity.identity` | `Identity.identity` |

先按四份文档保存源码及配置，再保存 Blueprint 节点与项目索引。示例中的所有绑定都依赖相应文件实际存在；只采用某一种语言时，删去未采用语言的绑定。

## 检查与验证

以下命令均从 Qprint 根目录执行，并使用项目内 `.conda`：

```powershell
.\.conda\python.exe -m qprint check --workspace examples/format-demo
.\.conda\python.exe -m qprint serve --workspace examples/format-demo
```

`check` 检查工作区解析及引用诊断。源码能定位、TeX 能渲染、节点标为 `complete`，都不能替代 Lean/Agda 验证。显式验证命令为：

```powershell
.\.conda\python.exe -m qprint verify --workspace examples/format-demo --offline
```

此命令要求对应固定版本的工具链已在 Qprint 托管环境中准备好；`--offline` 禁止联网安装。去掉该选项时，验证流程可下载支持的缺失工具链。本文版本是与仓库示例一致的固定示范版本，不表示最新版本。验证结果也不自动证明源码与论文的数学含义一致，仍需人工核对。

## 维护依据

本说明按当前仓库的解析与验证实现编写。格式细节可查阅 [Blueprint 模块](../blueprint.md)、[TeX 渲染](../tex-rendering.md)、[TeX 转换](../tex-to-blueprint.md)、[代码定位](../formal-code.md) 和 [项目配置解析](../formal-resolution.md)。返回 [Qprint 文档目录](../index.md)。
