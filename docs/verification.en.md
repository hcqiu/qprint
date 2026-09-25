# Qprint v1 acceptance record

> Command examples now use the project-local `.conda` convention. Historical results and timings are unchanged; this command migration does not imply those experiments were rerun.

[中文](verification.md) | [English](verification.en.md) · [Documentation](index.en.md)

The following records describe checks executed on their stated dates. This bilingual documentation update does not rerun or reassert those business tests. v1 means the initial product scope; the Python package version is `0.1.0`.

## 2026-09-25: three graph scopes

Follow-up fix: scope events now call `changeGraphScope`, resolving the Milestone from the selected graph node or reader node, synchronizing cross-project ownership and retaining focus. Entering Milestone scope from project granularity expands nodes and clears the old neighborhood filter. `node --test tests/graph_view.test.mjs`: **16 passed**; both JS module syntax checks passed. Browser checks switched Topology current project (8 nodes / 10 edges) to Maps.md (3 nodes / 3 edges). After manually choosing Notes, reentering Milestone returned to reader node Continuous's Maps file. Selecting Identity map in the graph then switching scope selected Notes (5 nodes / 5 edges) and retained node selection. A single project bubble expanded to Maps' 3 nodes. No JavaScript errors were recorded. The Python suite was not rerun for this fix.

Added current-Milestone scope and a file selector. All, current project, and current Milestone are independent of granularity; project level no longer forces all scope. Initial file context comes from the reader, manual selection survives refresh, and project changes, deletion, and empty files have safe fallbacks.

`node --test tests/graph_view.test.mjs`: **11 passed**. Syntax checks passed for `qprint/static/app.js` and `qprint/static/graph-view.js`. Coverage includes file-local nodes/internal edges, all-scope restoration, scope retention across levels, reader/manual context, deletion/empty files, and existing drill-down highlights. Python logic was unchanged and the Python suite was not rerun for this change.

Local browser checks on the current workspace: all scope showed 267 nodes / 560 edges; `Topology/KPT25TwoStabilizations` showed 216 nodes / 468 edges; `01-lattice-foundations.md` showed 12 nodes / 16 edges, and selecting `02-pin-spectrum.md` showed 10 nodes / 11 edges. Switching to project granularity retained Milestone scope and showed 1 project; manually selecting all restored 4 projects. Initialization after reload worked; the narrow-window file selector displayed project-relative filenames. No browser JavaScript errors were recorded during this check. These counts describe the current material snapshot, not a fixed demo baseline.

## 2026-09-22: FLT3 reports and legacy toolchains

The downloader reproduced the missing legacy release digest failure; the original report existed but had no browser entry point. Added readable/downloadable persistent reports, explicit exception/storage failures, legacy compiler acquisition, Lake name/Git metadata and cache-directory compatibility. FLT3 native default targets passed with original source/configuration hashes preserved. See the [FLT3 experiment](flt3-experiment.en.md). Full Python suite: **216 passed**, with two existing warnings; Node: **12 passed**. Clicking an actual history report in the browser displayed its error and diagnosis.

## 2026-09-22: sphere-eversion wait investigation

The production downloader reproduced the same pinned commit. After correcting the newer ProofWidgets release strategy, native mathlib cache preparation and `lake build` passed. Selected sources/configuration stayed unchanged; scope was native default targets with no additional safety audit. See the [experiment record](sphere-eversion-experiment.en.md) for reports and timings.

Added request-local progress, download bytes/extraction counts, build activity and elapsed time. Full Python suite: **184 passed**, with two existing dependency deprecations. Node frontend tests: **10 passed**. Coverage includes running API snapshots, unknown totals, failing observers, subprocess timeout and both ProofWidgets strategies. This turn validated frontend formatting and API behavior through tests, without claiming another browser-interaction acceptance run. The user's existing server was not restarted.

## 2026-09-22: post-download verification and restricted recovery

Full pytest in Conda `qprint`: **176 passed**, with two existing FastAPI/Starlette deprecation warnings. Coverage includes policies, native entries, resume/integrity, archive boundaries, pinned sources, cache repair, release receipts, helper scope/retry limits, source/configuration changes and API/CLI import switches. The runtime skill passed quick_validate.

Real Agda 2.8.0 respected inherit/require/off. TypeTopology's upstream `AllModulesIndex.lagda` passed under inherit in about 566 seconds, without an extra safe audit. A fresh Lean topology import acquired nine locked dependencies; after fixing Windows release receipts, a fresh runtime helper replay passed native Lake default targets. It reused 7740 existing official cache objects, not a cold-cache benchmark. An independent minimal-context skill fixture also completed real Lean checking. See [experiment reports](external-topology-experiment.en.md).

Browser checks confirmed default-on, opt-out and hiding the option for papers. Archive comparisons confirmed unchanged original 5 Lean / 996 Agda sources and fresh Lean sources/native configuration. Download, checking and safety results remain separate; universal upstream success is not guaranteed. The full Release was not rebuilt; its manifest now includes the runtime skill.

## 2026-09-21: managed local formal environments

The subsequent modular extension passed 136 regressions and a fresh-agent version-repair experiment with all 35 serre-finiteness modules passing. See [experiment record](serre-finiteness-experiment.en.md). The following 115-test and ZIP results belong to the earlier phase.

Installed in gitignored stores: Lean 4.19.0, Agda 2.8.0, and Cubical 0.9 pinned to `b150186d2544e7efeddd31e5d14a8b9ecbb100f7`. Existing imported material was not moved. Added manager/resolver/context, project requirements, receipts, and explicit light/full release manifests.

Executed `.\.conda\python.exe -m pytest -q --basetemp .qprint/tests-toolchain-release-final --tb=short`: **115 passed, 2 warnings, no skips**, 6.85 seconds. The existing dependency deprecations remain. Coverage includes exact versions, floating/conflicting/rc rejection, explicit PATH fallback, isolated Agda libraries/data, hashes/archives/atomic installs/removal, discovery, ZIP input rules, and real compilers.

`.\.conda\python.exe -m qprint verify --workspace examples/verification` passed Lean build/environment lookup and Agda/Cubical typechecking/declaration probes. Real missing-declaration tests failed as expected. Initial global Cubical flags broke primitive full/erased mode boundaries; native library scope is now preserved, mode is assigned to probes, and all interfaces are rechecked. The example regression passes.

Built an approximately 502 MB full test ZIP and extracted it into `.qprint/relocated full environment/Qprint`. Both languages verified successfully using the extracted code; compiler/include paths all pointed inside the new directory. The archive used the existing Conda environment and did not bundle Python. Git ignore checks passed for compilers/Cubical, and local links in 36 Markdown documents passed. No frontend changes were made. See [toolchains](toolchains.en.md) for installation, relocation, and packaging boundaries.

## 2026-09-20: unified formal verification adapters

Added Lean / Agda adapters, unified stage reports, CLI, opt-in background API, project configuration, process timeouts, and bounded returned logs. Author progress remains separate; Coq explicitly returns unsupported.

Executed:

```powershell
.\.conda\python.exe -m pytest -q --basetemp .qprint/tests-verification-final --tb=short
.\.conda\python.exe -m qprint verify --workspace examples/demo --language agda
```

Python results: **85 passed, 2 skipped, 2 warnings**, 1.73 seconds. New coverage includes command/probe construction, failed-stage short circuiting, valid lines with nonexistent declarations, missing tools, timeouts, bounded logs, configuration/path restrictions, probe injection, source changes, API token/Origin/enablement/queues, CLI exit codes, and unchanged author progress. The two dependency deprecations match the historical record.

The local Conda environment has no `lake`, `lean`, or `agda`; two real-toolchain tests skipped. This run does not establish compilation of real Lean/Agda projects. CLI smoke correctly returned `incomplete` / `unavailable`, exit 1. Verification reports now use ASCII JSON escapes to avoid Windows Conda capture encoding failures; decoded names and diagnostics are unchanged. There were no frontend changes or browser acceptance checks in this extension. See [formal verification](formal-verification.en.md) for capabilities and limitations.

## 2026-09-20: blueprint granularity extension

The [blueprint granularity guide](../blueprint分级指南.md) was implemented with node / Milestone / project levels and all / current-project scope. No grouping fields were added to the stored node format; groups derive from index Markdown and directories.

Automated checks:

```powershell
.\.conda\python.exe -m pytest -q --basetemp .qprint/tests-granularity-final --tb=short
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
.\.conda\python.exe -m pytest -q --basetemp .qprint/tests-final --tb=short
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

`.\.conda\python.exe tools/smoke_imports.py` downloaded into `.qprint/network-smoke-*`, without changing demo content.

| Source | Result |
| --- | --- |
| GitHub `CMU-HoTT/serre-finiteness` | Resolved `main`, imported 40 files, preserved directories and provenance |
| arXiv `1603.04246` | Retrieved PDF and 3 source files as paired paper resources |

These checks verified actual endpoints and archive handling, not universal source availability or compilation of imported code. Results were also recorded in `.qprint/network-smoke.json`.

## Startup and limits

`start.ps1` started the service, and page availability was checked in a new process. The demo index contained 10 nodes, 12 relations, and 1 paper, with no diagnostics.

TeX rendering uses a separate parser process and preserves source after an eight-second timeout. Common paragraphs, theorems, sections, lists, and mathematics are supported. Complex packages, images, cross-file input, and multiline macros remain initial-version limits. Large-graph performance was not benchmarked; browser records concern the 10-node demo. No Lean/Agda/Coq compiler was run; progress is author-assigned. Follow-up goals are described in the specification and [TODO](../TODO.en.md).
