import pytest

from qprint.tex import render_tex


@pytest.mark.parametrize('preamble', ['', r'''
\providecommand{\source}[1]{}
\providecommand{\dcref}[1]{}
\newcommand{\lean}[1]{Printed Lean: #1}
'''])
def test_ancient_kappa_metadata_is_readable_and_lean_is_hidden(preamble):
    source = r'''\begin{definition}[Ancient $\kappa$-solution]
\label{def:ancient-kappa}
An ancient $\kappa$-solution is a smooth Ricci flow $g(t)$ on $N$.
\[
 \bigl(A(s,q)\leq r^{-2}\text{ for }t-r^2<s\leq t,\
          q\in B_t(p,r)\bigr)
 \ \Longrightarrow\ \mu_{g(t)}(B_t(p,r))\geq\kappa r^n .
\]
The flow equation at zero uses derivatives within the closed time domain.
\lean{PoincareMT.AncientKappaSolution}
\source{MT2007}
\dcref{Definitions 9.1--9.2, pp. 179--180}
\end{definition}
Nonnegative curvature operator means positivity of the curvature quadratic form.'''
    html, warnings = render_tex(source, preamble)
    assert not warnings
    assert 'PoincareMT' not in html and 'Printed Lean' not in html
    assert r'\lean' not in html and r'\source' not in html and r'\dcref' not in html
    assert 'Source: ' in html and 'MT2007' in html
    assert '1. Definitions 9.1–9.2, pp. 179–180' in html
    assert '出处：' not in html
    assert 'data-tex=' in html and r'\Longrightarrow' in html
    assert 'Nonnegative curvature operator' in html


def test_source_keys_use_existing_bibliography_links_and_coordinates_keep_tex():
    bibliography = {'path': 'main.tex', 'entries': {'MT_2007': {'label': 'MT07'}, 'CK': {'label': 'CK04'}}}
    html, warnings = render_tex(r'''\source{MT_2007,CK}
\dcref{\emph{Theorem}~9.1, $n\geq2$}
\dcref{Section 9.2}
\dcref{Section 9.3}
\source{CK}\dcref{Another source}''', bibliography=bibliography)
    assert not warnings
    assert 'data-cite-key="MT_2007"' in html and '>MT07</a>' in html
    assert 'data-cite-key="CK"' in html and '>CK04</a>' in html
    assert '<em>Theorem</em>' in html and 'data-tex=' in html
    assert html.count('class="tex-dcref"') == 4
    assert html.count('class="tex-source-references"') == 2
    assert '1. <em>Theorem</em>' in html
    assert '2. Section 9.2' in html and '3. Section 9.3' in html
    assert '1. Another source' in html


def test_metadata_arguments_are_consumed_safely_and_verbatim_stays_literal():
    html, warnings = render_tex(r'''Before\lean{A.{B}, C_D}After
\source{<script>_&}\dcref{<img> \textbf{Safe}}
\verb|\lean{Literal}| % \source{Comment}
\source{}\dcref{}''')
    assert not warnings
    assert 'BeforeAfter' in html and 'C_D' not in html
    assert '&lt;script&gt;_&amp;' in html and '&lt;img&gt;' in html
    assert '<strong>Safe</strong>' in html and 'Literal' in html
    assert 'Comment' not in html
    assert html.count('class="tex-source"') == 1
    assert html.count('class="tex-dcref"') == 1
