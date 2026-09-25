# Knowledge Navigator

[中文](knowledge-navigator.md) | [English](knowledge-navigator.en.md)

[当前状态接口与独立 agent 重测报告](knowledge-navigator-state-evaluation.md)

[相对路径与无参数 runtime 回归验证](knowledge-navigator-portability.md)

本模块实现参考对话《修改渲染代码并创建工具》的第 1–13、16、17 节。
第 14 节的 UI 共用索引和第 15 节的全项目四层重构不在本次范围内。
后续增加了网页当前节点同步接口；现有 UI 的渲染和图索引保持原有实现。
模块独立位于 `qprint/knowledge/`，复用现有 Blueprint、TeX 扫描器；不执行 TeX 或形式化编译器。

## 从 Qprint 文件夹启动

在 Qprint 文件夹启动 Hermes、OpenCode、DeepSeek Harness，或在 ChatGPT、Codex、Claude Code 中打开此文件夹。
宿主首次准备环境：

```powershell
conda env create -p ./.conda -f environment.yml
conda run -p ./.conda qprint serve --workspace examples/demo
```

若宿主已把 qprint CLI 放在 PATH，agent 只需：

```text
qprint agent state
qprint agent open NODE_ID
qprint agent source NODE_ID --source tex --max-lines 100
qprint agent dependencies NODE_ID --depth 2
qprint agent backlinks NODE_ID
qprint agent context NODE_ID --token-budget 6000
```

CLI 不在 PATH 时使用 `conda run -p ./.conda qprint agent state`，无需 activate。
开发仓库若已明确指定 `conda run -n qprint`，可继续使用该环境。
每次新开 PowerShell 都可直接运行 `conda run -n qprint qprint agent state`，无需先 activate，
也无需继承启动 UI 的终端变量。UI 服务启动时自动准备索引并发布 workspace；无需手动执行首次 index。
运行命令、skill、来源引用与工具文件字段都使用相对 Qprint 文件夹的路径。
这里必须是**启动当前 UI 的同一个 Qprint 文件夹**；安装在 Conda 环境中的 `qprint`
命令不会自动切换到源码或服务目录。即使浏览器已打开，在另一个同名目录运行也无法读取它的状态。
`runtime_status="not_published"` 表示当前文件夹没有 UI runtime，先核对目录；
`runtime_status="published"` 则表示已找到本文件夹中的 runtime 指针，并不表示浏览器一定仍打开。

## UI → runtime → agent

UI 自动生成页签 session，点击节点、选择文本或切回页签时上报状态。
Qprint 根目录的 `.qprint/runtime/navigation.json` 记录相对 workspace 和当前 session；
该指针使用原子替换发布，不要求 agent 读取状态文件或自己选择 session。
`qprint agent state` 以及后续查询默认跟随它，无需 `--workspace` 或 `--session`。
显式覆盖仍可用于离线工作，例如 `--workspace examples/demo`；不允许绝对路径或离开 Qprint 文件夹。
没有 runtime 时只使用当前文件夹，不扫描目录猜测用户正在读哪篇论文。
尚未启动 UI 且没有索引时，`state` 返回成功的 JSON，包含 `current_node=null`、
`index_status="unavailable"` 与启动 UI 的提示，不会因为缺少索引退出失败。
若已有页面快照但索引缺失，仍返回节点 ID、文档、选择文本和 session，
以 `focus_verified=false` 标明暂时无法用索引校验；搜索和原文查询仍需有效索引。

```json
{
  "workspace": "examples/demo",
  "session": "browser-session",
  "path_base": "qprint",
  "current_node": {"id": "node-A"},
  "current_document": "examples/demo/tex/paper.tex",
  "selection": "用户选中的文字"
}
```

所有 `source_locations.file`、`fragments.file`、边来源与形式化文件位置都相对 Qprint 文件夹，
不能再把 workspace 前缀拼一次。当前节点还包含项目、视图、来源位置、时间戳与访问记录。
原文读取只更新历史，不覆盖 UI 当前节点；非节点文档页可保持 `current_node=null`，同时报告当前文档。
节点删除时标记 `stale_focus`。这是最后一次页面快照，不保证页面仍打开。
多个页签以最近一次发布或获得焦点者为准；需要固定其他页签时可显式指定 session。
整个 Qprint 文件夹移动后，runtime 不需要修改。

UI 使用受 token/同源保护的 `POST /api/navigator/focus`；`GET /api/navigator/state` 可读取同一状态。
嵌入式宿主传入 `create_app(workspace, runtime_root=qprint_root)`。
该写接口和 `set_focus` 不属于 agent 查询工具。
UI 宿主启动时增量准备索引（包括旧 WAL 存储迁移）；离线维护仍可运行 `qprint index`。
只读沙箱中保存历史失败会附 `state_warning`，不阻断有效原文查询。

Windows 下顺序启动 Conda；多个已知查询可用单进程批量入口：

```text
qprint agent batch --calls '[{"tool":"kb_state","arguments":{}},{"tool":"kb_source","arguments":{"node":"NODE_ID","max_lines":80}}]'
```

每批最多 32 个注册查询工具，顺序返回 result/error；部分失败退出码为 1，保留其余结果。
修改索引或边注释的维护操作不在批量查询白名单中。

## 架构要求与实现对应

| 参考章节 | 实现 |
| --- | --- |
| 1–2 | `KnowledgeNavigator` 统一导航；节点 ID 为基本实体，文件是来源容器 |
| 3 | `.qprint/index/knowledge.sqlite`：nodes、edges、aliases、chunks、文件缓存、embedding 和边注释；会话状态独立存储 |
| 4 | symbol/graph + SQLite FTS5 + 可插拔 semantic embedding；固定检索顺序 |
| 5–6 | 八个核心 `kb_*` 工具；另增 state 和 explain_edge，共十个查询工具；state → resolve/open → source |
| 7–8 | Markdown 导航摘要优先，TeX 原文验证；兼容旧 qprint 围栏与新增单节点 front matter |
| 9 | 搜索 `radius=1` 默认扩展依赖、反向引用及 parent 邻居 |
| 10 | SQLite 按 session 维护最近 32 个打开的节点，同名 alias 优先唯一 working-set 候选 |
| 11 | 文件 mtime/size 快速判断，SHA-256 内容确认，节点/片段差量 SQL 更新、embedding 哈希缓存 |
| 12 | 索引由确定性程序构建，附带 `skills/knowledge-navigator/SKILL.md` 指导 agent 使用 |
| 13 | Python API、`qprint agent` CLI、JSON tool schemas 与统一 dispatcher |
| 16 | formal symbol → Blueprint → 多层 backlinks → 有界 source 读取 |
| 17 | `kb_explain_edge` + `explain_link`/`annotate-edge`，保存人工或 agent review 的解释与边来源 |

## 身份、来源与关系

显式 front matter `id` 优先；否则带 TeX 绑定的节点采用
`<TeX相对路径去后缀>/<bpnode>`，如 `Topology/Paper/main/ganea-iso`。
Markdown 路径、旧 `文件#标题`、bpnode、TeX label、绑定的形式化 declaration 都进入 aliases。
Markdown 绑定到 bpnode 内部的 `\label` 时也合并到同一节点。
未绑定 TeX 的旧格式节点继续采用旧 ID；普通 Markdown 文件也有 document 节点。
同一 bpnode 的 statement/proof 可以对应多个不连续来源片段。
需要在移动 TeX 文件之后仍保持 ID 时，应指定显式 `id`。

`resolve` 不默选跨论文重名候选，返回 `ambiguous` 及候选来源。
索引器解析依赖时优先精确 ID、同文件引用和同项目唯一匹配。
新文件加入、删除或更名后，会重新解析缓存贡献间的关系，修复受影响的引用。
未解析关系保留 `target_ref` 和 `target=null`，不会伪造目标节点。

图的方向为 **使用者 → 被使用者**，即 `A --uses--> B` 表示 A 依赖 B。
这与现有 UI 图的展示箭头约定不同；本模块没有改动 UI 图。
`dependencies` 默认只遍历 uses；`backlinks` 默认还包含 ref、mentions、proof_of、formalizes。
`path` 默认双向，可按方向和类型限制，并返回沿途原始有向边。
支持的关系类型为 `uses/ref/defines/proves/proof_of/same_node/formalizes/cites/mentions/parent`。
除明确的 TeX/Markdown 引用和文件父节点外，不推断数学关系。
文献引用是按 TeX 目录命名的外部 citation 实体，不自动补全文献题录。

## Front matter 示例

```yaml
---
id: Topology/EM/loop-em
kind: theorem
aliases: [LoopEM, ΩEM]
description: Loop space of an Eilenberg–Mac Lane space.
proof_summary: Apply the suspension-loop adjunction.
milestone: EM induction
status: in_progress
source:
  tex: Topology/EM/main.tex
  label: thm:loop-em
formal:
  agda:
    declaration: loopEM
    file: Cubical/EM.agda
    lines: [20, 35]
uses:
  - target: Topology/EM/definition
    reason: Supplies the representing space.
---
```

后接 `# Loop space of EM spaces` 和导航正文。`formal.agda` 也接受
`Cubical/EM.agda#loopEM` 这种简写。`source.tex` 相对 `tex/`，形式化文件相对语言目录。
元数据关系接受节点名或 `[[wikilink]]`；正文 `Uses:` 下的 wikilinks 作为 uses，
其他 prose wikilinks 作为 mentions。代码块、行内代码及 HTML 注释中的链接不作为关系。
其他关系可使用同名 front matter 字段。现有多节点 qprint 围栏继续按原格式解析。

front matter 仅扩展 navigator 的解析；当前 UI 仍使用原 Blueprint 格式。
形式化符号定位来自显式绑定和简单声明扫描，复杂语法应填写 `file`、`lines`。
无法唯一定位时返回 `location_status=unresolved`，不会拿整个代码文件冒充声明。
这不是形式化编译器或所有语言的完整 symbol parser。

## 检索、上下文和增量更新

搜索顺序固定：精确 ID → alias → FTS5/BM25 → 图邻居 → semantic。
多词 FTS 默认 OR 匹配，以 BM25 排名；输入作为普通搜索文本转义，不接受裸 FTS 表达式。
`--scope` 按项目/ID 前缀过滤，`--kind` 可重复，`--radius 0` 关闭图扩展。
`score` 用于说明各阶段的局部排序，不是统一校准的概率；以返回顺序为准。
FTS5 使用 unicode61，适合符号和空格分词；中文自然语言的同义检索可接 embedding。

`open` 返回有限长度导航文本、依赖、source locations 和 formalizations，不自动读文件。
`source` 才读取指定节点的来源范围，默认最多 120 行/20000 字符，可用 `--lines START END` 取交集。
读取前比对内容哈希，过期索引报错提示 `qprint index`。
`context` 按当前节点、直接依赖、二层必要定义、最近工作节点选取内容；预算使用
紧凑 JSON 的 UTF-8 字节数作为保守的 byte-level tokenizer token 上界，包含元数据。
返回 `token_upper_bound` 和 `truncated`。不是特定模型的精确 token 计数。

更新仅重新读取/解析改变的源文件。关系合并使用缓存贡献，不再次读全部源文件；
差异比对后只写变化节点、边、片段及 embedding。文件枚举与缓存图投影仍随工作区规模增长，
尚未引入操作系统文件事件监听器。`--verify-hashes` 可检测 size/mtime 均未变化的内容修改。
事务保证失败更新不留下半成品索引；解析错误必须修复后才能发布新索引。
查询只使用已提交快照，更新与会话写入由 SQLite 协调。

## Python 与 tool API

```python
from qprint.knowledge import KnowledgeIndexer, KnowledgeNavigator
from qprint.knowledge.tools import call_tool, tool_definitions

KnowledgeIndexer("my-math").update()
with KnowledgeNavigator("my-math", session="em-review") as kb:
    result = call_tool(kb, "kb_resolve", {"query": "LoopEM"})
    if result["status"] == "resolved":
        summary = kb.kb_open(result["node"]["id"])
        context = kb.kb_context(result["node"]["id"], token_budget=6000)
```

`tool_definitions()` 返回八个核心工具和 `kb_explain_edge` 的 JSON Schema；
`call_tool` 是共享 dispatcher，可由 MCP host 或其他 agent host 包装。
本模块提供传输无关 tool API，不启动独立 MCP server，也不自动安装客户端配置。
`qprint agent tools` 打印这些 schemas；`agent call TOOL --args JSON` 调用同一实现。

可选 embedding provider 实现 `model_id` 和 `embed(list[str]) -> list[list[float]]`，
分别传给 `KnowledgeIndexer(..., embedding_provider=provider)` 与
`KnowledgeNavigator(..., embedding_provider=provider)`。向量保存在同一 SQLite 数据库，
按 chunk hash + model_id 缓存，以余弦相似度检索；模型更新应更换 model_id。
无 provider 时完全离线运行，不下载模型，不调用外部 API；默认 CLI 不启用 embedding。
语义检索使用线性向量扫描，适合第一版规模，未引入 ANN 服务。

边解释可以由 front matter 的 `reason` 提供，也可在 review 后执行：

```text
qprint agent annotate-edge A B --type uses --reason "B identifies the fiber of p_n." --workspace PATH
```

注释保存在 edge_notes，正常增量更新会保留，查询同时返回原始文件和行号。
没有 reason 的边返回 `unexplained`，程序不生成数学解释。索引中的 review 注释及 working set
不是源文件内容；删除整个 `.qprint/index` 会丢失它们，重建前按需备份该目录。
