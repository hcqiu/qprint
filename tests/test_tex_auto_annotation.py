import json

import pytest

from qprint.importers import import_paper
from qprint.paths import WorkspaceError
from qprint.tex import TexDocument
from qprint.tex_to_blueprint import annotate, annotate_sources, generate, validate
from qprint.workspace import Workspace


SOURCE = r'''\documentclass{article}
\title{A paper}\author{A. Author}
\newtheorem{theorem}{Theorem}
\begin{document}
\subsection{First}
Introduction to the result.
\begin{theorem}\label{thm:first}First result.
\begin{equation}\label{eq:nested}1=1\end{equation}
\end{theorem}
\begin{proof}By \ref{eq:nested}.\end{proof}
\subsection{Second}
Next result.
\begin{theorem}\label{thm:second}By \ref{thm:first}.\end{theorem}
\end{document}'''


def test_automatic_boundaries_nested_labels_proofs_and_idempotence():
    output, report = annotate_sources({'paper.tex': SOURCE})
    source = output['paper.tex']
    doc = TexDocument('paper.tex', source)
    assert [a['label'] for a in doc.anchors] == ['thm:first', 'thm:second']
    assert report['marked_nodes'] == 2 and report['marked_references'] == 2
    assert r'\bpnode{thm:first}' + '\n\nIntroduction' in source
    assert r'\ref{eq:nested}\uses{thm:first}' in source
    assert '\\bpdesc{' not in source
    assert '\\begin{proof}' in doc.fragment('thm:first')
    assert doc.annotations('thm:first')['descriptions'] == ['Introduction to the result.']
    again, report = annotate_sources(output)
    assert again == output
    assert report['marked_nodes'] == report['marked_references'] == 0


def test_existing_annotations_comments_verbatim_and_missing_labels():
    source = r'''\section{S}
% \begin{theorem}\label{fake}\end{theorem}
\verb|\begin{theorem}\label{fake2}\end{theorem}|
\bpnode{manual}\bpdesc{Manual description}
\begin{theorem}\label{original}Text.\end{theorem}
\begin{proof}\ref{original}\uses{manual}\end{proof}
\begin{theorem}No label.\end{theorem}'''
    output, report = annotate_sources({'paper.tex': source})
    assert output['paper.tex'] == source
    assert report['marked_nodes'] == report['marked_references'] == 0
    assert len(report['diagnostics']) == 1


def test_cross_file_references_and_explicit_description_priority(tmp_path):
    sources = {'main.tex': r'\documentclass{article}\begin{document}\input{a}\input{b}\end{document}',
               'a.tex': r'\subsection{A}Intro.\begin{theorem}\label{x}X.\end{theorem}',
               'b.tex': r'\subsection{B}\bpnode{y}\bpdesc{Explicit}\begin{theorem}\label{y}\ref{x}\end{theorem}'}
    output, _ = annotate_sources(sources)
    assert r'\ref{x}\uses{a.tex#x}' in output['b.tex']
    assert r'\providecommand{\bpnode}' in output['main.tex']
    (tmp_path / 'tex').mkdir()
    for path, content in output.items():
        (tmp_path / 'tex' / path).write_text(content, encoding='utf-8')
    report = generate(tmp_path, ['a.tex', 'b.tex'], 'Paper', title='Paper', authors=[], year='', keywords=[])
    assert not report['diagnostics']
    workspace = Workspace(tmp_path)
    x = next(n for n in workspace.nodes.values() if n.title == 'x')
    y = next(n for n in workspace.nodes.values() if n.title == 'y')
    assert y.uses == [f'[[{x.id}]]']
    assert y.body.strip() == 'Explicit'
    assert not validate(tmp_path, 'Paper', render_limit=0)['diagnostics']


def test_description_fallback_only_when_node_has_no_bpdesc():
    doc = TexDocument('p.tex', r'\bpnode{x}Intro\begin{theorem}X\end{theorem}'
                      r'\bpnode{x}\bpdesc{Explicit}\begin{proof}Proof\end{proof}')
    assert doc.annotations('x')['descriptions'] == ['Explicit']
    doc = TexDocument('p.tex', r'\bpnode{x}By \ref{y}\uses{y}.\begin{theorem}X\end{theorem}')
    assert doc.annotations('x')['descriptions'] == [r'By \ref{y}.']


def test_annotation_dry_run_and_invalid_input_do_not_write(tmp_path):
    (tmp_path / 'tex').mkdir()
    path = tmp_path / 'tex/p.tex'
    path.write_text(SOURCE, encoding='utf-8')
    assert annotate(tmp_path, ['p.tex'], dry_run=True)['marked_nodes'] == 2
    assert path.read_text(encoding='utf-8') == SOURCE
    (tmp_path / 'tex/bad.tex').write_text(r'\begin{theorem}', encoding='utf-8')
    with pytest.raises(WorkspaceError, match='未闭合'):
        annotate(tmp_path, ['p.tex', 'bad.tex'])
    assert path.read_text(encoding='utf-8') == SOURCE
    with pytest.raises(WorkspaceError):
        annotate(tmp_path, ['../outside.tex'])


@pytest.mark.parametrize('enabled', [True, False])
def test_paper_import_default_pipeline_and_opt_out(tmp_path, enabled):
    options = {} if enabled else {'auto_blueprint': False}
    result = import_paper(tmp_path, '2003.03925', 'Topology/Paper', 'Paper',
                          downloader=lambda url: b'%PDF-1.7' if '/pdf/' in url else SOURCE.encode(), **options)
    source = (tmp_path / result['tex'] / 'Paper.tex').read_text(encoding='utf-8')
    if not enabled:
        assert source == SOURCE
        assert result['blueprint']['status'] == 'not_run'
        assert not (tmp_path / 'blueprint').exists()
        return
    assert result['blueprint']['nodes'] == 2
    assert result['blueprint']['status'] == 'generated'
    report = json.loads((tmp_path / 'blueprint/Topology/Paper/generation-report.json').read_text(encoding='utf-8'))
    assert report['annotation']['marked_nodes'] == 2
    index = (tmp_path / 'blueprint/Topology/Paper/index.md').read_text(encoding='utf-8')
    assert 'A paper' in index and 'A. Author' in index and '2020' in index
    workspace = Workspace(tmp_path)
    assert len(workspace.nodes) == 2 and not workspace.diagnostics


def test_generation_failure_does_not_publish_download(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise WorkspaceError('generation failed')
    monkeypatch.setattr('qprint.tex_to_blueprint.generate', fail)
    with pytest.raises(WorkspaceError, match='generation failed'):
        import_paper(tmp_path, '2003.03925', 'Topology', 'Paper',
                     downloader=lambda url: b'%PDF-1.7' if '/pdf/' in url else SOURCE.encode())
    assert not (tmp_path / 'tex/Topology/Paper').exists()
    assert not (tmp_path / 'pdf/Topology/Paper.pdf').exists()
    assert not (tmp_path / 'blueprint/Topology/Paper').exists()


def test_existing_blueprint_is_protected_and_opt_out_allows_download(tmp_path):
    path = tmp_path / 'blueprint/Topology/Paper/index.md'
    path.parent.mkdir(parents=True)
    path.write_text('Existing', encoding='utf-8')
    download = lambda url: b'%PDF-1.7' if '/pdf/' in url else SOURCE.encode()
    with pytest.raises(WorkspaceError, match='Blueprint 目标已存在'):
        import_paper(tmp_path, '2003.03925', 'Topology', 'Paper', downloader=download)
    import_paper(tmp_path, '2003.03925', 'Topology', 'Paper', downloader=download, auto_blueprint=False)
    assert path.read_text(encoding='utf-8') == 'Existing'


def test_blueprint_publication_failure_rolls_back_pdf_and_tex(tmp_path, monkeypatch):
    from pathlib import Path
    rename = Path.rename
    def fail_blueprint(path, target):
        if target == tmp_path / 'blueprint/Topology/Paper':
            raise OSError('blueprint publication failed')
        return rename(path, target)
    monkeypatch.setattr(Path, 'rename', fail_blueprint)
    with pytest.raises(OSError, match='blueprint publication failed'):
        import_paper(tmp_path, '2003.03925', 'Topology', 'Paper',
                     downloader=lambda url: b'%PDF-1.7' if '/pdf/' in url else SOURCE.encode())
    assert not (tmp_path / 'pdf/Topology/Paper.pdf').exists()
    assert not (tmp_path / 'tex/Topology/Paper').exists()
    assert not (tmp_path / 'blueprint/Topology/Paper').exists()


def test_unlabelled_paper_is_downloaded_with_explicit_skip_report(tmp_path):
    source = r'\begin{document}\begin{theorem}Unlabelled\end{theorem}\end{document}'
    result = import_paper(tmp_path, '2003.03925', 'Topology', 'Paper',
                          downloader=lambda url: b'%PDF-1.7' if '/pdf/' in url else source.encode())
    assert result['blueprint']['status'] == 'skipped'
    assert result['blueprint']['annotation']['diagnostics']
    assert (tmp_path / result['tex'] / 'Paper.tex').read_text(encoding='utf-8') == source


def test_unlabelled_environments_use_rendered_counter_names():
    source = r'''\documentclass{article}
\newtheorem{thm}{Theorem}[section]
\newtheorem{lem}[thm]{Lemma}
\begin{document}
\section{One}\section{Two}
\begin{thm}\label{existing}First.\end{thm}
Introduction.
\begin{thm}[Named result]Second.\end{thm}
\begin{lem}Shared counter.\end{lem}
\begin{proof}Proof.\end{proof}
\setcounter{thm}{8}
\begin{thm}Ninth.\end{thm}
\section{Three}
\begin{thm}Reset.\end{thm}
\end{document}'''
    output, report = annotate_sources({'main.tex': source})
    doc = TexDocument('main.tex', output['main.tex'])
    assert [a['label'] for a in doc.anchors] == ['existing', 'Theorem 2.2', 'Lemma 2.3', 'Theorem 2.9', 'Theorem 3.1']
    assert doc.annotations('Theorem 2.2')['descriptions'] == ['Introduction.']
    assert '[Named result]' in doc.fragment('Theorem 2.2')
    assert not report['diagnostics']
    assert annotate_sources(output)[0] == output
    assert r'\qprintnameprobe' not in output['main.tex']


def test_unlabelled_starred_theorems_and_name_collisions_stay_separate():
    source = r'''\documentclass{article}
\newtheorem*{rem}{Remark}
\begin{document}
\bpnode{Remark}\begin{rem}Manual.\end{rem}
\begin{rem}Second.\end{rem}
\begin{rem}Third.\end{rem}
\end{document}'''
    output, report = annotate_sources({'main.tex': source})
    assert [a['label'] for a in TexDocument('main.tex', output['main.tex']).anchors] == ['Remark', 'Remark (2)', 'Remark (3)']
    assert not report['diagnostics']
    assert annotate_sources(output)[0] == output


def test_names_follow_include_order_and_preamble_from_loaded_main():
    sources = {
        'paper/main.tex': r'''\documentclass{article}
\input{preamble}
\begin{document}\section{One}\section{Two}\input{parts/b}\include{parts/a}\end{document}''',
        'paper/preamble.tex': r'\newtheorem{thm}{Theorem}[section]',
        'paper/parts/a.tex': r'\begin{thm}Second.\end{thm}',
        'paper/parts/b.tex': r'\begin{thm}First.\end{thm}',
    }
    output, report = annotate_sources(sources)
    assert r'\bpnode{Theorem 2.1}' in output['paper/parts/b.tex']
    assert r'\bpnode{Theorem 2.2}' in output['paper/parts/a.tex']
    assert not report['diagnostics']
    assert annotate_sources(output)[0] == output


def test_missing_includes_and_headingless_layout_do_not_invent_names():
    source = r'''\documentclass{article}
\newtheorem{thm}{Theorem}
\begin{document}\input{missing}\begin{thm}Unknown number.\end{thm}\end{document}'''
    output, report = annotate_sources({'main.tex': source})
    assert output['main.tex'] == source
    assert report['marked_nodes'] == 0 and report['diagnostics']
    source = r'\begin{document}\begin{itemize}\item A\end{itemize}\end{document}'
    output, report = annotate_sources({'main.tex': source})
    assert output['main.tex'] == source and report['diagnostics']


def test_import_generates_nodes_for_unlabelled_theorems(tmp_path):
    source = r'''\documentclass{article}
\newtheorem{thm}{Theorem}[section]
\begin{document}\section{One}\section{Two}
\subsection{Result}Intro.\begin{thm}A result.\end{thm}\end{document}'''
    result = import_paper(tmp_path, '2003.03925', 'Topology', 'Paper',
                          downloader=lambda url: b'%PDF-1.7' if '/pdf/' in url else source.encode())
    assert result['blueprint']['status'] == 'generated'
    workspace = Workspace(tmp_path)
    assert [n.title for n in workspace.nodes.values()] == ['Theorem 2.1']
    assert not workspace.diagnostics
    assert not validate(tmp_path, 'Topology/Paper', render_limit=0)['diagnostics']


def test_book_chapter_short_headings_and_equation_numberwithin():
    source = r'''\documentclass{book}
\newtheorem{thm}{Theorem}[section]
\numberwithin{equation}{section}
\begin{document}
\chapter[Short]{Long chapter}\section[Short]{Long section}
\begin{thm}Result.\end{thm}
\begin{equation}x=1\end{equation}
\begin{equation*}x=2\end{equation*}
\end{document}'''
    output, report = annotate_sources({'main.tex': source})
    assert [a['label'] for a in TexDocument('main.tex', output['main.tex']).anchors] == ['Theorem 1.1.1', 'Equation 1.1.1']
    assert len(report['diagnostics']) == 1 and 'equation*' in report['diagnostics'][0]


@pytest.mark.parametrize('declaration', [r'\newtheorem{thm}{Theorem}[section]',
                                      '\\newtheorem{thm}\n{Theorem}\n[section]'])
def test_name_declarations_are_independent_of_line_layout(declaration):
    source = (r'\documentclass{article}' + declaration + r'\begin{document}\section{One}\section{Two}'
              r'\begin{thm}Result.\end{thm}\end{document}')
    output, report = annotate_sources({'main.tex': source})
    assert r'\bpnode{Theorem 2.1}' in output['main.tex']
    assert not report['diagnostics']
