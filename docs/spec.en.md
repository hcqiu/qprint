# Qprint v1 development specification

[中文](spec.md) | [English](spec.en.md) · [Documentation](index.en.md)

Here, v1 denotes the initial product scope; the current Python package version is `0.1.0`. Implementation details are in the module documentation. Future work is tracked in [TODO](../TODO.en.md).

Status: the initial version is implemented; results are in [verification](verification.en.md). Source: [functional requirements](../Qprint功能需求.md), in Chinese. Initial date: 2026-09-18.

## 1. Goals and boundaries

Qprint is a local mathematical knowledge base and proof navigation IDE centered on Markdown blueprints. TeX and Lean / Agda / Coq code are optional node attachments. A node remains valid without either. The initial delivery includes a runnable Python service, browser UI, CLI, demo, and automated tests. It supports browsing, location, editing original Markdown, rebuilding indexes, and importing material. Reading never executes downloaded code. GitHub imports default to post-download verification, with an opt-out. Explicit verification is specified in section 9.

The stack uses Python 3.12, FastAPI, plasTeX, native ES modules, and SVG. It draws on leanblueprint's paper-reading structure and plasTeX approach without forking its Lean-specific data model. Force-directed interaction and traditional layered graphs are implemented locally without embedding an entire note application. Data stays on disk without a database.

Bidirectional AI generation, automatic legacy leanblueprint migration (commented out in the original request), LSP, Coq verification, and multi-user collaboration remain future scope. The 2026-09-20 extension adds explicit Lean / Agda checks (section 9). `complete` remains author-assigned and independent of verification.

## 2. Workspace and data contract

Workspace directories are `blueprint/`, `tex/`, `pdf/`, `lean/`, `agda/`, and `coq/`. Matching blueprint/TeX paths and basenames support paper bindings; library notes without TeX are valid. Multi-file imports preserve internal directories: PDFs use `pdf/<folder>/<paper>.pdf`, and source uses `tex/<folder>/<paper>/`, preserving relative `\input` paths on disk.

Each Markdown level-one heading defines a node. Lower headings belong to its body, and fenced-code headings do not create nodes. Node IDs combine the case-sensitive vault-relative path without `.md`, `#`, and the original heading. Headings cannot contain `#`, `|`, or `]]`; duplicates in one file are errors. File frontmatter may contain ordinary Obsidian properties but is not node metadata.

A `qprint` fence immediately after the heading stores YAML metadata, remaining ordinary Markdown readable in Obsidian:

````markdown
# continuous_id
```qprint
kind: theorem
status: complete
tex: Topology/Example#continuous-id
uses:
  - "[[Topology/Basic#Continuous]]"
inspired_by: []
lean:
  - declaration: continuous_id
    file: Topology/Example.lean
    lines: [4, 5]
agda: []
coq: []
```
The identity map is continuous. Ordinary Markdown, mathematics, and [[Topology/Basic#Continuous|continuous maps]] are supported.
````

| Field | Contract |
| --- | --- |
| kind | definition / lemma / theorem / conjecture / proof / other; default other |
| status | not_started / in_progress / complete; default not_started |
| tex | Relative TeX path (optional .tex) plus #bpnode-label; label alone infers the matching paper path |
| uses / inspired_by | Arrays of wikilink strings; dependencies and inspiration remain distinct edges |
| lean / agda / coq | Zero or more bindings; module.declaration shorthand is allowed; full bindings contain declaration and optional file, lines, url |
| file / lines | Relative to the language directory; one-based inclusive lines; explicit ranges resolve ambiguity |
| url | HTTPS source link; remote-only bindings show a link without automatic fetching |

Links support full vault paths, unique basenames, `[[#Heading in this file]]`, and aliases. Missing/ambiguous targets produce diagnostics without guessing. Prose links navigate but do not automatically become `uses`. Duplicate nodes, invalid YAML or fields, missing TeX labels, and similar failures appear in diagnostics rather than crashing the whole workspace.

## 3. TeX and formal code

Use `\bpnode{label}` for location only, without requiring `\leanok` or `\uses`. Place it before the bound content and outside environments; ordinary paragraphs also work. `\node{label}` remains a legacy alias. Labels are unique within each TeX file; comments and verbatim/lstlisting/minted examples do not create anchors.

A reading fragment starts after its anchor and ends before the next anchor. The preamble before the first node and trailing `\end{document}` are excluded. Only bound nodes participate in sequential navigation. The tree retains all TeX files, including unbound ones, and chapter/section/subsection/subsubsection levels. Section selection locates its first subsequent bound node or displays source when none exists.

plasTeX parses a DOM which a controlled adapter converts into paragraphs, headings, theorems, lists, emphasis, references, and mathematics. Local KaTeX renders math in the browser. Supported single-line macro and theorem definitions are retained from the preamble. External execution and file reads are not permitted. Unsupported complex macros, images, and cross-file `\input` produce warnings and allow original source inspection. The initial version is not a full typesetting engine and does not promise compatibility with all arXiv packages. TeX source remains accessible.

Code lookup returns explicitly bound lines or attempts language-specific declaration boundaries: Lean namespaces, Agda top-level signatures, and Coq Definition/Theorem declarations, among others. Uncertain or multiple candidates require an explicit message, never a whole file presented as an exact declaration. Module shorthand resolves against language directories. Special syntax and nonstandard library paths can specify `file` / `lines`. Source navigation never installs compilers; explicit installation is specified in section 11.

## 4. User interface

- Header: workspace name, node count, reader/graph switch, refresh, import.
- Collapsible left tree: paper files and sections, Blueprint files/nodes, global node search.
- Center: breadcrumbs, kind/status, Markdown description, dependencies/inspiration, reading/TeX/Markdown modes, previous/next navigation.
- Collapsible right code panel: language and declaration selection, paths/lines/source, unbound and remote-code empty states.
- Graph: dark force layout with node dragging, panning, zooming, and neighbor highlighting, plus a directed layered layout. Dependencies point from prerequisites to users; inspiration is dashed. Kind/status and whole-graph/one-hop filtering are available. Entering the graph focuses on the reader node. Click previews; double-click or Open Node locates prose and code. Cycles remain displayable.
- Boundary scrolling: move to the next node only on another downward scroll after reaching the content bottom, and conversely at the top. Short content first activates the boundary; cooldown prevents inertial skipping. Buttons and Alt+arrow keys remain alternatives.
- Refresh preserves an existing selected node. URL hashes support deep links and browser history. Empty workspaces, missing papers, and parse errors have usable states.
- Editing saves the whole Markdown file with its original SHA-256 revision. Detected conflicts return 409; validation precedes replacement. Temporary-file replacement and revision checks protect against detected external edits without converting files into a database. This is not a cross-process file lock; see the workspace module for its precise boundaries.

## 5. Downloaders

CLI and UI share two downloaders. Background jobs expose queued / running / succeeded / failed states, processed serially and polled by the browser. Timeouts, HTTP failures, and invalid content become concrete errors. Users initiate retries.

1. Code: accept public GitHub repository URLs, with branch/tag/SHA separately. Resolve the default branch if omitted. Preserve source, licenses, and configuration under `<language>/<destination>`, recording origin, ref, and time. Never execute repository content.
2. Papers: accept modern/legacy arXiv IDs and abs/pdf URLs, optionally versioned. Receive destination and basename. Fetch both PDF and source, recognizing tar/tar.gz, single gzipped TeX, and plain TeX. Missing source or error pages must fail clearly. Preserve archive paths/resources, validate both outputs before publication, clean temporary files on normal failure handling, and record arXiv ID/time.

Do not overwrite existing targets. Limits are 100 MiB per download and 300 MiB / 10,000 entries per archive. Reject traversal, absolute paths, Windows drive/ADS/reserved names, symlinks, hard links, and device files. Allow only fixed GitHub/arXiv download hosts and validate redirects. Writes require the session token and reject supplied cross-origin origins. The default listener is 127.0.0.1, without remote multi-user authentication.

## 6. API and CLI

- GET `/api/project`: nodes, relations, paper outlines, statistics, diagnostics, write token.
- GET `/api/node?id=...`: description, raw/rendered TeX, code bindings, previous/next nodes.
- GET `/api/document?path=...`, PUT `/api/document`: Markdown source and revision-checked saves.
- GET `/api/tex?path=...`: full TeX source and outline.
- POST `/api/reload`: rebuild indexes.
- POST `/api/import`, GET `/api/jobs/{id}`: create imports and inspect results.
- `conda run -n qprint python -m qprint serve --workspace PATH --port 8765`.
- `conda run -n qprint python -m qprint check --workspace PATH`: print diagnostics and exit 1 for errors.
- `conda run -n qprint python -m qprint import-code URL --language agda --dest serre-finiteness [--ref main] --workspace PATH`.
- `conda run -n qprint python -m qprint import-paper ID --dest Topology --name Lin20K3 --workspace PATH`.

The default workspace is `examples/demo`; specifying a path loads only that directory. Python commands use the `qprint` Conda environment. See [API details](server-api.en.md) for payloads and errors.

## 7. Acceptance and delivery

| ID | Acceptance condition | Verification |
| --- | --- | --- |
| A1 | Multiple Markdown nodes, fences, links, diagnostics, cycles | Parser unit tests |
| A2 | TeX boundaries around environments, sections, fake anchor exclusion, DOM math | TeX tests |
| A3 | Zero/multiple bindings, three-language lookup, remote empty states | Code lookup tests |
| A4 | Tree, content/code panels, search, graph, click/double-click, collapse, boundary scrolling | Browser acceptance |
| A5 | Markdown editing, conflicts, index rebuilds | API tests and browser acceptance |
| A6 | Repository/paper formats, failures, overwrite and extraction protections | Mocked network tests, without real paper downloads |
| A7 | Path escape rejection and safe output | Security regression tests |
| A8 | Documented demo startup and reproducible dependency installation | CLI/API smoke checks |

Delivery includes this specification, setup/authoring README, Python package, frontend, local math assets, demo, pytest tests, and verification records. Record measured results and limits; never mark unexecuted checks as passed.

## 8. Graph granularity extension (2026-09-20)

Based on the [blueprint granularity guide](../blueprint分级指南.md), grouping is derived from existing files. It adds no mandatory Project / Milestone storage model, changes no node metadata, and requires no file migration.

1. Three levels: heading nodes, Markdown files (milestones), and project directories. File graphs merge cross-file references including heading links, file links, and relative Markdown links. Project graphs merge cross-project file edges and index references, removing internal self-loops. Node-level uses / inspired_by remain unchanged.
2. Project detection: `<directory-name>.md` takes precedence over `index.md`; use the nearest indexed ancestor, allowing arbitrary subfolders. With none, use the immediate parent directory; root files use the root group. Full directory paths distinguish identical names.
3. Nodes default to current-project scope with optional all scope. Milestones allow both. Projects force all scope and disable the selector. The reader node sets the initial project; users can also choose a project explicitly.
4. Double-click project → all-scope milestone graph with member files highlighted. Double-click file → its project's node graph with every member node highlighted. Double-click node → existing prose/code navigation. Drill-down clears old filters; member highlights use gold outlines and text.
5. Empty files and heading-free indexes appear in file graphs. Index headings still follow normal node rules. Missing/ambiguous file targets are not guessed. Code examples, inline code, HTML comments, and external links do not create aggregate edges. Aggregate progress summarizes members, not verification.
6. `/api/project` adds read-only `graph`: files, projects, file_projects, node_projects, file_edges, project_edges. Saves and refreshes rebuild it.

Additional acceptance covers unindexed fallback, subfolders, nested indexes, cross-project dependencies, deduplication, empty files, project cycles, both drill-down highlights, initial/manual scope, and forced all scope at project level.

## 9. Unified verification extension (2026-09-20)

1. `verification.py` defines adapters, an injectable runner, and stage results. Lean builds the bound module and queries its exact environment name. Agda typechecks and resolves exported names, preserving upstream OPTIONS by default (safe: inherit), with explicit required safety audit and optional Cubical mode. Coq returns `unsupported`.
2. Explicit `verify --workspace PATH [--node ID] [--language LANG] [--timeout SECONDS]` emits JSON. Exit 0 requires every selected binding to pass and no index errors; empty selections do not pass. `check` remains index-only.
3. `POST /api/verify` requires token/Origin protection and `serve --allow-verification`. A separate single worker accepts five queued/running jobs, queried through `/api/jobs/{id}`. Job success means report generation; inspect `result.status` for check success.
4. Version 1 `qprint-verification.json` configures multiple projects, source roots, and Agda include/safe/mode settings within language-directory boundaries. Binding syntax is unchanged; `lines` never establishes declaration existence. Explicit verification acquires supported missing exact versions and never accepts arbitrary command configuration.
5. Separate reports record time, binding, project, policy, source hash, stages, statuses, return codes, and bounded logs. Missing tools, failures, timeouts, unsupported languages, and changed source cannot pass. Never overwrite author progress, reuse cached success, or claim axiom-free proofs or agreement with prose.
6. Timeout defaults to 120 seconds per stage (1–3600 allowed). No shell, closed stdin, hidden Windows windows, attempted process-tree termination on timeout, and probe cleanup on normal exit. Toolchains may execute project code; this is not an OS sandbox.

Acceptance covers stage success/failure, valid lines with nonexistent names, missing tools, timeouts, Coq/empty selections, configuration/path/probe injection, source changes, API enablement/queues, CLI exit codes, and unchanged author progress. Missing real tools must be recorded as skipped. Full contracts are in [formal verification](formal-verification.en.md).

## 10. Design references

- [leanblueprint](https://github.com/PatrickMassot/leanblueprint): plasTeX blueprint approach.
- [Sphere Packing](https://thefundamentaltheor3m.github.io/Sphere-Packing-Lean/blueprint/): section tree and paper reader structure.
- [Sphere Eversion](https://leanprover-community.github.io/sphere-eversion/blueprint/index.html): reader/dependency graph navigation.
- [nodum](https://github.com/nodummd/nodum): interaction reference; its code was not copied.
- [plasTeX package documentation](https://plastex.github.io/plastex/plastex/sec-packages.html): custom commands and DOM.

## 11. Managed formal environment extension (2026-09-21)

Gitignored `toolchains/` and `packages/` under Qprint hold versioned compilers and libraries separately. Existing workspaces are not migrated. Lean's `lean-toolchain` is authoritative; Agda pins compiler/packages in `project.yaml`. Declaration roots are discovered when explicit verification configuration is absent; custom source roots retain the existing configuration.

`ToolchainManager` installs/lists/removes artifacts with streaming download, pinned hashes, bounded/path-safe extraction, version checks, managed Agda data setup, receipts, and atomic publication. `FormalProjectResolver` parses native requirements without downloading; verification uses `ToolchainResolver` and a separate artifact provider to acquire missing exact versions and create `FormalExecutionContext`. System fallback is explicit and version-checked, without parent-environment changes. Reports include inspectable environment versions/origins.

Agda uses an isolated registry while retaining native module/library option scope. Mode and infective library options configure probes, never globally force Cubical mode onto primitives. Author progress remains independent. Initial support is Windows x64 Lean 4.19.0, Agda 2.8.0, and Cubical 0.9; Coq/other platforms remain extensions.

`release-manifest.json` defines light/full ZIPs; full explicitly includes installed ignored artifacts and fails if any are absent. Private caches, imported user repositories, and indiscriminate working-tree copies are excluded. Python runtime bundling is not included. Acceptance covers exact resolution, missing/conflicting/system versions, isolated packages/data, atomic installation failure, removal boundaries, Git ignores, both ZIP flavors, real toolchains, missing declarations, and relocated extraction. See [managed toolchains](toolchains.en.md).


## Download verification automation (2026-09-22)

GitHub post-download verification defaults on across UI, CLI and API through shared import/service modules. Download publication and verification results are separate; failures retain sources. Opt-out performs no checking. Agda inherit/require/off policy is independent of version resolution: preserve upstream OPTIONS by default and never downgrade explicit require. Reports separate scope, typecheck, safe audit and preparation recovery events.

Preparation uses fixed sources, full commits and applicable SHA-256 checks for bounded HTTP/cache/Windows archive recovery. Native Lake can record acquisition of a verified release; no proof compilation result is fabricated. Unresolved non-version cases go to a fresh [runtime helper](../skills/formalization-runtime-helper/SKILL.md) with restricted Python inspect/recover operations. Version cases use the version helper. Host permissions enforce agent scope; the backend does not launch AI. See [module contracts and limits](formal-resolution.en.md).
