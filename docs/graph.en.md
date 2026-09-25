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

Entering current-Milestone scope first follows the selected Blueprint node in the graph, then falls back to the reader node, updating both project and file. Only when neither is valid does it retain a manual file or use a valid fallback. Once inside this scope, users can still choose another file; ordinary refresh does not force it back to the reader file. Scope changes clear the previous one-hop filter and aggregate highlights. Entering Milestone scope from project granularity automatically expands to Blueprint nodes instead of leaving the same project bubble visible. Granularity can still be changed manually afterward.

Since 2026-09-25, three scopes can be selected manually at every granularity. Changing granularity preserves scope; the initial default remains current project.

| Scope | Node granularity | File granularity | Project granularity |
| --- | --- | --- | --- |
| All | Every node under `blueprint/` | Every Markdown file | Every project |
| Current project | Nodes in the selected project | Files in the selected project | The selected project |
| Current Milestone | Nodes in the selected Markdown file | The selected Markdown file | Its owning project |

Only edges with both endpoints in scope remain. The reader node supplies the initial project and Milestone; selecting another reader node updates context. Projects can be selected manually. Milestone scope adds a file selector within that project, displaying project-relative paths; the context label shows the full path. A manually selected file survives index refresh while it still exists. Changing projects or deleting the file falls back to a valid file in the current project. Empty files show zero nodes, and empty workspaces never substitute unrelated objects.

1. Double-click a project: open the all-scope file graph and highlight every file in that project in gold.
2. Double-click a file: open the node graph within its owning project and highlight every node in that file; other nodes in that project remain visible.
3. Double-click a node: open the reader and locate its prose and code.

Drill-down clears prior kind, status, and neighborhood filters to keep members visible. Member highlighting is separate from single-node selection. Empty files have no member nodes and do not create fabricated placeholders.

## Data interface and limits

`/api/project.graph` includes `files`, `projects`, `file_projects`, `node_projects`, `file_edges`, and `project_edges`. Saves and refreshes rebuild them. Frontend `graph-view.js` uses pure functions for level, scope, `projectId` / `milestoneId` context, focus, and member highlights. `graph.js` owns SVG rendering, layouts, and hit regions. All three scopes reuse existing graph data without new on-disk fields or APIs.

Force and layered layouts support dragging, zooming, panning, and keyboard preview/open actions. The URL currently stores the reader node only; graph scope and layout are not persisted. Large-graph performance remains unbenchmarked, and recorded browser acceptance uses a small demo.
