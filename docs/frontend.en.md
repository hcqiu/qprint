# Browser frontend module

[中文](frontend.md) | [English](frontend.en.md) · [Documentation](index.en.md)

Entry files: [index.html](../qprint/static/index.html), [style.css](../qprint/static/style.css), [app.js](../qprint/static/app.js). Graph files: [graph-view.js](../qprint/static/graph-view.js), [graph.js](../qprint/static/graph.js). The frontend uses native ES modules and SVG without an npm build step.

## Page and controls

The left panel contains paper outlines, Blueprint nodes, and search. The center displays node content, TeX, or a whole-file Markdown editor. The right panel provides language/declaration selection and code. Sidebars collapse; narrow layouts move code below the main content. Diagnostics, rendering warnings, and lookup errors are presented separately.

| Action | Behavior |
| --- | --- |
| `/` | Focus search outside input controls; search node titles, paths, and bodies |
| Alt + Left/Right | Visit the previous/next bound node in the same paper |
| Ctrl/Cmd + S | Save the entire file in Markdown edit mode |
| Scroll again after reaching a content boundary | Switch adjacent nodes with delay/cooldown; disabled in edit mode |
| Graph click / Space | Preview an object |
| Graph double-click / Enter | Open a node or drill down at the current level |
| Graph drag / Wheel | Move nodes, pan the canvas, or zoom |

Boundary scrolling applies only to the content panel; buttons and keyboard alternatives remain available. The URL uses `#node=<encoded node ID>` for deep links and browser history. Renaming files or headings affects existing links.

## State and requests

`app.js` maintains project data, current details, reader selection, view/mode, code binding selection, the edit document, dirty state, and scroll boundaries. Node requests carry increasing sequence numbers so stale responses cannot replace a later selection.

Reading `/api/project` stores the session token; writes include `x-qprint-token`. Refresh preserves an existing selected node or falls back to an available target. Markdown saves send the revision captured when loading the source. A 409 conflict displays an error for the user to reload and merge.

Leaving a node with unsaved changes prompts for confirmation. Closing the page uses `beforeunload`. There is no autosave, automatic conflict merge, or persistent browser draft storage.

## Graph responsibilities

`graph-view.js` has no DOM dependency and manages granularity, project scope, focus, and member highlighting. `app.js` passes projected and filtered data to the graph and handles previews, drill-down, and reader navigation. `graph.js` owns force/layered layouts, SVG nodes and edges, label hit regions, and keyboard/mouse interactions.

Drill-down highlighting is independent of reader selection. Scope always allows all, current project, or current Milestone; Milestone scope shows a file selector, while kind filtering is enabled only at node level. Labels retain a minimum display size while zooming, with larger hit regions. Controls are laid out separately from the canvas. See the [graph module](graph.en.md) for grouping rules.

## Rendering and verification boundaries

The backend renders Markdown with raw HTML disabled and uses a controlled TeX adapter. The frontend escapes ordinary text. KaTeX and auto-render use local assets and `trust: false`. Static assets come from the same server; ordinary reading requires no CDN.

Pure state regressions run with `node --test tests/graph_view.test.mjs`. Browser acceptance is recorded in [verification](verification.en.md) but is not automated end-to-end coverage. Layout, focus, and dragging still require browser checks. The current UI is primarily Chinese; bilingual documentation does not imply application localization.
