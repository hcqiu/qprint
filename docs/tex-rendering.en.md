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

Repeated labels within a file are supported for statements and separated proofs. `fragment(label)` joins matching fragments in source order; each stops at the next marker, section heading, bibliography, or `\end{document}`. Only missing labels return no fragment. `fragments(label)` exposes the individual parts; `annotations(label)` collects all `\bpdesc` descriptions and deduplicated `\uses` labels. Arguments support balanced nested braces. Splitting one theorem internally with markers does not preserve a complete environment.

Section indexing supports chapter, section, subsection, and subsubsection, including starred forms. The workspace links each section to its first subsequent bound node. Sections without nodes still expose the TeX source file. Previous/next navigation only visits bound nodes within the same TeX file.

## Rendering pipeline

`render_tex(fragment, preamble, references=None)` starts an independent Python worker, sending JSON and receiving HTML plus warnings. Combined input exceeding 200,000 characters falls back immediately; the subprocess has an eight-second timeout. The worker retains matching single-line macro/theorem definitions from the preamble and falls back if its combined source exceeds 100,000 characters.

The worker generates a plasTeX DOM. A controlled adapter emits paragraphs, headings, lists, emphasis, theorems, references, and math placeholders. Escaped math source is stored in `data-tex` and rendered by local KaTeX in the browser.

Text-mode `~`, `\thinspace`, `\enspace`, `\quad`, and `\qquad` become corresponding Unicode spaces. Rules (`\hrulefill` / `\dotfill`) and spacing (`\vspace` / `\hspace` and paragraph skips) use bounded CSS approximations; line breaks become `<br>`. Paper pagination, `\noindent`, `\relax`, and `\leavevmode` are safely ignored. Box `to` / `spread` dimensions are consumed while keeping box content. Math still goes to KaTeX, and verbatim remains literal. Unsupported layout commands are deduplicated into one warning per page, including both body and BBL warnings. Missing references, external-command restrictions, and parsing failures remain separate diagnostics.

Ordinary `\label` commands create hidden anchors. `\ref` and `\eqref` display linked numbers, with parentheses for `eqref`. The workspace caches numbering for each whole TeX paper, preserving context for forward references, references across nodes, and fragments joined by repeated `bpnode` markers. Local references scroll to the label; references across nodes open the target node and then scroll. Labels outside bound fragments open the source at the corresponding line. Ordinary references are resolved separately from Blueprint dependencies, preserving existing `\uses` and `\bpnode` behavior.

Labels are removed from KaTeX input. References inside math become numbers, with clickable links after the formula. Missing or duplicate ordinary labels produce visible text and warnings instead of guessed destinations. If size limits, timeouts, or unsupported external commands prevent whole-paper numbering, links display label names rather than misleading fragment-local numbers. Cross-file `\input` expansion remains unsupported; labels are never implicitly matched against another paper.

Forbidden external input, file operations, package loading, low-level macro definitions, image commands, and related commands trigger source fallback. The adapter does not emit arbitrary TeX-generated HTML. Timeouts, process failures, and unsupported commands preserve readable source and warnings.

## Limits and troubleshooting

This is a bounded reading renderer, not a complete LaTeX engine or operating-system security sandbox. Multiline macros, complex packages, external images, and cross-file `\input` are not fully supported. Preserving imported source directories does not imply include expansion during rendering.

For missing labels, check paths and spelling; ensure repeated labels denote the same mathematical node. For broken fragments, move markers outside environments. Switch to TeX mode when rendering warnings appear. Refresh after edits to clear cached output. See [TODO](../TODO.en.md) for future work.

## Citations and the References page

Following the rendering rules in the [cross-file citation guide](../产品经理prompt/跨文件引用指南.md), `\cite{KM}` stays literal when no `.bbl` exists beside the TeX file. A `.bib` alone does not enable citation rendering. BibTeX `thebibliography` / `bibitem` output supplies numeric or explicit labels, multiple citation keys, and optional notes such as `\cite[Theorem 2]{KM}`. Clicking a citation opens the paper's complete References list and locates the entry. The sidebar also provides a References entry; returning to the citing node, reloading, and browser history are supported.

A BBL matching the TeX basename takes precedence; otherwise the sole BBL in that directory is used. Ambiguous files preserve source with a warning instead of mixing paper numbering. Missing or duplicate citation keys display `?` with warnings. Read failures, unsupported formats (including biblatex `\entry` data), and parsing failures preserve readable source. Existing size, timeout, and external-command restrictions apply to BBL files too. Refresh clears cached results. `/api/references?path=...` returns references for an indexed paper.

Bibliographic navigation and Blueprint dependencies remain separate: `\cite` opens the reference list, while existing `\uses` links open nodes. The guide's agent-driven project search and `\uses` annotation rules belong to the annotation workflow; the renderer does not infer graph dependencies from citation keys alone.

## Blueprint annotations and conversion

`bpnode` and `bpdesc` are hidden in rendered paper content; descriptions become Blueprint prose. `uses` produces inline dependency links while preserving existing `ref` and `cite`. Links inside math appear after the formula so KaTeX receives clean input. Resolution prefers explicit node IDs, same-file TeX anchors, declared dependencies, then globally unique aliases. Missing or ambiguous targets remain visible with warnings. URLs and labels are escaped.

Use the [tex-to-blueprint skill](../skills/tex-to-blueprint/SKILL.md) for annotation, generation and mathematical review. Run `conda run -n qprint python -m qprint.tex_to_blueprint` or the skill's `scripts/convert.py` entry point. See [workflow and validation](tex-to-blueprint.en.md).
