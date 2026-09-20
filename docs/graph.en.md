# Knowledge graph module

[中文](graph.md) | [English](graph.en.md) · [Documentation](index.en.md)

Implementation: [graph_index.py](../qprint/graph_index.py), [graph-view.js](../qprint/static/graph-view.js), [graph.js](../qprint/static/graph.js). Tests: [Python aggregation tests](../tests/test_graph_index.py), [frontend state tests](../tests/graph_view.test.mjs). Source requirement: [blueprint granularity guide](../blueprint分级指南.md), in Chinese.

## Levels and project detection

| Granularity | Graph object | ID |
| --- | --- | --- |
| Blueprint node | Markdown level-one heading | `folder/file#heading` |
| Milestone | Markdown file, including empty files and indexes | `folder/file.md` |
| Project | A group derived from indexes/directories | Full directory path; `.` for root |

Within a directory, `<directory-name>.md` takes precedence as its index, followed by `index.md` (matched case-insensitively). A file belongs to its nearest indexed ancestor directory. A nested index starts a new project. With no indexed ancestor, its immediate parent directory is used.

```text
blueprint/
  Topology/
    Topology.md          # Topology project index
    Maps.md              # belongs to Topology
    Notes/Continuity.md   # still belongs to Topology
    Advanced/
      index.md           # new Topology/Advanced project
      Limits.md          # belongs to Topology/Advanced
  Algebra/Groups.md      # no index: falls back to Algebra
  Scratch.md             # root group .
```

Full paths distinguish directories with identical names. Indexes remain ordinary Markdown: headings create nodes, and heading-free indexes still appear in the file graph. No additional Project / Milestone fields are required.

## Edges and aggregate status

Node edges use only `uses` / `inspired_by`. File edges scan prose wikilinks, wikilinks in `qprint` metadata, and ordinary local Markdown links. File targets, heading targets, aliases, relative paths, and optional `.md` are supported. Resolution tries a vault path, a path relative to the current file, and a unique basename, in that order. Missing or ambiguous references are skipped.

HTML comments, ordinary code fences, inline code, and external links do not create file edges. Directed file pairs are deduplicated; within-file references create no self-loop. Project edges merge file edges between different projects. Their `count` is the number of contributing distinct directed file pairs, not the number of raw link occurrences.

All arrows point from the referenced object to its referrer. Node-level inspiration edges are dashed. Coarse edges use `reference` and do not preserve node relation types. Cycles are valid; layered layout handles them through strongly connected components.

A file/project is `complete` only if every member is complete. Empty groups or groups entirely `not_started` are `not_started`. Other combinations are `in_progress`. This summarizes author-assigned status, not verification.

## Scope and drill-down

Node level defaults to the current project. File level allows current-project or all scope. Project level always shows all projects and disables scope selection. The initial project comes from the reader's selected node and can be changed explicitly. Scoped graphs retain only edges with both endpoints in scope.

1. Double-click a project: open the all-scope file graph and highlight every file in that project in gold.
2. Double-click a file: open the node graph within its owning project and highlight every node in that file; other nodes in that project remain visible.
3. Double-click a node: open the reader and locate its prose and code.

Drill-down clears prior kind, status, and neighborhood filters to keep members visible. Member highlighting is separate from single-node selection. Empty files have no member nodes and do not create fabricated placeholders.

## Data interface and limits

`/api/project.graph` includes `files`, `projects`, `file_projects`, `node_projects`, `file_edges`, and `project_edges`. Saves and refreshes rebuild them. Frontend `graph-view.js` uses pure functions for level, scope, focus, and member highlights. `graph.js` owns SVG rendering, layouts, and hit regions.

Force and layered layouts support dragging, zooming, panning, and keyboard preview/open actions. The URL currently stores the reader node only; graph scope and layout are not persisted. Large-graph performance remains unbenchmarked, and recorded browser acceptance uses a small demo.
