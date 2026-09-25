# 知识图谱模块

[中文](graph.md) | [English](graph.en.md) · [文档目录](index.md)

实现：[graph_index.py](../qprint/graph_index.py)、[graph-view.js](../qprint/static/graph-view.js)、[graph.js](../qprint/static/graph.js)。测试：[Python 聚合测试](../tests/test_graph_index.py)、[前端状态测试](../tests/graph_view.test.mjs)。需求依据：[blueprint 分级指南](../blueprint分级指南.md)。

## 层级与项目识别

| 颗粒度 | 图中对象 | ID |
| --- | --- | --- |
| Blueprint 节点 | Markdown 一级标题 | `目录/文件#标题` |
| Milestone | Markdown 文件，包括空文件和索引 | `目录/文件.md` |
| 项目 | 按索引/目录派生的分组 | 完整目录路径，根为 `.` |

目录内的 `<目录名>.md` 是优先索引，其次是 `index.md`（该名称匹配不区分大小写）。文件归属最近的有索引祖先目录；嵌套索引开始新的项目。没有索引祖先时，使用文件的直接父目录。

```text
blueprint/
  Topology/
    Topology.md          # Topology 项目索引
    Maps.md              # 属于 Topology
    Notes/Continuity.md   # 仍属于 Topology
    Advanced/
      index.md           # 新的 Topology/Advanced 项目
      Limits.md          # 属于 Topology/Advanced
  Algebra/Groups.md      # 无索引，回退到 Algebra
  Scratch.md             # 根目录分组 .
```

同名目录由完整路径区分。索引是普通 Markdown，有一级标题就继续创建节点，无标题也进入文件图；不需要额外 Project / Milestone 字段。

## 边与聚合状态

节点边只使用 `uses` / `inspired_by`。文件边扫描正文 wikilink、`qprint` 元数据中的 wikilink 和普通 Markdown 本地链接；支持文件链接、标题链接、别名、相对路径和可省略的 `.md`。解析依次尝试 vault 路径、相对当前文件路径、唯一 basename；缺失或歧义则跳过。

HTML 注释、普通代码围栏、行内代码和外链不产生文件边。同一有向文件对去重，文件内部引用不生成自环。项目边把不同项目之间的文件边合并，`count` 表示贡献的不同有向文件对数量，不是原始链接出现次数。

所有箭头从被引用方指向引用方。节点级思想来源使用虚线；粗粒度边为 `reference`，不保留节点级关系类型。循环合法，分层布局通过强连通分量处理循环。

文件/项目进度：成员全为 `complete` 才是 `complete`；空组或全部 `not_started` 为 `not_started`；其他组合为 `in_progress`。这是作者状态摘要，不是验证结论。

## 范围与下钻

切入“当前 Milestone”时，先使用图中当前选中的 Blueprint 节点，再回退到当前阅读节点，自动同步其项目和文件；没有有效节点时才保留手选文件或使用有效回退。进入该范围后仍可手动选择其他文件，普通刷新不会强制改回阅读文件。切换范围关闭旧的一跳邻域筛选并清除聚合高亮。若切换前是项目颗粒度，进入 Milestone 范围自动展开为 Blueprint 节点，避免仍显示同一个项目圆点；之后仍可手动切换颗粒度。

2026-09-25 起，展示范围分三类，可在任意颗粒度手动切换；切换颗粒度保留当前范围，初始默认当前项目。

| 范围 | 节点颗粒度 | 文件颗粒度 | 项目颗粒度 |
| --- | --- | --- | --- |
| 全范围 | `blueprint/` 全部节点 | 全部 Markdown 文件 | 全部项目 |
| 当前项目 | 所选项目的节点 | 所选项目的文件 | 所选项目 |
| 当前 Milestone | 所选 Markdown 的节点 | 所选 Markdown 文件 | 该文件所属项目 |

范围过滤后只保留两端都在范围中的边。初始项目和 Milestone 来自当前阅读节点；阅读切换到其他节点时同步上下文。项目可手选，Milestone 范围额外显示所选项目内的文件下拉框，以相对项目路径显示，完整路径见上下文提示。手选文件在索引刷新后仍存在时保持；切换项目或文件被删除时回退到当前项目内的有效文件。空文件显示零节点，空工作区不展示其他对象作为替代。

1. 双击项目：切到全范围文件图，金色高亮该项目的全部文件。
2. 双击文件：切到该文件所属项目的节点图，高亮该文件全部节点；同项目其他节点仍可见。
3. 双击节点：打开阅读视图并定位正文和代码。

下钻清除旧类型、状态和邻域筛选，避免隐藏目标成员。成员高亮与单个选中节点分别管理。空文件下钻没有成员节点，不伪造占位节点。

## 数据接口与限制

`/api/project.graph` 包含 `files`、`projects`、`file_projects`、`node_projects`、`file_edges`、`project_edges`。保存和刷新时重建。前端 `graph-view.js` 用纯函数处理层级、范围、`projectId` / `milestoneId` 上下文、焦点与成员高亮；`graph.js` 负责 SVG、布局和命中区域。三种范围复用现有图谱数据，不增加磁盘字段或 API。

支持力导向、分层、拖动、缩放、平移与键盘预览/打开。当前 URL 只保存阅读节点，没有持久化图谱范围或布局。大规模图谱尚未建立性能基准，现有浏览器验收使用小型示例。
