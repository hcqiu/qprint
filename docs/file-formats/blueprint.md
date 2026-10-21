# Blueprint 文件格式

[返回格式总索引](index.md)

## 节点文件结构

Blueprint 使用工作区 `blueprint/` 下的 `.md` 文件。一个项目由目录组织，一个 milestone 对应一份 Markdown，一个数学节点对应一个一级标题。二级及更低标题属于节点正文，不新增节点。

节点的 `qprint` 围栏可省略；使用时应紧随一级标题，位于正文之前，围栏内容为 YAML mapping。代码围栏内的标题和文件开头的 frontmatter 不创建节点。

| 字段 | 格式与默认值 |
| --- | --- |
| `kind` | `definition`、`lemma`、`theorem`、`conjecture`、`proof`、`other`；默认 `other` |
| `status` | `not_started`、`in_progress`、`complete`；默认 `not_started`，由作者维护 |
| `tex` | 可省略；提供时为非空字符串，推荐 `path/file.tex#label` |
| `uses` | 依赖节点的 wikilink 字符串数组，默认 `[]` |
| `inspired_by` | 思想来源节点的 wikilink 字符串数组，默认 `[]` |
| `lean`、`agda`、`coq` | 声明字符串、绑定对象或两者组成的数组，默认 `[]` |

命题、推论使用 `theorem`；不要新增 `proposition`、`corollary`、`project` 或 `milestone` 类型。项目和 milestone 的层级通过目录、索引、文件表示。

每个代码绑定对象接受下列字段：

| 字段 | 规则 |
| --- | --- |
| `declaration` | 必填，非空声明名；建议完整限定名 |
| `file` | 可选，相对对应语言目录的源码路径；建议明确填写 |
| `lines` | 可选，`[start, end]`，从 1 开始的正整数闭区间 |
| `url` | 可选，以 `https://` 开头的来源链接 |

节点元数据未知字段产生 warning；绑定对象未知字段或非法值产生 error。`complete` 只是作者进度，不是编译器结论。

## 完整节点示例

保存为 `examples/format-demo/blueprint/Basics/Identity/results.md`。代码绑定对应 [Lean 示例](lean.md) 与 [Agda 示例](agda.md)，TeX 绑定对应 [TeX 示例](tex.md)。

````markdown
# identity-function

```qprint
kind: definition
status: not_started
tex: Identity/main.tex#identity-function
uses: []
inspired_by: []
lean:
  declaration: Identity.idNat
  file: Identity/Identity.lean
agda:
  declaration: Identity.idNat
  file: Identity/Identity.agda
```

定义自然数上的恒等函数 $i(n)=n$。

# identity-value

```qprint
kind: theorem
status: not_started
tex: Identity/main.tex#identity-value
uses:
  - "[[Basics/Identity/results#identity-function]]"
inspired_by: []
lean:
  - declaration: Identity.identity
    file: Identity/Identity.lean
agda:
  - declaration: Identity.identity
    file: Identity/Identity.agda
```

对每个自然数 $n$，恒等函数满足 $i(n)=n$。

## 证明思路

展开 [[#identity-function|恒等函数的定义]]，由等式的自反性得到结论。
````

## 标识与引用

上例第二个节点的完整 ID 是 `Basics/Identity/results#identity-value`。文件路径不含 `.md`，`#` 后是精确的一级标题，区分大小写。同文件标题必须唯一，标题不能含 `#`、`|` 或 `]]`。更改文件名、目录或标题后需同步更新引用。

| 链接 | 含义 |
| --- | --- |
| `[[Basics/Identity/results#identity-function]]` | 从 Blueprint 根目录定位节点 |
| `[[#identity-function]]` | 当前文件内节点 |
| `[[results#identity-function]]` | basename 简写，仅目标唯一时可靠 |
| `[[#identity-function\|恒等函数]]` | 指定显示文字；实际源码中竖线前无需反斜杠 |
| `[[Basics/Identity/results.md]]` | 文件链接，用于索引或文件图，不指定节点 |

在 YAML 的 `uses` / `inspired_by` 内必须给整个 wikilink 加引号。正文中的链接只提供导航；只有元数据中的 `uses` / `inspired_by` 建立节点依赖或思想来源边，方向为被引用节点指向当前节点。

`tex` 可省略 `.tex`；仅当 Markdown 与 TeX 在各自根目录下有相同相对路径时，才能直接填写标签。本例两个目录结构不同，保留完整 `Identity/main.tex#identity-value`。

## 项目索引示例

保存为 `examples/format-demo/blueprint/Basics/Identity/index.md`：

```markdown
---
title: Identity on natural numbers
authors:
  - Example Author
year: '2026'
keywords:
  - natural numbers
  - identity
---

## Blueprint index

- [[Basics/Identity/results.md]]

## Dependencies

本项目没有外部 Blueprint 依赖。
```

索引使用 frontmatter 和二级标题，避免把项目名称误建为数学节点。目录内同名文件（例如 `Identity.md`）也可作为索引，且优先于 `index.md`；建议一个项目只保留一种。嵌套索引会开始新的项目分组。

若有外部依赖，索引可列出其真实存在的项目索引文件；具体节点的 `uses` 仍需单独填写。索引中的文件列表不能替代节点依赖。详见 [图谱规则](../graph.md)。
