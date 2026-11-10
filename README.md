# Qprint

[English](README.md) | [中文](README.zh.md)

A mathematical knowledge graph and formalized proof navigation IDE. Blueprint nodes connect TeX papers with Lean / Agda / Coq code. Node content is stored in Markdown files that you can manage directly in Obsidian or any other editor.

1. Organize a visual knowledge graph at three levels—projects, milestones, and blueprint nodes (such as definitions, theorems, and conjectures)—for quick navigation by humans and AI.
2. Automatically import LaTeX from arXiv or GitHub and build a knowledge graph that includes all dependencies across papers.
3. Copy text from a page with node information and prompts automatically appended. Paste it into an agent so it can use skills to explore, conduct research, and answer questions.
4. Automatically type-check formalized code imported from GitHub, with natural language and formalized code shown side by side.

**License: free for noncommercial use; commercial use requires separate written authorization.** Personal noncommercial learning, nonprofit education, and academic research are free of charge. Internal company use, commercial SaaS, integration into commercial products, resale, and similar uses require commercial authorization. The copyright holder is Haochen Qiu. This is a source-available project. See the [licensing guide](docs/licensing.en.md), [noncommercial license](LICENSE), and [commercial terms](COMMERCIAL-LICENSE.md) for scope and exceptions. Third-party material retains its own licenses.

| Document | Purpose |
| --- | --- |
| [PRODUCT.en.md](PRODUCT.en.md) | Product goals, workflows, and boundaries |
| [ARCHITECTURE.en.md](ARCHITECTURE.en.md) | Module responsibilities, data flows, and technical decisions |
| [TODO.en.md](TODO.en.md) | Completed baseline, future work, and acceptance criteria |
| [docs/index.en.md](docs/index.en.md) | Module documentation and bilingual navigation |
| [Knowledge Navigator](docs/knowledge-navigator.en.md) | Incremental indexing, symbol navigation, dependency and context tools for agents |
| [docs/spec.en.md](docs/spec.en.md) | Development specification and acceptance contract |
| [docs/verification.en.md](docs/verification.en.md) | Completed verification and known limitations |

## Quick start

For first-time setup, open **Anaconda Prompt / Miniconda Prompt**, change to the Qprint root folder, and run:

```text
conda init powershell
conda env create -p .\.conda -f environment.yml
```

`environment.yml` installs Python 3.12+, Qprint, and its development dependencies. After setup, open PowerShell or an agent in the Qprint root folder and run:

```powershell
.\.conda\python.exe -m qprint serve --workspace examples/demo --port 8765
```

You can also run `.\start.ps1`. Open <http://127.0.0.1:8765>; the server listens only on the local machine by default. The script uses the project's `.conda` environment and shows the first-time setup commands if it is missing.

On Windows, double-click `start-qprint.bat` in a workspace directory to start Qprint. `serve` adds this script to the workspace if it is missing. You can also copy `qprint/start-qprint.bat` into the workspace or generate it with `.\.conda\python.exe -m qprint launcher --workspace my-math`. The workspace must be inside the Qprint root folder. The script uses the root folder's `.conda` environment without requiring activation.

If the same workspace is already running through the script or `serve`, the launcher prints the existing URL without starting a second server. The first double-click launch tries port 8765 and selects an available port if it is occupied; use the URL printed in the console. Keep the first console window open to keep the server running, and press Ctrl+C to stop it. Press any key to close a window opened by a repeated launch. Existing scripts are not overwritten.

Agents do not run `conda activate`, and neither Conda on PATH nor a loaded PowerShell profile is required. If Conda is available, `conda run -p .\.conda python -m qprint agent state` is an equivalent invocation. All commands and paths are relative to the Qprint root folder. When moving an installation, recreate `.conda` at the new location rather than copying the old environment.

The dependency version snapshot is in `requirements-lock.txt`. To reproduce the current test environment, install it before installing the project:

```powershell
.\.conda\python.exe -m pip install -r requirements-lock.txt
.\.conda\python.exe -m pip install -e . --no-deps
```

KaTeX JavaScript, CSS, fonts, and its license are bundled in `qprint/static/vendor/katex/`, so reading and graph views do not depend on a CDN. Run `.\.conda\python.exe tools/vendor_assets.py` to fetch the pinned assets again; the script verifies the SHA-512 integrity value provided by npm.

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

Directories may be empty, and standard library nodes do not need paper attachments. Click Refresh after modifying files externally; the application does not rewrite files in the background.

For existing LaTeX Blueprint and Lean projects, use the [Formal Blueprint Project to QPrint](docs/formal-blueprint-project-to-qprint.md) converter (documentation in Chinese). Provide the source project location and an output folder name. The converter preserves labels, dependencies, and existing descriptions, and generates source bindings from `\lean` commands.

## Author nodes

A Markdown file can contain multiple nodes. Each level-one heading defines a node. A `qprint` YAML fence below the heading describes its bindings, and the remaining content forms the Markdown body.

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
Write the theorem's description, mathematics such as $f : X \to Y$, and links such as [[Topology/Basic#Continuous|continuity]] here.
````

The node address is `Topology/Notes#My theorem`. Links support `[[#Heading in this file]]` and unambiguous `[[Filename#Heading]]` targets. For duplicate filenames, use the full vault path. Wikilinks in YAML must be quoted.

- `kind`: `definition`, `lemma`, `theorem`, `conjecture`, `proof`, or `other`.
- `status`: `not_started`, `in_progress`, or `complete`. This records the author's progress, not the result of a compiler check.
- `uses` records dependencies of a proof or definition; `inspired_by` records sources of inspiration.
- Language fields support multiple bindings. Bindings to remote code can use `declaration` with an HTTPS `url`, without downloading an entire standard library.
- `file` is relative to the language directory; `lines` is a one-based, inclusive range. Simple declarations can omit line numbers; specifying them is recommended for complex syntax.
- Level-two headings do not create new nodes. Do not repeat a level-one heading within the same file.

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

Place `\bpnode` outside the environment, before the content it identifies. It can also mark ordinary paragraphs without a theorem environment. A node displays the content up to the next marker. When `tex` contains only a label, the TeX file is matched automatically using the blueprint path.

## Navigation and editing

The left tree shows only blueprint folders, files, and nodes, without grouping headings. `/` focuses search. The center panel switches between reading, TeX, and Markdown modes. The right panel shows only code bound to the current node, with controls for selecting a language and declaration. Both sidebars can be collapsed; on narrow screens, the code panel appears below the main content.

Click Knowledge Graph to focus on the current node. Click a node to view its description, double-click or press Enter to open its content and source code, or press Space to preview it. The graph supports dragging, panning, zooming, force-directed and layered layouts, type and progress filters, and one-hop neighborhoods. Arrows point from a dependency to the node that uses it; dashed edges indicate inspiration.

The graph supports three levels of **granularity**: Blueprint nodes (level-one headings), Milestones (Markdown files), and projects (directories containing index files, or fallback directories). These levels are used only to aggregate the graph; they require no new node fields, file moves, or additional project configuration.

- Project detection: a directory's `<directory-name>.md` or `index.md` serves as its index, with the matching directory name taking precedence. A file belongs to its nearest ancestor directory with an index, so projects can contain arbitrary subfolders. If no such index exists, the file belongs to its immediate parent directory. Files directly under `blueprint/` belong to the blueprint root group.
- The Milestone graph merges all references from one file to another into a single edge. It includes wikilinks in body content or node metadata, such as `[[path#heading]]`, `[[path]]`, and links with aliases, as well as relative Markdown links such as `[text](../Other.md#heading)`. Code examples, inline code, HTML comments, and external web links are excluded from aggregation. The existing heading-level semantics of `uses` / `inspired_by` remain unchanged.
- The project graph further merges file references across projects, including project dependencies in index Markdown files. References within the same project do not create project self-loops.
- **Scope** can be set manually to All (the entire `blueprint/`), Current Project, or Current Milestone (a single Markdown file). Current Project is the default, with the initial project and Milestone taken from the node being read. Use the dropdowns to select a project and one of its files. Scope is independent of granularity: changing granularity preserves the scope, which can also be selected at project level. Milestone scope shows only the file's nodes and internal edges at node level, the file itself at file level, and its owning project at project level.
- Switching to Current Milestone automatically selects the file containing the graph's selected Blueprint node, or the node being read if there is no graph selection. If the graph was at project granularity, it expands to show that file's Blueprint nodes. Changing scope clears the previous neighborhood filter. You can still select another file manually afterward.
- Double-clicking a project opens the Milestone graph with All scope and highlights every file in that project with a gold outline. Double-clicking a Milestone opens its project's Blueprint node graph and highlights every level-one heading in that file. Double-clicking a Blueprint node then opens its content and code. Drilling down clears previous filters so that all members remain visible.

Indexes remain ordinary Markdown files. They appear in the file graph even without level-one headings; if they contain level-one headings, nodes are parsed using the usual rules. For index files with arbitrary names that cannot be recognized from the filename, use the naming convention above. No metadata is needed.

After scrolling to the bottom of the content, scroll down again to switch to the next node; scrolling up works in reverse. Use the footer buttons or Alt+Left/Right to navigate within the same paper. URL hashes provide direct links to nodes. Markdown mode edits the entire file, and Ctrl+S saves it. External file changes trigger a conflict warning to prevent silent overwrites.

## Import material

Import Material in the UI and the following CLI commands use the same downloader. For GitHub, provide a repository root URL and pass the branch, tag, or SHA separately. The default branch is detected automatically.

```powershell
.\.conda\python.exe -m qprint import-code https://github.com/CMU-HoTT/serre-finiteness --language agda --dest serre-finiteness --workspace my-math
.\.conda\python.exe -m qprint import-paper 1603.04246 --dest Geometry --name Via16SpherePacking --workspace my-math
```

The paper PDF is saved as `pdf/Geometry/Via16SpherePacking.pdf`, and multi-file source is stored under `tex/Geometry/Via16SpherePacking/`, preserving internal relative paths. The downloader does not add blueprint markers to papers. After importing, create a Markdown file with the same name as needed, and bind its nodes using the actual source paths.

Existing destinations are not overwritten. Downloads are limited to 100 MiB; extraction is limited to 300 MiB and 10,000 archive entries. Path traversal and link files are rejected. Each imported directory contains `.qprint-source.json` to record its origin. Missing source, network failures, and exceeded limits produce errors. Background job records exist only in the current server process and are cleared on restart. GitHub imports enable Verify After Download by default, preparing an environment with pinned versions and running project checks. Clear the checkbox in the UI or pass `--no-verify-after-download` to disable this step. Failed verification preserves both source files and reports.

## Tests and development

```powershell
.\.conda\python.exe -m pytest -q
node --test tests/graph_view.test.mjs
.\.conda\python.exe -m qprint check --workspace examples/demo
```

If a restricted Windows environment cannot access pytest's system temporary directory, use a new temporary directory inside the project:

```powershell
New-Item -ItemType Directory .qprint -Force
.\.conda\python.exe -m pytest -q --basetemp .qprint/test-local
```

pytest cleans its `--basetemp` directory, so always specify a directory dedicated to tests.

Main modules: `blueprint.py` parses nodes, `workspace.py` builds indexes, `tex.py` parses fragments and adapts the plasTeX DOM, `formal.py` locates code, `importers.py` imports resources, `server.py` provides the API, and `static/` contains the frontend, which requires no build step. The API's OpenAPI schema is available at `/openapi.json` on a running server.

## Formal verification

For a standalone project, run `.\.conda\python.exe -m qprint formal verify --project PROJECT --language agda --timeout 600`. All modules are checked by default. See [project resolution](docs/formal-resolution.en.md) for native configuration resolution, automatic installation, timestamped error reports, and the version repair skill.

Since 2026-09-21, compilers and libraries have been installed in `toolchains/` and `packages/` under the Qprint root folder; both directories are ignored by Git. Subprojects use their native configuration first, with `.qprint-formal.yaml` supplementing the Agda version. See [managed toolchains](docs/toolchains.en.md) for management commands and light/full ZIP packaging. A separate example for real verification is provided:

```powershell
.\.conda\python.exe -m qprint toolchain list
.\.conda\python.exe -m qprint verify --workspace examples/verification
```

Full ZIP packages include the specified formalization environment, but still require an existing Python/Conda environment.

The [unified formal verification adapter layer](docs/formal-verification.en.md) provides Lean builds and declaration existence checks, plus Agda type checking and declaration resolution. Coq explicitly returns an unsupported result. Explicit verification automatically installs missing supported pinned versions; `--offline` disables downloads. For example:

```powershell
.\.conda\python.exe -m qprint verify --workspace my-math --language lean
```

Optional flags include `--node "path#heading"` and `--timeout 180`. Verification produces a separate JSON report without rewriting the author's `status`. The HTTP endpoint is `POST /api/verify`; enable execution for trusted workspaces with `serve --allow-verification`. Reading and saving do not trigger verification automatically; GitHub imports enable Verify After Download by default. Agda defaults to `safe: inherit`, respecting upstream OPTIONS; safety audits require an explicit `formal audit`. See [project resolution](docs/formal-resolution.en.md) for automatic recovery and the two helpers with restricted capabilities.

## Current limits

plasTeX rendering supports common paper structures and mathematical formulas, but does not replace full LaTeX typesetting. Cross-file `\input`, external images, and complex packages within fragments fall back to TeX source with a warning; multiline macro definitions need further support. Lean and Agda can be installed through the repository's toolchain manager. Coq verification, Lean axiom auditing, and LSP are not yet implemented. The example code demonstrates navigation and has not been compiled as complete formalization projects. Bidirectional AI generation and the legacy leanblueprint converter remain future work under the original requirements.
