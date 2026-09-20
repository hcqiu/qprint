# TeX location and rendering module

[中文](tex-rendering.md) | [English](tex-rendering.en.md) · [Documentation](index.en.md)

Implementation: [tex.py](../qprint/tex.py), [_tex_worker.py](../qprint/_tex_worker.py). Tests: [test_tex_formal.py](../tests/test_tex_formal.py).

## Authoring and binding

```tex
\documentclass{article}
\newcommand{\bpnode}[1]{}
\newtheorem{theorem}{Theorem}
\begin{document}
\section{Continuity}
\bpnode{identity-map}
\begin{theorem}
The identity map is continuous.
\end{theorem}
\bpnode{next-result}
The next fragment begins here.
\end{document}
```

Place markers before content and outside theorem or other environments. `tex: Topology/Notes#identity-map` binds a label in `tex/Topology/Notes.tex`. For `blueprint/Topology/Notes.md`, it may be shortened to `tex: identity-map`. The legacy spelling `\node{label}` is also recognized.

## Indexes and fragments

`TexDocument(path, source)` exposes `preamble`, `anchors`, `sections`, and `diagnostics`. Scanning masks comments, verbatim/lstlisting/minted environments, and `\verb` content while preserving offsets and line numbers. Anchors before the document body are excluded.

Labels must be unique within a file. `fragment(label)` returns content after that marker and before the next marker, stopping at `\end{document}`. Missing or duplicated labels return no fragment. Splitting one theorem internally with markers does not preserve a complete environment.

Section indexing supports chapter, section, subsection, and subsubsection, including starred forms. The workspace links each section to its first subsequent bound node. Sections without nodes still expose the TeX source file. Previous/next navigation only visits bound nodes within the same TeX file.

## Rendering pipeline

`render_tex(fragment, preamble)` starts an independent Python worker, sending JSON and receiving HTML plus warnings. Combined input exceeding 200,000 characters falls back immediately; the subprocess has an eight-second timeout. The worker retains matching single-line macro/theorem definitions from the preamble and falls back if its combined source exceeds 100,000 characters.

The worker generates a plasTeX DOM. A controlled adapter emits paragraphs, headings, lists, emphasis, theorems, references, and math placeholders. Escaped math source is stored in `data-tex` and rendered by local KaTeX in the browser. TeX references may remain textual; this is not a full LaTeX numbering and cross-reference system.

Forbidden external input, file operations, package loading, low-level macro definitions, image commands, and related commands trigger source fallback. The adapter does not emit arbitrary TeX-generated HTML. Timeouts, process failures, and unsupported commands preserve readable source and warnings.

## Limits and troubleshooting

This is a bounded reading renderer, not a complete LaTeX engine or operating-system security sandbox. Multiline macros, complex packages, external images, and cross-file `\input` are not fully supported. Preserving imported source directories does not imply include expansion during rendering.

For missing labels, check paths and spelling; fix duplicates in the file. For broken fragments, move markers outside environments. Switch to TeX mode when rendering warnings appear. Refresh after edits to clear cached output. See [TODO](../TODO.en.md) for future work.
