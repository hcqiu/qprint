# Qprint

[中文](README.md) | [English](README.en.md)

A Markdown-centered mathematical knowledge graph and proof navigation IDE. Blueprint nodes connect TeX papers with Lean / Agda / Coq code. Material remains in ordinary files that can be managed with Obsidian or any editor.

The current package version is `0.1.0`. Documentation describes implemented behavior; future work is listed separately in TODO.

**License: free for noncommercial use; commercial use requires separate written authorization.** Personal noncommercial learning, nonprofit education, and academic research are eligible; internal company use, commercial SaaS, commercial product integration, and resale require commercial authorization. Copyright belongs to Haochen Qiu. This is a source-available project. See the [licensing guide](docs/licensing.en.md), [noncommercial license](LICENSE), and [commercial terms](COMMERCIAL-LICENSE.md) for scope and exceptions. Third-party material retains its own licenses.

| Document | Purpose |
| --- | --- |
| [PRODUCT.en.md](PRODUCT.en.md) | Product goals, workflows, and boundaries |
| [ARCHITECTURE.en.md](ARCHITECTURE.en.md) | Module responsibilities, data flows, technical decisions |
| [TODO.en.md](TODO.en.md) | Implemented baseline, follow-up work, acceptance conditions |
| [docs/index.en.md](docs/index.en.md) | Module documents and bilingual navigation |
| [Knowledge Navigator](docs/knowledge-navigator.en.md) | Incremental agent indexes, symbol navigation, dependencies and context tools |
| [docs/spec.en.md](docs/spec.en.md) | Development specification and acceptance contract |
| [docs/verification.en.md](docs/verification.en.md) | Executed verification and known limitations |

## Quick start

For first-time setup, open **Anaconda Prompt / Miniconda Prompt**, change to the Qprint root folder, and run:

```text
conda init powershell
conda env create -p .\.conda -f environment.yml
```

`environment.yml` installs Python 3.12+, Qprint, and development dependencies. After setup, open PowerShell or your agent in the Qprint root and run:

```powershell
.\.conda\python.exe -m qprint serve --workspace examples/demo --port 8765
```

Alternatively, run `.\start.ps1`. Open <http://127.0.0.1:8765>; the server listens locally by default. The script uses the project's `.conda` and reports the setup command if it is missing.

Agents do not run `conda activate`; Conda need not be on PATH and PowerShell profiles need not load. When Conda is available, `conda run -p .\.conda python -m qprint agent state` is equivalent. Commands and paths are relative to the Qprint root. Recreate `.conda` after relocating an installation rather than copying the old environment.

The dependency snapshot is in `requirements-lock.txt`. To reproduce the recorded environment, install it before the project:

```powershell
.\.conda\python.exe -m pip install -r requirements-lock.txt
.\.conda\python.exe -m pip install -e . --no-deps
```

KaTeX JS, CSS, fonts, and license are vendored in `qprint/static/vendor/katex/`. Reading and graphs require no CDN. `.\.conda\python.exe tools/vendor_assets.py` refreshes the pinned assets and verifies npm SHA-512 integrity.

## Use your own workspace

```text
my-math/
  blueprint/Topology/Notes.md
  tex/Topology/Notes.tex
  pdf/Topology/Notes.pdf
  lean/Topology/Notes.lean
  agda/Topology/Notes.agda
  coq/Topology/Notes.v
```

```powershell
.\.conda\python.exe -m qprint serve --workspace my-math
.\.conda\python.exe -m qprint check --workspace my-math
```

Directories may be empty. Library notes need not have paper attachments. Refresh after external edits; the application does not rewrite files in the background.

## Author nodes

A Markdown file may contain multiple nodes. Each level-one heading defines a node. A following `qprint` YAML fence describes bindings, followed by Markdown body content.

````markdown
# My theorem
```qprint
kind: theorem
status: in_progress
tex: Topology/Notes#my-theorem
uses:
  - "[[Topology/Basic#Continuous]]"
inspired_by: []
lean:
  - declaration: MyNamespace.my_theorem
    file: Topology/Notes.lean
    lines: [10, 18]
agda: []
coq: []
```
Describe the theorem with mathematics $f : X \to Y$ and [[Topology/Basic#Continuous|continuity]] links.
````

The node address is `Topology/Notes#My theorem`. Links support `[[#Heading in this file]]` and unique `[[Filename#Heading]]` targets. Use full vault paths for duplicate filenames. Quote wikilinks in YAML.

- `kind`: `definition`, `lemma`, `theorem`, `conjecture`, `proof`, or `other`.
- `status`: `not_started`, `in_progress`, or `complete`. This is author-assigned progress, not compiler verification.
- `uses` records proof/definition dependencies; `inspired_by` records inspiration.
- Language fields accept multiple bindings. Remote-only bindings may use `declaration` and an HTTPS `url` without downloading a whole library.
- `file` is relative to the language directory. `lines` is one-based and inclusive. Simple declarations can omit line numbers; complex syntax should specify them.
- Lower headings do not create nodes. Do not repeat a level-one heading within a file.

Papers only need location markers, not formalization status or dependency tags:

```tex
\documentclass{article}
\newcommand{\bpnode}[1]{}
\newtheorem{theorem}{Theorem}
\begin{document}
\section{Main result}
\bpnode{my-theorem}
\begin{theorem}
The identity map is continuous.
\end{theorem}
\bpnode{next-node}
The next mathematical object begins here.
\end{document}
```

Place `\bpnode` outside environments and before the bound content. Ordinary paragraphs are supported. A fragment extends to the next marker. A label-only `tex` value infers the TeX file from the blueprint path.

## Navigation and editing

The left tree contains paper sections and blueprint nodes. `/` focuses search. The center switches between reading, TeX, and Markdown. The right panel shows only the current node's code bindings, with language and declaration selection. Both sidebars collapse; narrow layouts place code below content.

The graph focuses on the current node when opened. Click to preview; double-click or press Enter to open content and source; Space previews. Drag, pan, zoom, switch force/layered layouts, filter by kind/progress, or show a one-hop neighborhood. Arrows point from dependencies to their users; dashed edges indicate inspiration.

Graph **granularity** has three levels: Blueprint nodes (level-one headings), Milestones (Markdown files), and projects (indexed directories or fallback directories). Grouping is derived for graph display without new required metadata, file migration, or project configuration.

- Project detection: `<directory-name>.md` or `index.md` is an index, with the named file taking precedence. A file belongs to its nearest indexed ancestor, allowing arbitrary subfolders. Without an indexed ancestor, its immediate parent directory is used. Files directly under blueprint belong to the root group.
- Milestone graphs merge references between each directed file pair. They include prose and metadata wikilinks such as `[[path#heading]]`, `[[path]]`, aliases, and Markdown relative links such as `[text](../Other.md#heading)`. Example code, inline code, HTML comments, and external links are excluded. Node-level `uses` / `inspired_by` retain their original meaning.
- Project graphs merge references between projects, including references in index Markdown. References within the same project create no project self-loop.
- **Scope** manually selects all (the entire `blueprint/`), current project, or current Milestone (one Markdown file). The default is current project, with initial project/file context taken from the reader node. Selectors let you choose a project and its file. Scope is independent of granularity and survives level changes; it remains selectable at project level. Milestone scope shows only that file's nodes and internal edges at node level, the file itself at file level, and its owning project at project level.
- Entering current-Milestone scope automatically selects the file of the graph's current Blueprint node, falling back to the reader node. From project granularity, it expands to that file's Blueprint nodes. Scope changes clear the old neighborhood filter. Users can still select another file afterward.
- Double-clicking a project opens the all-scope Milestone graph and highlights its files in gold. Double-clicking a Milestone opens its project's node graph and highlights all headings in that file. Double-clicking a Blueprint node opens its content and code. Drill-down clears old filters so members remain visible.

Indexes remain ordinary Markdown. Those without headings still appear in file graphs; those with headings also create nodes. Use the index naming convention for files whose arbitrary names cannot otherwise be recognized as indexes. No extra metadata is necessary.

Scrolling again after reaching a content boundary switches to the next/previous node. Footer buttons and Alt+Left/Right navigate within the same paper. URL hashes provide node deep links. Markdown mode edits the entire file; Ctrl+S saves. Detected external changes produce a conflict rather than a silent overwrite.

## Import material

The UI and CLI share a downloader. GitHub input is a repository root URL; branch/tag/SHA is a separate argument. The default branch is discovered automatically.

```powershell
.\.conda\python.exe -m qprint import-code https://github.com/CMU-HoTT/serre-finiteness --language agda --dest serre-finiteness --workspace my-math
.\.conda\python.exe -m qprint import-paper 1603.04246 --dest Geometry --name Via16SpherePacking --workspace my-math
```

The PDF is saved to `pdf/Geometry/Via16SpherePacking.pdf`, with multi-file source under `tex/Geometry/Via16SpherePacking/`, retaining internal paths. The downloader does not insert blueprint markers. Create Markdown and bind nodes to actual source paths afterward.

Existing destinations are not overwritten. Limits are 100 MiB per download and 300 MiB / 10,000 archive entries when extracting. Traversal and link files are rejected. Each imported directory includes `.qprint-source.json` provenance. Missing source, network failures, and exceeded limits produce errors. Background job records last only for the current server process. GitHub imports verify after download by default, preparing pinned environments and executing project checks. Uncheck the UI option or use `--no-verify-after-download` to opt out. Failed checks preserve sources and reports.

## Tests and development

```powershell
.\.conda\python.exe -m pytest -q
node --test tests/graph_view.test.mjs
.\.conda\python.exe -m qprint check --workspace examples/demo
```

If Windows restricts pytest's system temporary directory, use a new test-only workspace directory:

```powershell
New-Item -ItemType Directory .qprint -Force
.\.conda\python.exe -m pytest -q --basetemp .qprint/test-local
```

pytest cleans its `--basetemp` directory; only use a dedicated test directory.

Main modules: `blueprint.py` parses nodes, `workspace.py` builds indexes, `tex.py` extracts fragments and adapts plasTeX DOM, `formal.py` locates code, `importers.py` imports resources, `server.py` exposes APIs, and `static/` contains the frontend. Runtime OpenAPI schema is at `/openapi.json`.

## Current limits

plasTeX rendering supports common paper structures and mathematics but does not replace full LaTeX typesetting. Cross-file `\input`, external images, and complex packages can fall back to source with warnings; multiline macros need further work. Qprint can explicitly install managed Lean/Agda toolchains. Coq verification, Lean axiom auditing, and LSP remain unimplemented. Demo code illustrates navigation and has not been compiled as complete formalization projects. Bidirectional AI generation and legacy leanblueprint conversion remain future work from the original requirements.

## Formal verification

For an independent project, use `.\.conda\python.exe -m qprint formal verify --project PROJECT --language agda --timeout 600`; all modules are selected by default. Native resolution, automatic installation, timestamped reports and the version helper skill are documented in [project resolution](docs/formal-resolution.en.md).

Since 2026-09-21, compilers/libraries live in gitignored `toolchains/` and `packages/` under Qprint. Projects prefer native configuration, with `.qprint-formal.yaml` filling missing Agda pins. See [managed toolchains](docs/toolchains.en.md) for commands and light/full ZIP packaging. A real verification example is provided:

```powershell
.\.conda\python.exe -m qprint toolchain list
.\.conda\python.exe -m qprint verify --workspace examples/verification
```

Full ZIPs include the specified formal environment; an existing Python/Conda environment is still required.

The [unified adapter layer](docs/formal-verification.en.md) provides Lean builds/declaration checks and Agda typechecking/name resolution. Coq explicitly returns unsupported. Explicit verification acquires supported missing exact versions unless `--offline` is selected:

```powershell
.\.conda\python.exe -m qprint verify --workspace my-math --language lean
```

Optional flags include `--node "path#heading"` and `--timeout 180`. JSON results remain separate from author `status`. HTTP uses `POST /api/verify`, enabled through `serve --allow-verification` for trusted workspaces. Reading and saving never trigger verification; GitHub imports verify by default. Agda defaults to `safe: inherit`, preserving upstream OPTIONS; use `formal audit` for explicit safety requirements. See [automatic recovery and helper boundaries](docs/formal-resolution.en.md).
