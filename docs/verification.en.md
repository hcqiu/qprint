# Qprint v1 acceptance record

[中文](verification.md) | [English](verification.en.md) · [Documentation](index.en.md)

The following records describe checks executed on their stated dates. This bilingual documentation update does not rerun or reassert those business tests. v1 means the initial product scope; the Python package version is `0.1.0`.

## 2026-09-20: blueprint granularity extension

The [blueprint granularity guide](../blueprint分级指南.md) was implemented with node / Milestone / project levels and all / current-project scope. No grouping fields were added to the stored node format; groups derive from index Markdown and directories.

Automated checks:

```powershell
conda run -n qprint pytest -q --basetemp D:/Qprint_v2/.qprint/tests-granularity-final --tb=short
node --test tests/graph_view.test.mjs
node --check qprint/static/app.js
node --check qprint/static/graph.js
```

Result: **53 Python tests passed; 6 frontend state tests passed**. Python still emitted the two third-party deprecation warnings described below. New coverage included nearest-index ownership, unindexed fallback, duplicate names, empty indexes, Markdown/wikilink references, file-pair deduplication, project aggregation, rebuilds after saves, cycles, exclusion of code/external links, default scope, forced all scope, and both drill-down highlight transitions. API fixtures copy fixed demo files rather than treating separately imported user repositories as test fixtures.

Browser checks on the demo:

- Entering the graph from a Topology node defaults to its project: 8 nodes and 10 edges; all scope shows 10 nodes and 12 edges.
- Project level shows 2 projects and 1 cross-project reference, with scope locked to all.
- Double-clicking Topology opens the all-scope Milestone graph with 3 files and 2 edges, highlighting Topology's 2 files.
- Double-clicking Notes26Continuity opens the Topology node graph and highlights its 5 nodes while keeping other project members visible.
- Selecting Algebra shows 2 nodes; opening Associativity locates Lean lines 6–8.
- Desktop 1440 × 900 and approximately 535 px width were checked. Controls and canvas are separated, and labels stay readable after fitting/scaling.
- Drill-down was checked in force and layered layouts, with no browser JavaScript errors recorded.

The remaining sections preserve initial-version acceptance history.

Date: 2026-09-18. Environment: Windows, Conda `qprint`, Python 3.12.14.

## Automated tests

Command:

```powershell
conda run -n qprint pytest -q --basetemp D:/Qprint_v2/.qprint/tests-final --tb=short
```

Result: **47 passed, 2 warnings**, in 1.29 seconds.

Warnings concerned Starlette test-client deprecations involving httpx / AnyIO, not failed business tests. Dependency versions were recorded in `requirements-lock.txt`. Initial system temporary-directory permission failures were resolved by using a project-local test directory.

| Spec | Coverage |
| --- | --- |
| A1 | Multiple nodes, frontmatter, fences, lower headings, duplicates, invalid YAML, status/lines, wikilinks, ambiguous targets, cycles |
| A2 | Fragment boundaries, comments/verbatim, sections, duplicate labels, plasTeX DOM, math, HTML escaping, dangerous-command and timeout fallbacks |
| A3 | Lean/Agda/Coq lookup, namespaces, explicit lines, module shorthand, remote bindings, missing/ambiguous declarations |
| A5 | API saves/rebuilds, revision conflicts, invalid metadata rejection, empty workspaces |
| A6 | zip/tar/gzip/plain TeX, default branches, license retention, paired PDF/source, import failures, background job success/failure |
| A7 | Relative/Windows special paths, linked files, archive size, external redirects, download limits, token/Origin/Host checks |
| A8 | Page and local JS/CSS/math font availability |

## Browser acceptance

Checks were performed against the local service at `http://127.0.0.1:8765`:

- Desktop 1440 × 960: paper folders/files/sections and parallel content/code panels worked.
- Approximately 303 px width: initial cramped panels were fixed; header actions wrapped and content/code stacked.
- Lean → Agda → Coq switching updated source paths and line numbers.
- Reading → TeX switching and KaTeX rendering worked.
- Previous/next buttons and another scroll after reaching the bottom updated the node and code together.
- Searching Homotopy returned one result.
- Acceptance text was added through Markdown mode, saved, and reloaded; the original demo text was then restored and saved.
- The code panel collapsed and reopened.
- Force/layered switching worked; status filtering showed 2 in-progress nodes, and the selected-node neighborhood showed 5 nodes and 6 edges.
- Clicking Homotopy previewed its description. Double-clicking Composition of continuous maps located prose and Lean lines 8–10.
- Label hit detection was fixed; node dragging, canvas panning, and wheel zoom were exercised.
- An invalid repository submitted through the import UI produced a specific background failure. The paper form displayed arXiv input and a paper filename field.
- No browser JavaScript errors were recorded.

## Real network imports

`conda run -n qprint python tools/smoke_imports.py` downloaded into `.qprint/network-smoke-*`, without changing demo content.

| Source | Result |
| --- | --- |
| GitHub `CMU-HoTT/serre-finiteness` | Resolved `main`, imported 40 files, preserved directories and provenance |
| arXiv `1603.04246` | Retrieved PDF and 3 source files as paired paper resources |

These checks verified actual endpoints and archive handling, not universal source availability or compilation of imported code. Results were also recorded in `.qprint/network-smoke.json`.

## Startup and limits

`start.ps1` started the service, and page availability was checked in a new process. The demo index contained 10 nodes, 12 relations, and 1 paper, with no diagnostics.

TeX rendering uses a separate parser process and preserves source after an eight-second timeout. Common paragraphs, theorems, sections, lists, and mathematics are supported. Complex packages, images, cross-file input, and multiline macros remain initial-version limits. Large-graph performance was not benchmarked; browser records concern the 10-node demo. No Lean/Agda/Coq compiler was run; progress is author-assigned. Follow-up goals are described in the specification and [TODO](../TODO.en.md).
