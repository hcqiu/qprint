from html import unescape
import re

from fastapi.testclient import TestClient
import pytest

from qprint.server import create_app
from qprint.tex import render_tex
from qprint.workspace import Workspace


BBL = r'''\begin{thebibliography}{99}
\bibitem{KM}K. Author and M. Author.
\newblock \emph{A mathematical paper}.
\newblock Journal, 2020. \url{https://example.com/paper?a=1&b=2}
\bibitem[AB21]{AB}A. Author. \textbf{Another paper}, 2021.
\end{thebibliography}'''


def paper(root, folder='Paper', bbl=BBL):
    tex = root / 'tex' / folder
    tex.mkdir(parents=True, exist_ok=True)
    blueprint = root / 'blueprint'
    blueprint.mkdir(exist_ok=True)
    (blueprint / f'{folder}.md').write_text(
        f'# Result\n```qprint\ntex: {folder}/main#result\n```\n'
        '# Dependency\n', encoding='utf-8')
    (tex / 'main.tex').write_text(r'''\documentclass{article}
\begin{document}
\bpnode{result}
\label{local}See \ref{local} and \cite[Theorem 2]{KM,AB}\uses{Dependency}.
\bibliography{refs}
\end{document}''', encoding='utf-8')
    if bbl is not None:
        (tex / 'main.bbl').write_text(bbl, encoding='utf-8')
    return tex


@pytest.mark.parametrize('bib_only', [False, True])
def test_no_bbl_preserves_cite_source_even_with_bib(tmp_path, bib_only):
    tex = paper(tmp_path, bbl=None)
    if bib_only:
        (tex / 'refs.bib').write_text('@article{KM,title={Paper}}', encoding='utf-8')
    workspace = Workspace(tmp_path)
    content = workspace.detail('Paper#Result')['tex_content']
    assert r'\cite[Theorem 2]{KM,AB}' in content['html']
    assert 'class="tex-cite"' not in content['html']
    assert not content['warnings']
    assert not workspace.project()['papers'][0]['has_bibliography']


def test_citations_bibliography_and_blueprint_links_are_independent(tmp_path):
    paper(tmp_path)
    workspace = Workspace(tmp_path)
    content = workspace.detail('Paper#Result')['tex_content']
    assert not content['warnings']
    assert r'\cite' not in content['html']
    assert 'href="#references=Paper%2Fmain.tex&amp;cite=KM"' in content['html']
    assert '>1</a>' in content['html'] and '>AB21</a>' in content['html']
    assert ', Theorem 2]' in content['html']
    assert '<a class="wikilink tex-use" href="#node=Paper%23Dependency">↗ Dependency</a>' in content['html']
    assert 'class="reference tex-ref"' in content['html']
    bibliography = workspace.bibliography('Paper/main.tex')
    assert [e['key'] for e in bibliography['entries']] == ['KM', 'AB']
    assert '<em>A mathematical paper</em>' in bibliography['entries'][0]['html']
    assert 'href="https://example.com/paper?a=1&amp;b=2"' in bibliography['entries'][0]['html']
    assert workspace.project()['papers'][0]['has_bibliography']
    assert not workspace.edges  # A citation alone does not invent graph dependencies.


def test_bbl_selection_is_local_and_prefers_matching_filename(tmp_path):
    tex = paper(tmp_path)
    (tex / 'other.bbl').write_text(BBL.replace('AB21', 'WRONG'), encoding='utf-8')
    paper(tmp_path, 'Other', BBL.replace('AB21', 'OTHER'))
    workspace = Workspace(tmp_path)
    assert '>AB21</a>' in workspace.detail('Paper#Result')['tex_content']['html']
    assert '>OTHER</a>' in workspace.detail('Other#Result')['tex_content']['html']
    (tex / 'main.bbl').unlink()
    workspace.reload()
    assert '>WRONG</a>' in workspace.detail('Paper#Result')['tex_content']['html']
    (tex / 'third.bbl').write_text(BBL, encoding='utf-8')
    workspace.reload()
    content = workspace.detail('Paper#Result')['tex_content']
    assert r'\cite' in content['html'] and any('多个 BBL' in w for w in content['warnings'])


def test_bbl_reload_and_missing_keys(tmp_path):
    tex = paper(tmp_path)
    workspace = Workspace(tmp_path)
    workspace.detail('Paper#Result')
    (tex / 'main.bbl').write_text(BBL.replace('{KM}', '{missing}').replace('AB21', 'AB22'), encoding='utf-8')
    workspace.reload()
    content = workspace.detail('Paper#Result')['tex_content']
    assert any('KM' in w for w in content['warnings'])
    assert '>AB22</a>' in content['html']
    assert 'data-cite-key="KM"' not in content['html']


def test_duplicate_keys_do_not_link_to_arbitrary_entries(tmp_path):
    paper(tmp_path, bbl=BBL.replace(r'\end{thebibliography}', r'\bibitem{KM}Duplicate.\end{thebibliography}'))
    workspace = Workspace(tmp_path)
    content = workspace.detail('Paper#Result')['tex_content']
    assert any('重复' in w for w in content['warnings'])
    assert 'data-cite-key="KM"' not in content['html']
    anchors = [e['anchor'] for e in workspace.bibliography('Paper/main.tex')['entries']]
    assert len(anchors) == len(set(anchors))


@pytest.mark.parametrize('bbl', [r'\input{secret}', r'\entry{KM}{article}{}\endentry', ''])
def test_unsupported_bbl_preserves_readable_source(tmp_path, bbl):
    paper(tmp_path, bbl=bbl)
    workspace = Workspace(tmp_path)
    content = workspace.detail('Paper#Result')['tex_content']
    assert r'\cite[Theorem 2]{KM,AB}' in content['html']
    assert content['warnings']
    assert 'tex-fallback' in workspace.bibliography('Paper/main.tex')['html']


def test_math_citations_do_not_enter_katex():
    html, warnings = render_tex(r'$x\cite{KM}\uses{dep}$', references={'dep': 'A#B'},
                                bibliography={'path': 'A/main.tex', 'entries': {'KM': {'label': '1'}}})
    assert not warnings
    sources = [unescape(s) for s in re.findall(r'data-tex="([^"]*)"', html)]
    assert all(r'\cite' not in s and 'qprintdependency' not in s for s in sources)
    assert 'data-cite-key="KM"' in html and 'class="wikilink tex-use"' in html
    html, warnings = render_tex(r'$x\cite{KM}$')
    assert not warnings and r'\cite{KM}' in html


def test_bibliography_escapes_html_and_rejects_unsafe_links():
    parsed, warnings = render_tex(r'''\begin{thebibliography}{1}
\bibitem{key"<x>}<script>alert(1)</script>\href{javascript:alert(1)}{Unsafe}
\end{thebibliography}''', bibliography_only=True)
    assert not warnings
    entry = parsed['entries'][0]
    assert '<script>' not in entry['html'] and '&lt;script&gt;' in entry['html']
    assert 'javascript:' not in entry['html'] and 'Unsafe' in entry['html']
    assert '"' not in entry['anchor']


def test_bibliography_nonbreaking_spaces_do_not_warn_on_every_node(tmp_path):
    paper(tmp_path, bbl=BBL.replace('K. Author', 'K.~Author').replace('Journal, 2020.', 'Journal, pp.~483--532.'))
    workspace = Workspace(tmp_path)
    bibliography = workspace.bibliography('Paper/main.tex')
    assert not bibliography['warnings']
    entry = bibliography['entries'][0]['html']
    assert 'K.\u00a0Author' in entry and 'pp.\u00a0483' in entry
    content = workspace.detail('Paper#Result')['tex_content']
    assert not content['warnings']
    assert 'data-cite-key="KM"' in content['html']
    assert 'class="wikilink tex-use"' in content['html']


def test_references_api_is_scoped_to_indexed_papers(tmp_path):
    paper(tmp_path)
    with TestClient(create_app(tmp_path)) as client:
        response = client.get('/api/references', params={'path': 'Paper/main.tex'})
        assert response.status_code == 200
        data = response.json()
        assert len(data['entries']) == 2 and data['bbl'] == 'Paper/main.bbl'
        assert 'citations' not in data
        for path in ('../secret.bbl', 'missing.tex', 'Paper/main.bbl'):
            assert client.get('/api/references', params={'path': path}).status_code == 404
