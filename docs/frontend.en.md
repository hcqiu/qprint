# Browser frontend module

[中文](frontend.md) | [English](frontend.en.md) · [Documentation](index.en.md)

Entry files: [index.html](../qprint/static/index.html), [style.css](../qprint/static/style.css), [app.js](../qprint/static/app.js). Graph files: [graph-view.js](../qprint/static/graph-view.js), [graph.js](../qprint/static/graph.js). The frontend uses native ES modules and SVG without an npm build step.

## Page and controls

Folders and files in the directory tree start collapsed. Expansion is saved locally by library name and full path, surviving node selection, search, index refresh, and page reload. Collapsing a parent retains its children's expansion preferences. If browser storage is unavailable, preferences remain in memory for the current page.

The left panel contains Blueprint folders, files, nodes, and search, without paper outlines or group headings. The center displays node content, TeX, or a whole-file Markdown editor. The right panel provides language/declaration selection and code. Sidebars collapse; narrow layouts move code below the main content. Diagnostics, rendering warnings, and lookup errors are presented separately.

| Action | Behavior |
| --- | --- |
| `/` | Focus search outside input controls; search node titles, paths, and bodies |
| Alt + Left/Right | Visit the previous/next bound node in the same paper |
| Ctrl/Cmd + S | Save the entire file in Markdown edit mode |
| Ctrl/Cmd + C / context-menu Copy | Copy a selection in the node reader or TeX view with node context; preserve the selected text verbatim |
| Scroll again after reaching a content boundary | Switch adjacent nodes with delay/cooldown; disabled in edit mode |
| Graph click / Space | Preview an object |
| Graph double-click / Enter | Open a node or drill down at the current level |
| Graph drag / Wheel | Move nodes, pan the canvas, or zoom |

Boundary scrolling applies only to the content panel; buttons and keyboard alternatives remain available. The URL uses `#node=<encoded node ID>` for deep links and browser history. Renaming files or headings affects existing links.

## State and requests

`app.js` maintains project data, current details, reader selection, view/mode, code binding selection, the edit document, dirty state, and scroll boundaries. Node requests carry increasing sequence numbers so stale responses cannot replace a later selection.

Reading `/api/project` stores the session token; writes include `x-qprint-token`. Refresh preserves an existing selected node or falls back to an available target. Markdown saves send the revision captured when loading the source. A 409 conflict displays an error for the user to reload and merge.

Leaving a node with unsaved changes prompts for confirmation. Closing the page uses `beforeunload`. There is no autosave, automatic conflict merge, or persistent browser draft storage.

## Clipboard context

`clipboard-context.js` handles native `copy` events in the node reader. Level 0 includes the complete current node TeX, direct dependency names and descriptions, and a short instruction to use Knowledge Navigator if more context is needed. `User question:` comes last, followed by the unchanged browser selection: no formula reconstruction or whitespace rewriting. Markdown editors, search fields, code panels, graph views, and unbound whole-paper views retain ordinary copying.

The backend prebuilds in-memory Context Bundles on workspace load and every reload (including save/import). Node detail includes `copy_context`, so the browser has it before displaying the node. Copy writes synchronously, without fetching, waiting, or querying Navigator. Bundles are replaced with node details; missing context falls back to ordinary copying.

Direct Markdown and TeX `uses` are merged and deduplicated. Level 0 includes no dependency TeX or recursive expansion: at most 20 dependencies, descriptions up to 600 characters, and 8,000 characters total across dependency IDs, titles and descriptions. Inspired-by links are not proof dependencies. Omissions, unresolved references and missing TeX are explicitly marked. Use existing Navigator `resolve`, `open` and `source` commands for Level 1 descriptions and Level 2 source expansion.

## Graph responsibilities

Entering the graph from the reader switches to node granularity, follows the reading node's project and Milestone, and clears kind, status, and neighborhood filters. The node is selected, highlighted, centered, and previewed just like a single click. Centering follows force-layout motion until the user pans, zooms, or selects a node.

`graph-view.js` has no DOM dependency and manages granularity, project scope, focus, and member highlighting. `app.js` passes projected and filtered data to the graph and handles previews, drill-down, and reader navigation. `graph.js` owns force/layered layouts, SVG nodes and edges, label hit regions, and keyboard/mouse interactions.

Drill-down highlighting is independent of reader selection. Scope always allows all, current project, or current Milestone; Milestone scope shows a file selector, while kind filtering is enabled only at node level. Labels retain a minimum display size while zooming, with larger hit regions. Controls are laid out separately from the canvas. See the [graph module](graph.en.md) for grouping rules.

## Rendering and verification boundaries

The reader supports AMS math environments, table rows/columns/borders, theorem names/numbers, and same-node or cross-node `\Cref` / `\cref` navigation. Large-paper indexing retains counter structure instead of falling back to label names when the full text exceeds the rendering limit. Labels containing underscores are read literally. `comment` environments are excluded from content, annotations and reference indexing. Simple `\def` math aliases are translated to bounded macros; empty array intercolumn spacing and fixed-width boxes in arrow labels receive web-layout approximations.

Bibliographies support AMSRefs `bibdiv` / `biblist` / `\bib` BBL records as well as BibTeX `thebibliography`. Author, title, publication metadata, math and links are preserved. Explicit `label` fields are honored; otherwise the web reader numbers entries in BBL order, consistently across citations and the References page.

Formal Blueprint `\lean{...}` annotations are hidden in the LaTeX reading view; the original TeX and code bindings remain available. `\source{...}` displays `Source: ...` and reuses citation navigation when a parsed bibliography is available. Consecutive `\dcref{...}` annotations form a numbered list starting at 1, displaying source coordinates such as sections, theorems and pages, preserving text styles and math in its argument. These commands do not produce layout warnings, even when the print preamble defines them as empty macros.

`\includegraphics` supports PDF, PNG, JPEG, WebP and GIF (first frame) inside the workspace `tex/` directory, relative to the source file and `\graphicspath`. PDFs show page 1 unless `page=N` is supplied. `tikzpicture`, `tikzcd`, and display-math XY-pic `\xymatrix` / AMSCD diagrams compile independently; images, captions and labels retain their positions. Exchange diagrams include their enclosing formula so arrows, labels and surrounding operations stay together. Images are rasterized to PNG under `.qprint/cache/tex-media/`. A failed graphic shows an expandable source and diagnostic without replacing the surrounding text. Normal reading uses cached TeX packages only and does not download them.

The Conda environment includes Tectonic; Python dependencies include Pillow and pypdfium2. Update existing environments with `conda env update -p .\.conda -f environment.yml`. Warm a paper's graphics from the Qprint root before first use (this downloads required TeX packages):

```powershell
.\.conda\python.exe -m qprint.tex_media --workspace examples/demo --paper Topology/KPT25TwoStabilizations/main.tex
```

TikZ uses a restricted standalone preamble with needed simple command definitions and TikZ libraries. Arbitrary file access, dynamic TeX definitions and nested external images are unsupported. Normal compilation has a 30-second timeout. Reload the workspace after editing images or graphics to generate fresh cache entries. Existing `\uses`, `\bpnode` and reference navigation is preserved.

The backend renders Markdown with raw HTML disabled and uses a controlled TeX adapter. The frontend escapes ordinary text. KaTeX and auto-render use local assets and `trust: false`. Static assets come from the same server; ordinary reading requires no CDN.

Pure state regressions run with `node --test tests/graph_view.test.mjs`. Browser acceptance is recorded in [verification](verification.en.md) but is not automated end-to-end coverage. Layout, focus, and dragging still require browser checks. The current UI is primarily Chinese; bilingual documentation does not imply application localization.
