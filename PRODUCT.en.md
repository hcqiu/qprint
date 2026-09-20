# Qprint product overview

[中文](PRODUCT.md) | [English](PRODUCT.en.md) · [Documentation](docs/index.en.md)

Baseline: package version `0.1.0`, including the blueprint graph granularity extension dated 2026-09-20. This document describes implemented behavior. See the [specification](docs/spec.en.md) for the development contract and [TODO](TODO.en.md) for future work.

## Purpose and users

Qprint is a Markdown-centered mathematical knowledge base and proof navigation tool. It connects explanations, paper fragments, and formal declarations so researchers can move from a dependency graph to an argument and its corresponding code.

Its primary users are researchers organizing mathematical notes, learners exploring formalization projects, and authors maintaining links between papers and code. Users retain ordinary files, Git, Obsidian, or their preferred editor; Qprint adds indexing, reading, graphs, and Markdown editing.

## Core concepts

| Concept | Product meaning |
| --- | --- |
| Workspace | A set of local directories loaded by one server instance |
| Blueprint node | One Markdown level-one heading, its metadata, and its body |
| Milestone | One Markdown file in the graph, not a new on-disk data type |
| Project | A group derived from index files and directory ownership; distinct from the whole workspace |
| Binding | A connection from a node to a TeX anchor or a Lean / Agda / Coq declaration |
| Progress | Author-assigned `not_started`, `in_progress`, or `complete`; not compiler verification |

## Typical workflow

1. Start a local workspace, place existing material in its directories, or import GitHub repositories and arXiv papers through the UI or CLI.
2. Create Markdown under `blueprint/`, organize nodes using level-one headings, and record dependencies, progress, and bindings in `qprint` metadata.
3. Place `\bpnode{label}` before the relevant TeX content, and specify code declarations with files and line ranges when needed.
4. Refresh the index, select a node through the tree or search, and read its explanation, paper fragment, and code together.
5. Switch graph granularity, drill from projects to files and then nodes, and narrow the view with scope and filters.
6. Edit the entire file in Markdown mode and save. Reload and manually merge when an external edit causes a conflict.

Creating files, renaming them, and reorganizing directories currently require an external editor. Imports do not generate blueprints or insert TeX anchors.

## Implemented capabilities

| Area | Current behavior |
| --- | --- |
| Knowledge organization | Multiple nodes per Markdown file, wikilinks, dependencies and inspiration, backlinks, diagnostics |
| Paper reading | TeX section tree, anchor fragments, bounded plasTeX rendering, local KaTeX, source view |
| Code navigation | Three languages, multiple declarations, explicit line ranges, heuristic lookup, HTTPS source links |
| Graphs | Node/file/project granularity, current-project/all scope, drill-down member highlights, force/layered layouts, cycles |
| Interaction | Search, collapsible sidebars, narrow layouts, node deep links, previous/next navigation, boundary scrolling |
| Editing | Whole-file Markdown saves, syntax validation, revision conflicts, index rebuilds after saves |
| Imports | Public GitHub repositories, arXiv PDF and source pairs, provenance records, background job status |

Node graphs distinguish `uses` from `inspired_by`. File and project graphs aggregate ordinary references; their edges do not establish proven logical dependencies.

## Boundaries

The current product targets local, single-user use. Reading and graphs use local assets; importing material or refreshing vendored assets requires network access. PDFs are saved as imported resources. The reader centers on TeX fragments and does not provide PDF page navigation.

Qprint does not run Lean / Agda / Coq compilers and has no LSP integration, automated proving, bidirectional AI generation, multi-user collaboration, or legacy leanblueprint converter. `complete` is an author assertion. TeX rendering is not full LaTeX typesetting: cross-file input, external images, complex packages, and multiline macros have limitations, with original source retained on failure.

Graph grouping requires no migration or Project / Milestone metadata. External edits require a manual refresh. Import job history disappears on server restart. No large-graph performance guarantee has been established.

## Success criteria and evidence

A valid node should open from the tree, search, or graph and display its bindings accurately. Missing or ambiguous bindings must be visible. Save conflicts must not silently overwrite detected external edits, and imports must preserve existing destinations. Drill-down must display the correct members and scope while keeping reader selection distinct from member highlighting.

Acceptance criteria are defined in the [specification](docs/spec.en.md). Executed automated tests, browser checks, and network smoke tests are recorded in [verification](docs/verification.en.md). Historical acceptance does not establish compatibility with every paper, repository, or graph size.

Original requirements remain in [Qprint功能需求.md](Qprint功能需求.md) and [blueprint分级指南.md](blueprint分级指南.md), in Chinese. Differences between requested and implemented behavior should be scoped in the specification and tracked in TODO.
