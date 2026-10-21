# Formal Blueprint Project to QPrint

入口是 `tools/formal_blueprint_project_to_qprint.py`。它将已有的 LaTeX Blueprint 划分和 Lean 工程转成 Qprint 工作区，不执行源仓库的脚本、Lake 或 Lean 编译器。

## 输入与运行

始终从 Qprint 根目录使用本地 `.conda`：

```powershell
.\.conda\python.exe tools/formal_blueprint_project_to_qprint.py https://github.com/frenzymath/Poincare-Conjecture Poincare-QPrint
```

两个必填参数：

1. 源工程地址：GitHub 仓库根 URL、本地工程目录或 zip/tar 文件。
2. 输出文件夹名字：Qprint 根目录下尚不存在的文件夹，不允许路径分隔符。

GitHub 输入会将默认分支或 `--ref` 指定的分支、tag、commit 解析为固定 commit，下载该 revision 并记录归档 SHA-256。本地输入只读取源工程。转换在临时目录完成后发布；失败不留下半成品输出，已有目标不会覆盖。

```powershell
# 固定 revision
.\.conda\python.exe tools/formal_blueprint_project_to_qprint.py https://github.com/frenzymath/Poincare-Conjecture Poincare-Pinned --ref COMMIT

# 本地工程；只选主项目的 Blueprint
.\.conda\python.exe tools/formal_blueprint_project_to_qprint.py upstream/Poincare-Conjecture Poincare-Main --tex-root PoincareConjecture/blueprint

# Blueprint 与证明分别存放于两个仓库时
.\.conda\python.exe tools/formal_blueprint_project_to_qprint.py BLUEPRINT_URL MyProject --lean-source LEAN_URL --lean-ref COMMIT
```

`--tex-root` 相对源工程，可重复。默认优先选名为 `blueprint` 的目录内的所有 TeX；没有这样的目录时扫描工程中的 TeX。历史 `archive`、Git、`.lake`、构建产物等目录不进入转换，完整排除列表写入报告。归档上限为 100 MiB 下载、300 MiB 解压、100,000 个条目；解压仍校验路径和链接。

## 转换规则

| 原工程 | 转换结果 |
| --- | --- |
| `\label{label}` | 原样保留，补充 `\bpnode{label}`，Markdown 一级标题也使用同一 label |
| 已有 `\bpnode` / `\node` | 复用覆盖当前片段的锚点，不重复插入；分离证明可复用同名节点 |
| `\uses{a,b}` | TeX 原样保留，Markdown 映射到对应节点的 wikilink；优先同文件、同项目，最后全局唯一匹配 |
| `\lean{Namespace.decl}` | 精确匹配 Lean 声明，生成 `declaration`、相对 `lean/` 的 `file`、1 起始闭区间 `lines` |
| 多个 `\lean` 或逗号分隔声明 | 同一节点的多个 Lean 绑定 |
| `\leanok` | 保留源标记，记录 `status: complete`，仅表示源作者的进度 |
| `\bpdesc{...}` | 复制已有描述；没有时 Markdown 正文留空，不推断或补写数学描述 |

Lean 源文件、Lake 配置、`lean-toolchain`、锁文件和许可证等按原目录复制，不注入 begin/end 注释。TeX 按原路径复制，并保留 `.bib`、样式和图片等附件。节点通常放在含唯一 label 的定理环境之前，使 Qprint 能显示完整陈述。章节、公式等普通 label 也保留为同名节点。

每个含节点的 TeX 文件生成一份 Markdown，保留原有章节文件划分。不同 `blueprint` 根按所属源项目分组，各组生成 `index.md`；同文件的重复锚点合并为一个节点。`index.tex` 对应 `index-nodes.md`，避免覆盖项目索引。

## 输出

```text
Poincare-QPrint/
  blueprint/                      # 节点 Markdown、各项目索引
    PoincareConjecture/...
    references/...
  tex/                            # 添加锚点的 TeX 及附件，保留源相对路径
  lean/                           # 原工程快照，保留原相对布局和原生 Lean 项目
    PoincareConjecture/lean-toolchain
    PoincareConjecture/lakefile.toml
    PoincareConjecture/PoincareLib/...
    companion/                    # 仅使用 --lean-source 时出现
  conversion-report.json          # 来源、数量、无法解析的绑定或标签
```

```powershell
.\.conda\python.exe -m qprint check --workspace Poincare-QPrint
.\.conda\python.exe -m qprint serve --workspace Poincare-QPrint
```

`lean/` 中保留源仓库的其他文件以保全许可证与原生工程上下文；Qprint 只从输出的 `blueprint/` 和 `tex/` 加载节点与论文。

## 诊断与边界

转换器不展开 TeX 宏，不运行 Lean elaborator。Lean 索引支持普通声明、命名空间、section、注释屏蔽、多行声明头与常见属性；宏生成的声明、自动生成的结构字段或其他复杂语法可能无法定位。不会以短名称猜测全限定声明。缺失或多个候选的声明保留 `declaration`，并在报告中列出候选，需人工补充精确位置。

未解析的依赖保留为未解析链接。若 `\uses` 内包含 `\cite`、其他宏或换行等不能作为节点链接的内容，保留原 TeX 并记录 `unsupported_use`，不生成非法链接。不能原样用作 Qprint 节点名的 label（如包含反斜杠、`#`、`|`）保留原 TeX，报告 `unsupported_label`，不擅自重命名。缺失描述是允许的，不作为错误。源码导航及 `\leanok` 继承都不代表本次执行通过了 Lean 编译或数学证明验收。

该工具按现有标注转换；复杂嵌套环境、多个不同 label 共处一个环境时，仍应检查 Qprint 显示的片段边界。第三方 TeX 宏的显示能力取决于 Qprint 阅读渲染器。

示例来源：[Poincare-Conjecture](https://github.com/frenzymath/Poincare-Conjecture)、[贡献指南](https://github.com/frenzymath/Poincare-Conjecture/blob/main/CONTRIBUTING.md)。该仓库本身含 Blueprint 与 Lean 库，无需再叠加 companion 仓库；只有源码确实分开存放时才使用 `--lean-source`。

完整工程的数量、来源快照和保留诊断见 [Poincare 实测记录](evaluations/formal-blueprint-poincare.md)。可用 `tools/smoke_formal_blueprint.py SOURCE.zip OUTPUT` 复核源码、标注与 Qprint 绑定。
