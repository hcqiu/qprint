# Qprint

[中文](README.md) | [English](README.en.md)

以 Markdown 为中心的数学知识图谱与 proof navigation IDE。TeX 论文、Lean / Agda / Coq 代码通过 blueprint 节点连接，资料保留为普通文件，可直接用 Obsidian 或其他编辑器管理。

当前包版本为 `0.1.0`。文档描述当前实现；未来工作单独列在 TODO 中。

| 文档 | 用途 |
| --- | --- |
| [PRODUCT.md](PRODUCT.md) | 产品目标、用户流程、功能边界 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 模块职责、数据流、技术决策 |
| [TODO.md](TODO.md) | 已完成基线、后续工作与验收条件 |
| [docs/index.md](docs/index.md) | 模块文档及中英文导航 |
| [docs/spec.md](docs/spec.md) | 开发规格与验收契约 |
| [docs/verification.md](docs/verification.md) | 已执行的验证及已知限制 |

## 快速启动

在项目根目录运行（Python 3.12+，使用 `qprint` Conda 环境）：

```powershell
conda run -n qprint python -m pip install -e ".[dev]"
conda run -n qprint python -m qprint serve --workspace examples/demo --port 8765
```

打开 <http://127.0.0.1:8765>。默认仅监听本机。示例包含 10 个节点、12 条关系、1 篇 TeX 笔记及三种语言的代码片段。

如果 PowerShell 找不到 `conda`，可以运行 `./start.ps1`；脚本会查找 PATH 和用户目录下的 Anaconda / Miniconda。或使用完整路径：

```powershell
& "$env:USERPROFILE\anaconda3\Scripts\conda.exe" run -n qprint python -m qprint serve --workspace examples/demo
```

依赖版本快照在 `requirements-lock.txt`，需要复现当前测试环境时，先安装该文件再安装项目：

```powershell
conda run -n qprint python -m pip install -r requirements-lock.txt
conda run -n qprint python -m pip install -e . --no-deps
```

KaTeX JS、CSS、字体和许可证已保存在 `qprint/static/vendor/katex/`，阅读与图谱不依赖 CDN。重新获取固定版本资源可运行 `conda run -n qprint python tools/vendor_assets.py`，脚本验证 npm 提供的 SHA-512 integrity。

## 使用自己的工作区

```text
my-math/
  blueprint/Topology/Notes.md
  tex/Topology/Notes.tex
  pdf/Topology/Notes.pdf
  lean/Topology/Notes.lean
  agda/Topology/Notes.agda
  coq/Topology/Notes.v
```

```powershell
conda run -n qprint python -m qprint serve --workspace D:/my-math
conda run -n qprint python -m qprint check --workspace D:/my-math
```

目录可为空，标准库节点不必有论文附件。文件在外部修改后点击“刷新”；应用不会后台改写文件。

## 编写节点

一份 Markdown 可以包含多个节点。每个一级标题是一个节点，标题下方的 `qprint` YAML 围栏描述绑定，后续内容为 Markdown 正文。

````markdown
# My theorem
```qprint
kind: theorem
status: in_progress
tex: Topology/Notes#my-theorem
uses:
  - "[[Topology/Basic#Continuous]]"
inspired_by: []
lean:
  - declaration: MyNamespace.my_theorem
    file: Topology/Notes.lean
    lines: [10, 18]
agda: []
coq: []
```
这里写定理的描述、数学公式 $f : X \to Y$ 和 [[Topology/Basic#Continuous|连续性]] 链接。
````

节点地址是 `Topology/Notes#My theorem`。支持 `[[#同文件标题]]` 和唯一的 `[[文件名#标题]]`；重名文件请写完整 vault 路径。必须给 YAML 中的 wikilink 加引号。

* `kind`：`definition`、`lemma`、`theorem`、`conjecture`、`proof`、`other`。
* `status`：`not_started`、`in_progress`、`complete`。这是作者记录的进度，不是编译器检查结果。
* `uses` 是证明或定义的依赖，`inspired_by` 是思想来源。
* 语言字段支持多个绑定；仅远程代码可以用 `declaration` + HTTPS `url`，不要求下载整个标准库。
* `file` 相对于语言目录；`lines` 是从 1 开始的闭区间。简单声明可省略行号，复杂语法建议明确填写。
* 二级标题不会创建新节点。不要在同一份文件内重复一级标题。

论文只需添加定位标记，不需要加入形式化状态或依赖标签：

```tex
\documentclass{article}
\newcommand{\bpnode}[1]{}
\newtheorem{theorem}{Theorem}
\begin{document}
\section{Main result}
\bpnode{my-theorem}
\begin{theorem}
The identity map is continuous.
\end{theorem}
\bpnode{next-node}
The next mathematical object begins here.
\end{document}
```

`\bpnode` 放在环境外、所绑定内容之前；也能标记没有 theorem 环境的普通段落。当前节点展示到下一个标记之前的内容。`tex` 仅写标签名时，按 blueprint 的路径自动匹配 TeX 文件。

## 导航与编辑

左侧目录包含论文目录和 blueprint 节点。`/` 聚焦搜索。中栏切换阅读、TeX、Markdown；右栏仅显示当前节点绑定的代码，支持切换语言和声明。两个侧栏可以收起；窄屏下代码栏位于正文下方。

点击“知识图谱”聚焦当前节点。单击节点查看描述，双击或 Enter 打开正文和源码，空格预览。支持拖动、平移、缩放、力导向/分层切换、类型/进度筛选、一跳邻域；箭头从依赖指向使用者，虚线表示思想来源。

图谱支持三种**颗粒度**：Blueprint 节点（一级标题）、Milestone（Markdown 文件）、项目（索引文件所在目录或回退目录）。分级仅用于图谱聚合，不要求新增节点字段、搬动文件或建立额外项目配置。

* 项目识别：目录内的 `<目录名>.md` 或 `index.md` 视为索引，同名文件优先。文件归属最近的有索引祖先目录，因而项目内仍可有任意子文件夹；没有这样的索引时，归属文件所在的最小目录。blueprint 根目录直接存放的文件归入“blueprint 根目录”。
* Milestone 图谱将同一文件内所有指向另一文件的引用合并成一条边。支持正文或节点元数据中的 `[[路径#标题]]`、`[[路径]]`、带别名的 wikilink，以及 Markdown 相对链接 `[文本](../Other.md#标题)`。代码示例、行内代码、HTML 注释和外部网页链接不参与聚合。标题级 `uses` / `inspired_by` 的原有语义保持不变。
* 项目图谱进一步合并跨项目的文件引用，包括索引 Markdown 中的项目依赖；同一项目内部的引用不产生项目自环。
* **范围**可选“全范围”或“当前项目”，并可通过项目下拉框切换当前项目。节点级默认当前项目；项目级始终全范围，范围选择器自动禁用。
* 双击项目进入全范围 Milestone 图谱，并用金色描边高亮该项目的所有文件。双击 Milestone 进入其项目的 Blueprint 节点图谱，高亮该文件的所有一级标题；再次双击 Blueprint 节点打开正文和代码。下钻时清除旧筛选，确保所有成员可见。

索引仍是普通 Markdown：即使没有一级标题，也会出现在文件图谱；若含一级标题，仍按原有规则解析节点。对于名称任意、无法从文件名识别的索引，可使用上述命名约定，无需添加元数据。

正文滚动到底后再向下滚动切换到下一节点，向上相反。同一篇论文内可用页脚按钮或 Alt+左右方向键导航。URL hash 可作为节点深链。Markdown 模式编辑整份文件，Ctrl+S 保存；外部文件变化会触发冲突提示，避免静默覆盖。

## 导入资料

界面的“导入资料”与以下 CLI 使用同一个下载器。GitHub 接受仓库根地址，branch / tag / SHA 单独传入；默认分支会自动读取。

```powershell
conda run -n qprint python -m qprint import-code https://github.com/CMU-HoTT/serre-finiteness --language agda --dest serre-finiteness --workspace D:/my-math
conda run -n qprint python -m qprint import-paper 1603.04246 --dest Geometry --name Via16SpherePacking --workspace D:/my-math
```

论文 PDF 保存为 `pdf/Geometry/Via16SpherePacking.pdf`，多文件源码保存在 `tex/Geometry/Via16SpherePacking/`，保持内部相对路径；下载器不会擅自给论文添加 blueprint 标记。导入后按需要创建同名 Markdown，并以实际源码路径绑定节点。

现有目标不会被覆盖。下载上限 100 MiB、解压上限 300 MiB / 10,000 个归档条目；拒绝路径穿越与链接文件。每个导入目录包含 `.qprint-source.json` 以记录来源。源码不存在、网络失败、超限会显示错误。后台任务记录只保留在当前服务进程，重启后清空。下载不会执行代码或安装仓库依赖。

## 测试与开发

```powershell
conda run -n qprint pytest -q
node --test tests/graph_view.test.mjs
conda run -n qprint python -m qprint check --workspace examples/demo
```

受限的 Windows 运行环境若无法访问系统 pytest 临时目录，可指定项目内新建的临时目录：

```powershell
New-Item -ItemType Directory .qprint -Force
conda run -n qprint pytest -q --basetemp .qprint/test-local
```

注意 pytest 会清理其 `--basetemp` 目录，务必只指定测试专用目录。

主要代码：`blueprint.py` 解析节点，`workspace.py` 构建索引，`tex.py` 解析片段并适配 plasTeX DOM，`formal.py` 定位代码，`importers.py` 导入资源，`server.py` 提供 API，`static/` 为无构建步骤的前端。API 的 OpenAPI schema 在运行服务的 `/openapi.json`。

## 当前边界

plasTeX 渲染支持常用论文结构和数学公式，但不替代完整 LaTeX 排版。片段中的跨文件 `\input`、外部图像、复杂宏包会回退到 TeX 源文并提示；多行宏定义需要后续扩展。Lean / Agda / Coq 编译器和 LSP 不在首版范围，示例代码用于导航演示，未作为完整形式化项目编译。AI 双向生成与旧 leanblueprint 转换器按原需求留在后续范围。
