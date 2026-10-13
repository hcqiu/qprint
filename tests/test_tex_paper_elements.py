from html import unescape
import re

from qprint.tex import TexDocument, render_tex, tex_graphics
from qprint.tex_support import compact_label_source, normalize_math, simple_definitions
from qprint.workspace import Workspace


def test_amsrefs_records_preserve_fields_math_and_citation_labels():
    source = r'''\begin{bibdiv}\begin{biblist}
\bib{AB}{article}{author={A, Alice},author={B, Bob},title={A {$4$}-manifold},
journal={Journal},date={2025},pages={1\ndash 10},url={https://example.org/?a=1&b=2},}
\bib{C}{book}{author={C, Claire},title={A {nested} title},label={C25},publisher={Press},date={2025},}
\end{biblist}\end{bibdiv}'''
    data, warnings = render_tex(source, bibliography_only=True)
    assert not warnings
    a, b = data['entries']
    assert a['label'] == '1' and b['label'] == 'C25'
    assert all(text in a['html'] for text in ['A, Alice', 'B, Bob', 'data-tex=', '1–10', 'Journal', '2025'])
    assert 'a=1&amp;b=2' in a['html']
    html, warnings = render_tex(r'\cite[Theorem~2]{AB,C}', bibliography={'path': 'P.tex', 'entries': {e['key']: e for e in data['entries']}})
    assert not warnings and 'data-cite-key="AB"' in html and '>C25</a>' in html


def test_comments_are_hidden_from_rendering_labels_and_blueprint_scanning():
    source = r'Before\begin{comment}\bpnode{fake}\label{fake}\input{secret}Hidden\end{comment}After\bpnode{real}'
    assert [a['label'] for a in TexDocument('a.tex', source).anchors] == ['real']
    html, warnings = render_tex(source)
    assert not warnings and 'BeforeAfter' in html and 'Hidden' not in html and 'secret' not in html
    html, warnings = render_tex(r'\verb|\begin{comment}Literal\end{comment}|')
    assert not warnings and 'Literal' in html


def test_clever_references_keep_type_number_and_cross_node_navigation(tmp_path):
    (tmp_path / 'tex').mkdir(); (tmp_path / 'blueprint').mkdir()
    (tmp_path / 'blueprint/P.md').write_text('# First\n```qprint\ntex: main#first\n```\n# Second\n```qprint\ntex: main#second\n```', encoding='utf-8')
    (tmp_path / 'tex/main.tex').write_text(r'''\newtheorem{thm}{Theorem}[section]
\begin{document}\section{A}\bpnode{first}\begin{thm}[Named result]\label{thm_one}Text\end{thm}
\bpnode{second}See \Cref{thm_one} and \cref{thm_one}.\uses{first}\end{document}''', encoding='utf-8')
    workspace = Workspace(tmp_path)
    first = workspace.detail('P#First')['tex_content']['html']
    second = workspace.detail('P#Second')['tex_content']['html']
    assert 'Theorem 1.1' in first and 'Named result' in first
    assert 'Theorem 1.1</a>' in second and 'theorem 1.1</a>' in second
    assert 'data-tex-node="P#First"' in second
    assert r'\Cref' not in second


def test_large_paper_counter_index_agrees_with_small_paper():
    preamble = r'\newtheorem{thm}{Theorem}[section]'
    body = r'''\section{First}\begin{thm}\label{one}A\end{thm}
\begin{align}a&=\begin{matrix}b\\c\end{matrix}\label{equation_one}\\c&=d\label{equation_two}\end{align}
\section{Next}\begin{thm}\label{two}B\end{thm}\appendix\section{Appendix}\label{appendix_a}'''
    small, warnings = render_tex(body, preamble, index_only=True)
    large, large_warnings = render_tex(('Plain prose. ' * 18000) + body, preamble, index_only=True)
    assert not warnings and not large_warnings and small == large
    assert large['two']['text'] == '2.1' and large['equation_one']['text'] == '1'
    assert large['appendix_a']['text'] == 'A'


def test_tables_keep_rows_columns_spans_borders_and_inline_math():
    html, warnings = render_tex(r'\begin{tabular}{|l|r|}\hline A&$x$\\\hline\multicolumn{2}{c}{Total}\\\hline\end{tabular}')
    assert not warnings
    assert html.count('<tr>') == 2 and html.count('<td ') == 3
    assert 'colspan="2"' in html and 'border-top' in html and 'data-tex=' in html
    assert r'\hline' not in html


def test_math_aliases_and_layout_preserve_mathematical_content():
    aliases = simple_definitions(r'\def\H{\mathbb{H}}\def\wt{\widetilde}\def\bad{\input{secret}}')
    source = r'\H_i+\wt{x}+\begin{array}{@{}c|c@{}}x&y\end{array}+\xrightarrow{\makebox[2cm][c]{\tiny $f\otimes g$}}'
    result = normalize_math(source, aliases)
    assert r'\mathbb{H}_i' in result and r'\widetilde{x}' in result
    assert r'{c|c}' in result and r'f\otimes g' in result
    assert r'\makebox' not in result and 'tiny' not in result and not any('bad' in a for a in aliases)
    html, warnings = render_tex(r'\begin{align}a&=\H_i\\b&=\wt{x}\end{align}', r'\def\H{\mathbb{H}}\def\wt{\widetilde}')
    assert not warnings and html.count('data-tex=') == 1
    math = unescape(re.search(r'data-tex="([^"]+)"', html)[1])
    assert r'\mathbb' in math and r'\widetilde' in math


def test_exchange_diagrams_preserve_surrounding_math_and_equation_labels():
    source = r'\begin{equation}\label{eq_one}H=\vcenter{\xymatrix@C=2em{A\ar[r]&B}}\end{equation}'
    graphic, = tex_graphics(source)
    assert graphic['kind'] == 'diagram' and graphic['source'] == source
    labels, warnings = render_tex(source, index_only=True)
    assert not warnings and labels['eq_one']['text'] == '1'


def test_color_is_escaped_and_cannot_inject_css():
    html, warnings = render_tex(r'\textcolor{red}{Visible $x$}\textcolor{red;position:fixed}{Safe}')
    assert not warnings and 'color:red' in html and 'position:' not in html
    assert 'Visible' in html and 'Safe' in html


def test_theorem_does_not_take_a_nested_equation_number_or_repeat_at_end():
    preamble = r'\newtheorem{thm}{Theorem}'
    html, warnings = render_tex(r'\begin{thm}Text\begin{equation}x=1\label{eq}\end{equation}\end{thm}', preamble,
                                labels={'eq': {'text': '17', 'kind': 'Equation', 'local': True}})
    assert not warnings and '>Theorem</div>' in html and 'Theorem 17' not in html
    html, warnings = render_tex(r'Trailing text\end{thm}', preamble)
    assert not warnings and 'Trailing text' in html and 'theorem-label' not in html
