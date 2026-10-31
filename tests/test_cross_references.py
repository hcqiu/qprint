import json
from pathlib import Path

import pytest

from qprint.cross_references import citations, link_workspace
from qprint.tex import TexDocument
from qprint.workspace import Workspace


def paper(root, name, identifier, body, bib='', *, preamble='', index=True):
    tex = root / 'tex/Topic' / name
    blueprint = root / 'blueprint/Topic' / name
    tex.mkdir(parents=True)
    blueprint.mkdir(parents=True)
    (tex / '.qprint-source.json').write_text(json.dumps({'type':'arxiv','id':identifier}), encoding='utf-8')
    source = preamble + '\n\\begin{document}\n' + body + '\n\\end{document}\n'
    (tex / 'main.tex').write_text(source, encoding='utf-8')
    if bib:
        (tex / 'main.bbl').write_text(bib, encoding='utf-8')
    doc = TexDocument('main.tex', source)
    nodes = []
    for anchor in dict.fromkeys(a['label'] for a in doc.anchors):
        nodes.append(f'# {anchor}\n\n```qprint\nkind: theorem\ntex: Topic/{name}/main.tex#{anchor}\nuses: []\n```\n\nReviewed prose.\n')
    (blueprint / 'results.md').write_text('\n'.join(nodes), encoding='utf-8')
    if index:
        (blueprint / 'index.md').write_text('---\ntitle: Test paper\n---\n\n## Blueprint\n\n- [[results.md]]\n', encoding='utf-8')
    return tex


def bbl(key, identifier):
    return r'\begin{thebibliography}{9}\bibitem{' + key + '}Author. arXiv:' + identifier + r'.\end{thebibliography}'


@pytest.mark.parametrize('word,kind', [
    ('Thm','theorem'),('thm.','theorem'),('THEOREM','theorem'),('Theorem','theorem'),
    ('Prop','proposition'),('Proposition','proposition'),('prp.','proposition'),
    ('Lemma','lemma'),('lem.','lemma'),('Def','definition'),('Definition','definition'),
    ('definition','definition'),('defn','definition'),('Defn.','definition'),
    ('Cor.','corollary'),('Remark','remark'),('rmk','remark'),('Example','example'),('Conj.','conjecture'),
])
@pytest.mark.parametrize('template', [r'WORD~2.3 in \cite{B}', r'\cite[WORD~2.3]{B}', r'\cite{B}, WORD 2.3'])
def test_flexible_adjacent_locators(word, kind, template):
    call, = citations(TexDocument('a.tex', template.replace('WORD',word)))
    assert call['locators'] == [(kind,'2.3')]
    assert not call['uncertain']


def test_citation_scanner_ignores_comments_preamble_and_bibliography():
    source = r'''\newcommand{\test}{\cite{no}}
\begin{document}
% \cite{comment}
\verb|\cite{verbatim}|\begin{comment}\cite{hidden}\end{comment}
\citep[see][{Thm.}~A.2]{B}
\cite*{C}
\begin{thebibliography}{9}\bibitem{B}\cite{inside}\end{thebibliography}
\end{document}'''
    calls = list(citations(TexDocument('a.tex', source)))
    assert [c['keys'] for c in calls] == [['B'],['C']]
    assert calls[0]['locators'] == [('theorem','a.2')]


@pytest.mark.parametrize('source', [r'Theorems 1--3 \cite{B}', r'\cite[Theorems 1--3]{B}',
                                  r'\cite{B}, Theorems 1--3', r'Theorem \ref{unknown} in \cite{B}'])
def test_unsupported_locator_is_not_a_bare_citation(source):
    call, = citations(TexDocument('a.tex', source))
    assert call['uncertain']


def test_compact_abbreviations_and_lists():
    call, = citations(TexDocument('a.tex', r'\cite[Thm.2.3 and 2.4]{B}'))
    assert call['locators'] == [('theorem','2.3'),('theorem','2.4')]


def test_bidirectional_links_numbers_index_markdown_backups_and_idempotence(tmp_path):
    a = paper(tmp_path,'A','2401.00001', r'\bpnode{a}See \cite[Prop. 1]{B}. Also \cite{B}.', bbl('B','2401.00002v1'))
    b = paper(tmp_path,'B','2401.00002v3', r'\bpnode{b}\begin{prop}Result.\end{prop} Related \cite{A}.',
              bbl('A','2401.00001'), preamble=r'\newtheorem{prop}{Proposition}')
    original = (a / 'main.tex').read_bytes()
    preview = link_workspace(tmp_path, imported='2401.00002', dry_run=True)
    assert preview['links_added'] == 3 and not preview['diagnostics']
    assert (a / 'main.tex').read_bytes() == original
    assert not (tmp_path / '.qprint/cross-links').exists()
    report = link_workspace(tmp_path, imported='2401.00002')
    assert report['links_added'] == 3 and report['citations_changed'] == 3
    assert r'\cite[Prop. 1]{B}\uses{Topic/B/results#b}' in (a/'main.tex').read_text(encoding='utf-8')
    assert r'\cite{B}\uses{Topic/B/index#index}' in (a/'main.tex').read_text(encoding='utf-8')
    assert r'\cite{A}\uses{Topic/A/index#index}' in (b/'main.tex').read_text(encoding='utf-8')
    w = Workspace(tmp_path)
    assert '[[Topic/B/results#b]]' in w.nodes['Topic/A/results#a'].uses
    assert not w.diagnostics
    assert len(w.edges) == 5
    rendered = w.detail('Topic/A/results#a')['tex_content']
    assert 'href="#node=Topic%2FB%2Fresults%23b"' in rendered['html']
    assert not any('依赖未解析' in warning for warning in rendered['warnings'])
    folder = (tmp_path / report['report_path']).parent
    assert (folder / 'before/tex/Topic/A/main.tex').read_bytes() == original
    again = link_workspace(tmp_path)
    assert again['links_added'] == 0 and not again['files']


def test_missing_and_duplicate_numbered_nodes_fall_back_to_index(tmp_path):
    a = paper(tmp_path,'A','2401.00001', r'\bpnode{a}\cite[Thm 99]{B}. \cite[Thm 1]{B}.', bbl('B','2401.00002'))
    paper(tmp_path,'B','2401.00002', r'\bpnode{one}\begin{thm}X\end{thm}\setcounter{thm}{0}\bpnode{two}\begin{thm}Y\end{thm}', preamble=r'\newtheorem{thm}{Theorem}')
    report = link_workspace(tmp_path)
    assert report['links_added'] == 2
    assert len(report['diagnostics']) == 2
    assert (a/'main.tex').read_text(encoding='utf-8').count(r'\uses{Topic/B/index#index}') == 2
    assert (tmp_path / report['report_path']).is_file()


def test_bib_only_nested_chapter_and_import_filter(tmp_path):
    a = paper(tmp_path,'A','2401.00001', r'\input{chapters/result}')
    (a/'chapters').mkdir()
    (a/'chapters/result.tex').write_text(r'\bpnode{a}\cite{B}\cite{C}', encoding='utf-8')
    (tmp_path/'blueprint/Topic/A/results.md').write_text('# a\n```qprint\ntex: Topic/A/chapters/result#a\n```\n',encoding='utf-8')
    (a/'refs.bib').write_text('@article{B,title={Nested {title}},archivePrefix={arXiv},eprint={2401.00002}}\n'
                             '@article{C,title="Other",url="https://arxiv.org/abs/2401.00003"}',encoding='utf-8')
    paper(tmp_path,'B','2401.00002',r'\bpnode{b}B',index=False)
    paper(tmp_path,'C','2401.00003',r'\bpnode{c}C')
    report = link_workspace(tmp_path, imported='2401.00002v2')
    assert report['links_added'] == 1 and not report['diagnostics']
    assert r'\cite{C}\uses' not in (a/'chapters/result.tex').read_text(encoding='utf-8')
    assert 'Topic/B/index#index' in (a/'chapters/result.tex').read_text(encoding='utf-8')
    assert r'\providecommand{\uses}[1]{}' in (a/'main.tex').read_text(encoding='utf-8')


def test_numbering_follows_include_order_and_shared_counters(tmp_path):
    a = paper(tmp_path,'A','2401.00001',r'\bpnode{a}\cite[Defn. 2.1]{B}',bbl('B','2401.00002'))
    b = paper(tmp_path,'B','2401.00002',r'\section{First}\input{first}\section{Second}\input{second}',
              preamble=r'\newtheorem{thm}{Theorem}[section]\newtheorem{defn}[thm]{Definition}')
    (b/'first.tex').write_text(r'\bpnode{first}\begin{thm}X\end{thm}',encoding='utf-8')
    (b/'second.tex').write_text(r'\bpnode{second}\begin{defn}Y\end{defn}',encoding='utf-8')
    (tmp_path/'blueprint/Topic/B/results.md').write_text('# first\n```qprint\ntex: Topic/B/first#first\n```\n# second\n```qprint\ntex: Topic/B/second#second\n```\n',encoding='utf-8')
    report=link_workspace(tmp_path)
    assert report['links_added']==1 and not report['diagnostics']
    assert 'Topic/B/results#second' in (a/'main.tex').read_text(encoding='utf-8')


def test_duplicate_arxiv_projects_and_multiple_keys_with_locator_are_ambiguous(tmp_path):
    paper(tmp_path,'A','2401.00001',r'\bpnode{a}\cite{B}\cite[Thm 1]{C,D}',bbl('B','2401.00002')+bbl('C','2401.00003'))
    paper(tmp_path,'B','2401.00002',r'\bpnode{b}B')
    paper(tmp_path,'Bcopy','2401.00002v2',r'\bpnode{b}B')
    paper(tmp_path,'C','2401.00003',r'\bpnode{c}C')
    report=link_workspace(tmp_path)
    assert report['links_added']==1 and len(report['diagnostics'])==2


def test_existing_manual_uses_and_reviewed_metadata_are_preserved(tmp_path):
    a=paper(tmp_path,'A','2401.00001',r'\bpnode{a}\cite{B}\uses{Topic/B/results#b}',bbl('B','2401.00002'))
    paper(tmp_path,'B','2401.00002',r'\bpnode{b}B')
    md=tmp_path/'blueprint/Topic/A/results.md'
    md.write_text(md.read_text(encoding='utf-8').replace('uses: []','status: complete\nuses: ["[[Topic/B/results#b]]"]\nlean: [{declaration: Test}]'),encoding='utf-8')
    link_workspace(tmp_path)
    w=Workspace(tmp_path)
    node=w.nodes['Topic/A/results#a']
    assert node.status=='complete' and node.bindings[0]['declaration']=='Test'
    assert 'Reviewed prose.' in node.body
    assert len(node.uses)==2
    assert (a/'main.tex').read_text(encoding='utf-8').count(r'\uses{Topic/B/results#b}')==1


def test_publish_failure_rolls_back_all_changed_files(tmp_path, monkeypatch):
    import qprint.cross_references as module
    paper(tmp_path,'A','2401.00001',r'\bpnode{a}\cite{B}',bbl('B','2401.00002'))
    paper(tmp_path,'B','2401.00002',r'\bpnode{b}B')
    before={p:p.read_bytes() for top in ('tex','blueprint') for p in (tmp_path/top).rglob('*') if p.is_file()}
    replace=module.os.replace
    calls=0
    def fail_second(source,target):
        nonlocal calls
        calls+=1
        if calls==2:
            raise OSError('publish failed')
        return replace(source,target)
    monkeypatch.setattr(module.os,'replace',fail_second)
    with pytest.raises(OSError,match='publish failed'):
        link_workspace(tmp_path)
    assert all(p.read_bytes()==content for p,content in before.items())


def test_import_automatically_links_new_and_existing_papers_in_both_directions(tmp_path):
    from qprint.importers import import_paper
    a=paper(tmp_path,'A','2401.00001',r'\bpnode{a}\cite[Thm 1]{B}',bbl('B','2401.00002'))
    source=r'''\documentclass{article}\newtheorem{thm}{Theorem}
\begin{document}\begin{thm}\label{thm:b}Use \cite{A}.\end{thm}
\begin{thebibliography}{9}\bibitem{A}Author. arXiv:2401.00001.\end{thebibliography}
\end{document}'''
    result=import_paper(tmp_path,'2401.00002v2','Topic/B','B',
                        downloader=lambda url:b'%PDF-1.7' if '/pdf/' in url else source.encode())
    links=result['cross_links']
    assert result['blueprint']['status']=='generated'
    assert links['status']=='completed' and links['links_added']==2 and not links['diagnostics']
    assert '#thm:b}' in (a/'main.tex').read_text(encoding='utf-8')
    assert r'\cite{A}\uses{Topic/A/index#index}' in (tmp_path/'tex/Topic/B/B.tex').read_text(encoding='utf-8')
    assert not Workspace(tmp_path).diagnostics


def test_linking_failure_does_not_discard_successful_download(tmp_path, monkeypatch):
    from qprint.importers import import_paper
    def fail(*args,**kwargs):
        raise OSError('linking unavailable')
    monkeypatch.setattr('qprint.cross_references.link_workspace',fail)
    result=import_paper(tmp_path,'2401.00002','Topic/B','B',auto_blueprint=False,
                        downloader=lambda url:b'%PDF-1.7' if '/pdf/' in url else br'\begin{document}B\end{document}')
    assert result['cross_links']['status']=='error'
    assert (tmp_path/result['tex']/'B.tex').is_file() and (tmp_path/result['pdf']).is_file()


def test_explicit_numbered_blueprint_title_and_after_cite_locator_are_idempotent(tmp_path):
    a=paper(tmp_path,'A','2401.00001',r'\bpnode{a}\cite{B}, Definition 2.3.',bbl('B','2401.00002'))
    paper(tmp_path,'B','2401.00002',r'\bpnode{Definition 2.3}A definition.')
    first=link_workspace(tmp_path)
    assert first['links_added']==1 and not first['diagnostics']
    assert r'\cite{B}\uses{Topic/B/results#Definition 2.3}, Definition' in (a/'main.tex').read_text(encoding='utf-8')
    assert not link_workspace(tmp_path)['files']


def test_existing_equivalent_markdown_link_is_not_duplicated(tmp_path):
    paper(tmp_path,'A','2401.00001',r'\bpnode{a}\cite{B}\uses{Topic/B/index#index}',bbl('B','2401.00002'))
    paper(tmp_path,'B','2401.00002',r'\bpnode{b}B')
    (tmp_path/'blueprint/Topic/B/index.md').write_text('# index\n',encoding='utf-8')
    md=tmp_path/'blueprint/Topic/A/results.md'
    text=md.read_text(encoding='utf-8').replace('uses: []','uses: ["[[Topic/B/index.md#index]]"]')
    md.write_text(text,encoding='utf-8')
    report=link_workspace(tmp_path)
    assert report['links_added']==0 and not report['files']
    assert md.read_text(encoding='utf-8')==text


@pytest.mark.parametrize('citation', [r'\cite{B}', r'\cite[Theorems 1--3]{B}'])
def test_canonical_index_preserves_legacy_node_and_has_directory(tmp_path, citation):
    a = paper(tmp_path, 'A', '2401.00001', r'\bpnode{a}' + citation, bbl('B', '2401.00002'))
    paper(tmp_path, 'B', '2401.00002', r'\bpnode{b}Result.')
    path = tmp_path / 'blueprint/Topic/B/index.md'
    original = '---\ntitle: Reviewed paper\n---\n\n# 文献索引\nReviewed index prose.\n'
    path.write_text(original, encoding='utf-8')
    report = link_workspace(tmp_path)
    assert report['links_added'] == 1
    assert r'\uses{Topic/B/index#index}' in (a / 'main.tex').read_text(encoding='utf-8')
    assert '# 文献索引\nReviewed index prose.' in path.read_text(encoding='utf-8')
    workspace = Workspace(tmp_path)
    assert not workspace.diagnostics
    assert workspace.nodes['Topic/B/index#index'].uses == ['[[Topic/B/results#b]]']
    assert 'data-milestone="Topic/B/results.md"' in workspace.detail('Topic/B/index#index')['body_html']
    assert not link_workspace(tmp_path)['files']
