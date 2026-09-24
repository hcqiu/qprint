from html import unescape
import re

from qprint.tex import merge_tex_warnings, render_tex
from qprint.workspace import Workspace


def test_text_spacing_and_layout_keep_readable_content():
    html, warnings = render_tex(
        r"A~B\thinspace C\quad D\qquad E\enspace F"
        r"\noindent\relax\leavevmode\unskip G\hrulefill H\dotfill I"
        r"\vspace*{12pt}J\hspace{8pt}K\hspace{-2pt}L\newline M"
        r"\smallskip N\medskip O\bigskip P\newpage Q")
    assert not warnings
    assert "A\u00a0B\u2009C\u2003D\u2003\u2003E\u2002F" in html
    assert 'border-bottom:1px solid currentColor' in html
    assert 'border-bottom:1px dotted currentColor' in html
    assert 'height:12pt' in html and 'width:8pt' in html and 'margin-right:-2pt' in html
    assert '<br>M' in html and html.endswith('Q')
    assert not any(command in html for command in (r'\vspace', r'\noindent', r'\relax', r'\hrulefill'))


def test_spacing_dimensions_are_bounded_and_verbatim_math_are_preserved():
    html, warnings = render_tex(r'A\vspace{10000pt}B\vspace{-10pt}C\verb|\quad ~| $x\quad y\thinspace z$')
    assert not warnings
    assert 'height:144pt' in html and 'height:0pt' in html
    assert r'\quad ~' in html
    sources = [unescape(s) for s in re.findall(r'data-tex="([^"]*)"', html)]
    assert len(sources) == 1 and r'\quad' in sources[0] and r'\thinspace' in sources[0]


def test_ams_bibliography_layout_has_no_source_leaks_or_warnings():
    bbl = r'''\providecommand{\bysame}{\leavevmode\hbox to3em{\hrulefill}\thinspace}
\providecommand{\MR}{\relax\ifhmode\unskip\space\fi MR }
\begin{thebibliography}{9}
\bibitem{first}J.~F. Author. First paper.\MR{123}
\bibitem{second}\bysame, Second paper.\MR{456}
\end{thebibliography}'''
    result, warnings = render_tex(bbl, bibliography_only=True)
    assert not warnings
    first, second = result['entries']
    assert 'J.\u00a0F. Author' in first['html'] and 'MR 123' in first['html']
    assert 'class="tex-rule"' in second['html'] and 'Second paper' in second['html']
    assert 'to3em' not in second['html'] and r'\bysame' not in second['html']
    html, warnings = render_tex(r'\hbox{Inside}\hbox spread 2pt{More}\vbox to10pt{Last}')
    assert not warnings
    assert all(word in html for word in ('Inside', 'More', 'Last'))
    assert 'spread' not in html and 'to10pt' not in html


def test_unhandled_layout_is_one_warning_but_missing_refs_stay_distinct():
    html, warnings = render_tex(r'\unsupportedA\unsupportedB\unsupportedA\ref{missing}')
    layout = [w for w in warnings if w.startswith('部分 TeX 排版细节')]
    assert len(layout) == 1
    assert layout[0].endswith('unsupportedA、unsupportedB')
    assert len(warnings) == 2 and any('TeX 引用不存在' in w for w in warnings)
    assert r'\unsupportedA' in html
    assert merge_tex_warnings([*warnings, *warnings, '未完整渲染命令: unsupportedC'])[-1].endswith(
        'unsupportedA、unsupportedB、unsupportedC')


def test_node_combines_bibliography_and_body_layout_warnings(tmp_path):
    (tmp_path / 'tex').mkdir()
    (tmp_path / 'blueprint').mkdir()
    (tmp_path / 'blueprint/A.md').write_text('# Node\n```qprint\ntex: main#node\n```', encoding='utf-8')
    (tmp_path / 'tex/main.tex').write_text(r'\bpnode{node}\unsupportedBody\unsupportedBoth\cite{key}\uses{missing}', encoding='utf-8')
    (tmp_path / 'tex/main.bbl').write_text(
        r'\begin{thebibliography}{1}\bibitem{key}\unsupportedBib\unsupportedBoth Paper.\end{thebibliography}', encoding='utf-8')
    content = Workspace(tmp_path).detail('A#Node')['tex_content']
    layout = [w for w in content['warnings'] if w.startswith('部分 TeX 排版细节')]
    assert len(layout) == 1
    assert all(name in layout[0] for name in ('unsupportedBody', 'unsupportedBib', 'unsupportedBoth'))
    assert layout[0].count('unsupportedBoth') == 1
    assert len(content['warnings']) == 2 and any('Blueprint 依赖' in w for w in content['warnings'])
    assert 'class="tex-cite"' in content['html']
