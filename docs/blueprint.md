# Blueprint 节点模块

[中文](blueprint.md) | [English](blueprint.en.md) · [文档目录](index.md)

实现：[blueprint.py](../qprint/blueprint.py)。测试：[test_blueprint.py](../tests/test_blueprint.py)。本模块把一份 Markdown 转成节点和诊断，不读取 TeX 或代码文件。

## 节点与元数据

`parse_markdown(path, text)` 返回 `(nodes, diagnostics)`。`path` 相对于 `blueprint/`。每个一级标题开始一个节点，到下一个一级标题结束；二级及以下标题属于正文。初始 frontmatter 与代码围栏中的标题不创建节点。

节点 ID 为 `Topology/Notes#Identity map` 这样的路径与标题组合，区分大小写。同文件一级标题不能重复，标题不能含 `#`、`|` 或 `]]`。改标题或文件名会改变 ID。

````markdown
# Identity map
```qprint
kind: theorem
status: in_progress
tex: Topology/Notes#identity-map
uses:
  - "[[Topology/Maps#Continuous]]"
inspired_by: []
lean:
  - declaration: Topology.identity_continuous
    file: Topology/Notes.lean
    lines: [10, 18]
agda: []
coq: []
```
说明与数学公式 $f : X \to X$。
## 证明思路
这里仍属于 Identity map 节点。
````

这是格式示例，文件和行号需按实际资料填写。可省略元数据；若提供，应放在标题后、正文前的三反引号 `qprint` 围栏中。

| 字段 | 规则 |
| --- | --- |
| `kind` | `definition` / `lemma` / `theorem` / `conjecture` / `proof` / `other`，默认 `other` |
| `status` | `not_started` / `in_progress` / `complete`，默认 `not_started`，由作者填写 |
| `tex` | 非空字符串；`路径#标签` 或仅标签；路径相对 `tex/`，可省 `.tex` |
| `uses`、`inspired_by` | wikilink 字符串数组；YAML 中必须加引号 |
| `lean`、`agda`、`coq` | 单个声明字符串、绑定对象或两者组成的数组 |
| 绑定 `declaration` | 必填的非空声明名 |
| 绑定 `file` | 相对于对应语言目录的路径 |
| 绑定 `lines` | `[起始行, 结束行]`，正整数、一基闭区间 |
| 绑定 `url` | HTTPS 来源链接 |

节点元数据未知字段产生 warning；绑定对象中的未知字段和非法字段值产生 error。YAML 使用安全加载。无效节点被诊断，有效节点继续返回；[工作区保存](workspace.md) 会拒绝含解析 error 的文本。

## 链接与关系

`resolve_link(link, current_id, nodes)` 支持 `[[Topology/Maps#Continuous]]`、唯一 basename `[[Maps#Continuous]]`、`[[#同文件标题]]` 和 `[[路径#标题|显示名]]`，路径可带 `.md`。缺失或歧义时返回空结果，不猜测。

节点链接必须含标题。`[[Maps]]` 这样的文件链接可以参与[文件图聚合](graph.md)，但不会解析成具体节点。正文链接用于导航，不自动成为依赖；只有 `uses` / `inspired_by` 创建节点图边。边由被引用节点指向当前节点。

公开节点字段包括 `id`、`title`、`path`、`line`、`body`、`kind`、`status`、`tex`、`uses`、`inspired_by` 和合并后的 `bindings`；绑定增加 `language` 标识。`revision(text)` 返回 UTF-8 文本的 SHA-256，用于保存版本比较。

## 常见问题

- YAML 把 wikilink 当数组：给整个 `[[...]]` 字符串加引号。
- 重名链接无法解析：使用相对于 `blueprint/` 的完整路径和准确标题。
- `complete` 与实际证明不一致：它只是人工进度；本模块不运行编译器。
- TeX 或代码绑定缺失：格式解析通过不代表目标存在；分别查看 [TeX](tex-rendering.md) 和[代码定位](formal-code.md)。
