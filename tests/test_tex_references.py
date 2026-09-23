from html import unescape
import re

from qprint.tex import render_tex, tex_label_anchor
from qprint.workspace import Workspace


def test_local_forward_references_and_equation_labels():
    html, warnings = render_tex(
        r"See \ref{th:a} and \eqref{eq:a}."
        r"\begin{theorem}\label{th:a}A\end{theorem}"
        r"\begin{equation}x=1\label{eq:a}\end{equation}",
        r"\newtheorem{theorem}{Theorem}",
    )
    assert not warnings
    assert f'href="#{tex_label_anchor("th:a")}"' in html
    assert f'id="{tex_label_anchor("eq:a")}"' in html
    assert '>1</a>' in html and '>(1)</a>' in html
    assert r"\label" not in html and r"\ref" not in html


def test_math_references_keep_numbers_and_clickable_links_outside_katex():
    html, warnings = render_tex(
        r"\begin{equation}x=1\label{eq:a}\end{equation}"
        r"$x=\ref{eq:a}+\eqref{eq:a}\uses{dependency}$",
        references={"dependency": "A#B"},
    )
    assert not warnings
    math_sources = [unescape(s) for s in re.findall(r'data-tex="([^"]*)"', html)]
    assert any('x=1+(1)' in s for s in math_sources)
    assert all(r"\ref" not in s and r"\label" not in s and "qprintdependency" not in s for s in math_sources)
    assert html.count('class="reference tex-ref"') == 2
    assert '<a class="wikilink tex-use" href="#node=A%23B">↗ dependency</a>' in html


def test_missing_duplicate_and_html_labels_are_safe():
    html, warnings = render_tex(r"\label{duplicate}\label{duplicate}\ref{duplicate}\ref{<missing>}")
    assert len(warnings) == 2
    assert 'class="reference tex-ref"' not in html
    assert '&lt;missing&gt;' in html and '<missing>' not in html
    html, warnings = render_tex(r'\label{a"<b>}\ref{a"<b>}')
    assert not warnings and '<b>' not in html
    assert f'id="{tex_label_anchor(chr(97) + chr(34) + "<b>")}"' in html


def make_workspace(tmp_path):
    (tmp_path / 'tex').mkdir()
    (tmp_path / 'blueprint').mkdir()
    (tmp_path / 'blueprint/A.md').write_text(
        '# First\n```qprint\ntex: paper#one\n```\n'
        '# Second\n```qprint\ntex: paper#two\n```\n', encoding='utf-8')
    (tmp_path / 'tex/paper.tex').write_text(r'''\documentclass{article}
\newcommand{\bpnode}[1]{}
\newtheorem{theorem}{Theorem}[section]
\begin{document}
\section{First section}\label{sec:one}
\bpnode{one}
See \ref{th:second}, \ref{th:first}, \ref{eq:first}, and \ref{sec:one}.
\uses{two}
\begin{theorem}\label{th:first}First theorem.\end{theorem}
\begin{equation}a=1\label{eq:first}\end{equation}
% \label{th:second}
\begin{verbatim}\label{th:second}\end{verbatim}
\bpnode{two}
\begin{theorem}\label{th:second}Second theorem.\end{theorem}
\begin{equation}b=2\label{eq:second}\end{equation}
See \ref{th:first}, \ref{th:second}, and \eqref{eq:second}.
\bpnode{one}
Proof continues; see \ref{th:first} and \ref{th:second}.
\end{document}''', encoding='utf-8')
    return Workspace(tmp_path)


def test_workspace_global_numbers_local_cross_node_and_repeated_fragments(tmp_path):
    workspace = make_workspace(tmp_path)
    first = workspace.detail('A#First')['tex_content']
    second = workspace.detail('A#Second')['tex_content']
    assert not first['warnings'] and not second['warnings']
    assert 'data-tex-node="A#Second"' in first['html']
    assert 'href="#node=A%23Second"' in first['html']
    assert f'href="#{tex_label_anchor("th:first")}"' in first['html']
    assert first['html'].count('>1.2</a>') == 2
    assert '>1.1</a>' in second['html'] and '>1.2</a>' in second['html']
    assert '>(2)</a>' in second['html']
    assert 'data-tex-node="A#First"' in second['html']
    assert 'data-paper="paper.tex" data-line="5"' in first['html']
    assert '<a class="wikilink tex-use" href="#node=A%23Second">↗ two</a>' in first['html']
    assert '\\bpnode' not in first['html']


def test_label_scope_reload_and_missing_reference(tmp_path):
    workspace = make_workspace(tmp_path)
    workspace.detail('A#First')
    (tmp_path / 'tex/other.tex').write_text(r'\bpnode{other}\label{th:first}Other paper.', encoding='utf-8')
    path = tmp_path / 'tex/paper.tex'
    path.write_text(path.read_text(encoding='utf-8').replace(r'\label{th:second}', r'\label{th:changed}'), encoding='utf-8')
    workspace.reload()
    detail = workspace.detail('A#First')['tex_content']
    assert any('th:second' in w for w in detail['warnings'])
    assert not any('th:first' in w for w in detail['warnings'])
    assert 'data-tex-node="A#Second"' not in detail['html']


def test_reference_index_cannot_execute_external_tex(tmp_path):
    workspace = make_workspace(tmp_path)
    path = tmp_path / 'tex/paper.tex'
    path.write_text(path.read_text(encoding='utf-8').replace(r'\section{First section}', r'\input{secret}\section{First section}'), encoding='utf-8')
    workspace.reload()
    detail = workspace.detail('A#Second')['tex_content']
    assert not detail['warnings']
    assert '>th:first</a>' in detail['html']  # No invented fragment-local number.
    assert 'data-tex-node="A#First"' in detail['html']
