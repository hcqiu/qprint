# Blueprint 文件约定

工作区以 `tex/` 保存论文源文、`pdf/` 保存 PDF、`blueprint/` 保存 Markdown。一个项目目录对应一篇论文，一般放在子领域下。milestone 是一份以数学目标组织的 Markdown，例如几个引理与一个主定理，或一个需要多个前置定义的数学对象。每个定义、引理、定理等节点用一级标题表示。不要添加 project/milestone 类型字段。

## 节点文件

````markdown
# thm:example

```qprint
kind: theorem
status: not_started
tex: Paper/main.tex#thm:example
uses:
  - "[[Topology/Paper/definitions#def:object]]"
  - "[[Topology/Existing/results#lem:known]]"
```

在给定假设下，对象 $X$ 具有指定性质。

## 证明思路

对前置引理的数学应用说明。
````

这些 ID 仅为格式示例，不能当作已有节点引用。标题在文件内唯一，不能包含 `#`、`|` 或 `]]`。节点 ID 是不含 `.md` 的 Blueprint 根目录相对路径与标题，以 `#` 连接；区分大小写。

`qprint` YAML 围栏必须紧跟一级标题。`kind` 允许 `definition`、`lemma`、`theorem`、`conjecture`、`proof`、`other`；命题和推论使用 theorem。`status` 允许 `not_started`、`in_progress`、`complete`，生成默认为 `not_started`；完成论文 review 不代表形式化证明完成，不据此更改 status。

`tex` 为 `tex/` 下相对文件路径与 bpnode 标签，`.tex` 可省略。`uses` 为加引号的 wikilink 数组；同文件可用 `[[#标题]]`，跨文件推荐完整根目录相对路径。`inspired_by` 可表达思想来源，不能替代证明依赖。正文支持 Markdown 和数学表达式。不要为没有形式化代码的节点伪造 Lean/Agda/Coq 绑定。

## 项目索引

索引命名为 `index.md` 或与项目目录同名。用 frontmatter 记录元信息，用二级标题列出各 milestone 与依赖项目，避免把索引标题当作数学节点。

```markdown
---
title: 论文完整标题
authors:
  - 作者
year: '2025'
keywords:
  - 关键词
---

## Blueprint 索引

- [[Topology/Paper/definitions.md]]
- [[Topology/Paper/main-result.md]]

## 依赖项目

- [[Topology/Existing/index.md]]
```

列出的依赖项目须已经存在。其他论文尚无 Blueprint 时仅在 review 中说明参考关系。项目内可以有子目录；改变路径后同步修改当前项目中的全部节点链接和索引。
