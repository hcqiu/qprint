# Blueprint node module

[中文](blueprint.md) | [English](blueprint.en.md) · [Documentation](index.en.md)

Implementation: [blueprint.py](../qprint/blueprint.py). Tests: [test_blueprint.py](../tests/test_blueprint.py). This module converts Markdown into nodes and diagnostics without reading TeX or code files.

## Nodes and metadata

`parse_markdown(path, text)` returns `(nodes, diagnostics)`. Paths are relative to `blueprint/`. Each level-one heading starts a node ending at the next level-one heading. Lower headings remain body content. Initial frontmatter and headings inside code fences do not create nodes.

Node IDs combine path and heading, for example `Topology/Notes#Identity map`, and are case-sensitive. Level-one headings must be unique within a file and cannot contain `#`, `|`, or `]]`. Renaming a heading or file changes its ID.

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
Explanation and mathematics $f : X \to X$.
## Proof idea
This still belongs to the Identity map node.
````

This example illustrates syntax; use actual files and line numbers. Metadata is optional. When present, place it after the heading and before prose in a triple-backtick `qprint` fence.

| Field | Rule |
| --- | --- |
| `kind` | `definition` / `lemma` / `theorem` / `conjecture` / `proof` / `other`; default `other` |
| `status` | `not_started` / `in_progress` / `complete`; default `not_started`; author-assigned |
| `tex` | Nonempty `path#label` or label alone; path relative to `tex/`, optional `.tex` |
| `uses`, `inspired_by` | Arrays of quoted wikilink strings |
| `lean`, `agda`, `coq` | A declaration string, a binding object, or an array of either |
| Binding `declaration` | Required nonempty declaration name |
| Binding `file` | Path relative to the language directory |
| Binding `lines` | `[start, end]`, positive integers, one-based and inclusive |
| Binding `url` | HTTPS source link |

Unknown node metadata fields produce warnings. Unknown binding fields or invalid field values produce errors. YAML is loaded safely. Invalid nodes produce diagnostics while valid nodes are returned. [Workspace saves](workspace.en.md) reject text containing parser errors.

## Links and relations

`resolve_link(link, current_id, nodes)` supports `[[Topology/Maps#Continuous]]`, a unique basename such as `[[Maps#Continuous]]`, `[[#Heading in this file]]`, and `[[path#heading|display name]]`. Paths may include `.md`. Missing or ambiguous targets return no result rather than a guess.

Node links require a heading. File links such as `[[Maps]]` can contribute to [file graph aggregation](graph.en.md), but do not resolve to a specific node. Prose links enable navigation without becoming dependencies. Only `uses` / `inspired_by` create node graph edges, directed from the referenced node to the current node.

Public node fields are `id`, `title`, `path`, `line`, `body`, `kind`, `status`, `tex`, `uses`, `inspired_by`, and the combined `bindings` array. Bindings carry a `language` field. `revision(text)` computes SHA-256 over UTF-8 text for save revision comparisons.

## Troubleshooting

- YAML interprets a wikilink as an array: quote the entire `[[...]]` string.
- Duplicate names prevent resolution: use the full path relative to `blueprint/` and the exact heading.
- `complete` differs from actual proof status: it is manual progress; this module runs no compiler.
- A TeX or code binding is missing: valid metadata does not prove that its target exists; see [TeX](tex-rendering.en.md) and [code lookup](formal-code.en.md).
