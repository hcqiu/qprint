# Qprint v1 开发规格

[中文](spec.md) | [English](spec.en.md) · [文档目录](index.md)

本文的 v1 指首版产品范围；当前 Python 包版本为 `0.1.0`。模块实现细节见文档目录，后续计划见 [TODO](../TODO.md)。

状态：首版已实现，验收结果见 [verification.md](verification.md)。来源：[功能需求](../Qprint功能需求.md)。日期：2026-09-18。

## 1. 目标与边界

Qprint 是以 Markdown blueprint 为核心的本地数学知识库和 proof navigation IDE。TeX 与 Lean / Agda / Coq 都是节点的可选附件，任何一种附件缺失都不影响节点存在。首版交付可运行的 Python 服务、浏览器界面、CLI、示例工程与自动测试。支持浏览、定位、编辑节点原始 Markdown、重建索引和导入资料；不运行下载的代码、不声称自动验证证明。

采用 Python 3.12、FastAPI、plasTeX、原生 ES modules 和 SVG。继承 leanblueprint 的论文阅读结构与 plasTeX 原理，但不直接 fork 其 Lean 专用数据模型。图谱自行实现力导向交互及传统分层模式，避免引入整个笔记应用。数据保留在磁盘，不引入数据库。

AI 双向生成、旧 leanblueprint 自动迁移（原需求已注释）、LSP、编译器验证、多用户协作是后续范围。当前 `complete` 是作者声明状态，界面必须明确说明。

## 2. 工作区与数据契约

工作区根目录包含 `blueprint/`、`tex/`、`pdf/`、`lean/`、`agda/`、`coq/`。论文的 blueprint 与 tex 使用相同相对路径和 basename；标准库笔记没有 TeX 也合法。导入的多文件论文保留内部目录，PDF 为 `pdf/<目录>/<论文名>.pdf`，源码为 `tex/<目录>/<论文名>/`，以免破坏 `\input` 的相对路径。

每份 Markdown 中每个一级标题是一个节点；二级及以下标题属于正文；代码围栏中的 `#` 不产生节点。节点 ID 为不带 `.md` 的 vault 相对路径加 `#` 加原始标题，区分大小写。标题不得包含 `#`、`|` 或 `]]`，同文件重复一级标题是错误。文件级 frontmatter 可存普通 Obsidian 属性，但不是节点元数据。

紧接一级标题用 `qprint` 代码围栏储存 YAML 元数据（标准 Markdown，Obsidian 能直接打开）：

````markdown
# continuous_id
```qprint
kind: theorem
status: complete
tex: Topology/Example#continuous-id
uses:
  - "[[Topology/Basic#Continuous]]"
inspired_by: []
lean:
  - declaration: continuous_id
    file: Topology/Example.lean
    lines: [4, 5]
agda: []
coq: []
```
恒等映射是连续的。支持普通 Markdown、数学公式与 [[Topology/Basic#Continuous|连续映射]]。
````

字段约束：

| 字段 | 契约 |
| --- | --- |
| kind | definition / lemma / theorem / conjecture / proof / other；默认 other |
| status | not_started / in_progress / complete；默认 not_started |
| tex | `相对tex路径（可省.tex）#bpnode标签`；仅标签则推断同路径论文 |
| uses / inspired_by | wikilink 字符串数组；依赖与思想来源是不同边 |
| lean / agda / coq | 0 到多个绑定，允许 `module.declaration` 简写；完整绑定含 declaration、可选 file、lines、url |
| file / lines | 相对于语言文件夹；行号为一基闭区间；有歧义时必须显式给行号 |
| url | HTTPS 代码链接；无本地文件时展示外链，不自动抓取 |

链接支持 vault 完整路径、唯一 basename、`[[#本文件标题]]`、显示别名。缺失或有歧义的引用产生诊断，不猜测目标。正文链接可以导航，但不会自动变成 `uses`。重复节点、无效 YAML、非法字段、缺失 TeX 标签等不会导致整个工作区崩溃，出现在诊断面板中。

## 3. TeX 与形式化代码

只用 `\bpnode{label}` 标识内容，不要求 `\leanok`、`\uses`。标记放在所绑定内容之前，且处于环境外（普通段落也支持）。保留 `\node{label}` 作为旧拼写别名。标签在单份 TeX 文件中唯一；注释及 verbatim/lstlisting/minted 内的伪标签不计入。

吸附窗口严格定义为：当前标签后的内容，到下一个标签之前；首节点之前的序言与末节点之后的 `\end{document}` 不进入正文。只有有绑定的节点参与上下切换。目录保留全部 TeX 文件（包括无绑定文件），以及 chapter / section / subsection / subsubsection 层级；点击章节定位该节或后续第一个节点，无节点时展示章节源文件。

HTML 由 plasTeX 解析 DOM 再通过受控适配器输出段落、标题、定理环境、列表、强调、引用与数学公式；浏览器通过本地 KaTeX 渲染数学。保留论文 preamble 中支持的单行宏定义和定理定义。禁止执行 TeX 外部命令/读取外部文件，复杂宏、图像及跨文件 `\input` 未能在片段渲染时还原的部分给出警告并允许查看原始 TeX；首版不是完整排版引擎，不承诺所有 arXiv 宏包兼容。TeX 原文永远可访问。

代码解析器返回绑定行号对应的源码；未写行号时按语言声明边界尝试定位（Lean namespace、Agda 顶层签名、Coq Definition/Theorem 等），无法确定或存在多个候选时展示明确提示，不能将整个文件当作已定位声明。模块简写通过语言目录的模块路径查找；跨标准库目录和特殊语法可显式配置 `file` / `lines`。不安装 Lean/Agda/Coq 编译器。

## 4. 用户界面

* 顶部：项目名、节点数量、阅读/知识图谱切换、刷新、导入资料。
* 左侧可折叠目录：论文文件树及章节、Blueprint 文件及节点、全局节点搜索。
* 中栏：面包屑、节点类型/状态、Markdown 描述、依赖与思想来源、阅读/TeX/Markdown 编辑模式、前后节点导航。
* 右侧可折叠代码栏：当前节点绑定的语言及多个声明切换、文件路径/行号/来源、未绑定和远程代码空状态。
* 知识图谱：深色力导向视图（拖动节点、平移、缩放、选中邻居高亮）和传统有向分层视图可切换；依赖箭头从前置节点指向使用者，思想来源用虚线；可按类型、状态筛选，可切换全局/一跳邻域。进入图谱聚焦当前节点，单击显示描述，双击或“打开节点”同时定位正文和代码。循环依赖仍可显示。
* 滚动吸附：只在阅读正文滚动区触底后再次向下滚动才进入下一节点，触顶反向相同；短内容先激活边界再切换，设冷却避免惯性连跳；始终提供按钮与 Alt+方向键替代。
* 刷新索引后保留仍存在的选中节点；URL hash 支持深链与浏览器前后退；无节点/无论文/解析错误均有可操作空状态。
* 编辑保存整份 Markdown，携带原始 SHA-256，检测到冲突返回 409；写入前校验、临时文件替换，保护已检测到的外部修改。此机制不是跨进程文件锁，具体边界见[工作区文档](workspace.md)。用户原文件无需转成数据库。

## 5. 下载器

两个下载器均可从 CLI 和界面调用，后台任务显示 queued / running / succeeded / failed。串行处理导入，界面轮询进度与结果。网络超时、状态码、非法内容须变为具体错误；重试由用户发起。

1. 代码：仅接受 GitHub 公共仓库 URL，单独接收 branch/tag/SHA（空值解析默认分支），获取仓库归档，保留代码、许可证及项目配置至 `<语言>/<指定子目录>`；记录来源、ref、下载时间。不执行仓库内容。
2. 论文：接受新版或旧版 arXiv ID、abs/pdf URL，可含版本；输入目标子目录与论文 basename；同时获取 PDF 和源文件，识别 tar/tar.gz、单个 gzip TeX、纯 TeX；无源码/错误页面要明确失败。保留归档路径及资源。PDF 和 TeX 全部验证后提交，失败清理临时目录。记录 arXiv ID 和时间。

不覆盖既有目标；下载上限 100 MiB，解压总量上限 300 MiB，文件数上限 10,000。拒绝 `..`、绝对路径、Windows drive/ADS/reserved name、符号链接、硬链接及设备文件。仅允许固定 GitHub/arXiv 下载域，验证重定向目标。写操作只接受同源请求及会话 token；服务默认绑定 127.0.0.1，不提供远程多用户认证。

## 6. API 与 CLI

* GET `/api/project`：节点、关系、论文目录、统计、诊断、写入 token。
* GET `/api/node?id=...`：描述、TeX 原文/渲染内容、代码绑定及前后节点。
* GET `/api/document?path=...`，PUT `/api/document`：Markdown 原文与版本校验。
* GET `/api/tex?path=...`：论文全文与目录。
* POST `/api/reload`：重建索引。
* POST `/api/import`，GET `/api/jobs/{id}`：创建导入任务与查询结果。
* `python -m qprint serve --workspace PATH --port 8765`。
* `python -m qprint check --workspace PATH` 输出诊断，存在错误退出码 1。
* `python -m qprint import-code URL --language agda --dest serre-finiteness [--ref main] --workspace PATH`。
* `python -m qprint import-paper ID --dest Topology --name Lin20K3 --workspace PATH`。

默认工作区为 `examples/demo`；指定路径时只加载该目录。Python 命令统一通过 `conda run -n qprint` 执行。

## 7. 验收与交付

| 编号 | 验收条件 | 验证方法 |
| --- | --- | --- |
| A1 | 多节点 Markdown、围栏、链接、诊断、循环图 | 解析器单元测试 |
| A2 | 环境内外 TeX 片段边界、章节、伪标签排除、DOM 数学 | TeX 测试 |
| A3 | 零/多绑定及三语言定位、远程空状态 | 代码解析测试 |
| A4 | 目录/双栏/搜索/图谱/点击/双击/折叠/吸附 | 浏览器交互验收 |
| A5 | Markdown 编辑、冲突保护、重建索引 | API 测试及浏览器验收 |
| A6 | 仓库/论文下载格式、错误、覆盖与解压保护 | 模拟网络测试（不在测试中下载论文） |
| A7 | 任意路径逃逸被拒绝、内容安全输出 | 安全回归测试 |
| A8 | 文档中的命令能启动 demo，依赖可重复安装 | CLI/API 冒烟测试 |

交付：本 spec、安装与数据编写 README、Python 包、前端静态资源、本地数学渲染资源、示例知识库、pytest 测试、验收记录。记录实测结果及限制，不把未运行的验证写成通过。

## 8. 图谱分级扩展（2026-09-20）

依据 [blueprint 分级指南](../blueprint分级指南.md)，分级仅由图谱从现有文件派生，不新增强制 Project / Milestone 数据模型、不改变 node 元数据、不要求迁移文件。

1. 三种颗粒度：一级标题节点、Markdown 文件（milestone）、项目目录。文件级合并所有跨文件引用（含标题链接、文件链接、普通 Markdown 相对链接）；项目级合并跨项目文件边及索引中的项目引用，去除聚合产生的内部自环。节点级保持原有 uses / inspired_by 关系。
2. 项目识别：`<目录名>.md` 优先于 `index.md`；取最近有索引的祖先目录，允许任意子文件夹；无索引祖先时取文件的直接父目录，根目录文件使用根目录分组。同名项目以完整目录路径区分。
3. 节点级默认当前项目，允许手动全范围；Milestone 允许两种范围；项目级固定全范围，禁用范围选择。通过当前阅读节点确定初始项目，也可以显式选择项目。
4. 双击项目 → 全范围 Milestone 图谱并高亮其文件；双击文件 → 所属项目内的节点图谱并高亮该文件所有节点；双击节点 → 既有正文/代码定位。下钻清除旧筛选，成员高亮使用金色描边和文字。
5. 空文件/无一级标题的索引也出现在文件图谱；包含一级标题的索引仍按原有节点规则解析。缺失/歧义文件引用不猜测目标，示例代码、行内代码、HTML 注释和外链不构成引用边。聚合状态是成员状态的摘要，不代表验证结果。
6. `/api/project` 增加只读 `graph`：files、projects、file_projects、node_projects、file_edges、project_edges。保存或刷新时同步重建。

验收补充：无索引回退、带子文件夹的项目、嵌套索引、跨项目依赖、引用去重、空文件、项目循环、两级下钻成员高亮、默认/手选范围及项目级强制全范围。

## 9. 设计参考

* [leanblueprint](https://github.com/PatrickMassot/leanblueprint)：plasTeX blueprint 原理。
* [Sphere Packing](https://thefundamentaltheor3m.github.io/Sphere-Packing-Lean/blueprint/)：章节目录与论文阅读结构。
* [Sphere Eversion](https://leanprover-community.github.io/sphere-eversion/blueprint/index.html)：阅读与依赖图导航。
* [nodum](https://github.com/nodummd/nodum)：现代知识图谱交互参考；未复制其代码。
* [plasTeX package 文档](https://plastex.github.io/plastex/plastex/sec-packages.html)：自定义命令及 DOM。
