from pathlib import Path
import re
import subprocess

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from qprint.server import create_app
from qprint.tex import TexDocument, render_tex, tex_graphics
from qprint.tex_media import MediaError, TexMedia, drawing_document
from qprint.workspace import Workspace


def test_tikz_nodes_are_not_blueprint_annotations():
    source = r'''\bpnode{real}
\begin{tikzpicture}\node{A}; \node{B};\end{tikzpicture}
\node{legacy}Text
% \includegraphics{comment.png}
\verb|\includegraphics{literal.png}|
\includegraphics[width=.5\linewidth]{real.png}'''
    doc = TexDocument("main.tex", source)
    assert [anchor["label"] for anchor in doc.anchors] == ["real", "legacy"]
    assert [g["kind"] for g in tex_graphics(source)] == ["tikz", "image"]
    assert tex_graphics(source)[1]["value"] == "real.png"


def test_drawing_imports_needed_macros_and_libraries_only():
    document = drawing_document(r'\begin{tikzpicture}\node{$\Z$};\end{tikzpicture}',
                                r'\newcommand{\Z}{\mathbb{Z}}\newcommand{\unused}{\input{secret}}'
                                r'\usetikzlibrary{patterns,decorations.pathreplacing}')
    assert r'\providecommand{\Z}{\mathbb{Z}}' in document
    assert 'decorations.pathreplacing' in document
    assert 'unused' not in document and 'secret' not in document
    with pytest.raises(MediaError):
        drawing_document(r'\begin{tikzpicture}\input{secret}\end{tikzpicture}', '')
    with pytest.raises(MediaError):
        drawing_document(r'\begin{tikzpicture}\Z\end{tikzpicture}', r'\newcommand{\Z}{\input{secret}}')


def test_images_resolve_graphicspath_resize_cache_and_isolate_failures(tmp_path):
    folder = tmp_path / 'tex/paper/assets'
    folder.mkdir(parents=True)
    Image.new('RGB', (40, 20), 'red').save(folder / 'plot.png')
    media = TexMedia(tmp_path)
    source = r'Before\includegraphics[width=.5\linewidth]{plot}\includegraphics{missing.png}After'
    prepared, images, warnings = media.prepare(source, 'paper/main.tex', r'\graphicspath{{assets/}}')
    html, parse_warnings = render_tex(prepared, media=images)
    assert 'width:50%' in html and '<img' in html
    assert 'Before' in html and 'After' in html and '<details' in html
    assert len(warnings) == 1 and not parse_warnings
    key = re.search(r'/tex-media/([a-f0-9]+)', html)[1]
    target = media.cached_file(key)
    before = target.stat().st_mtime_ns
    media.prepare(source, 'paper/main.tex', r'\graphicspath{{assets/}}')
    assert target.stat().st_mtime_ns == before
    Image.new('RGB', (40, 20), 'blue').save(folder / 'plot.png')
    assert key not in media.prepare(source, 'paper/main.tex', r'\graphicspath{{assets/}}')[1][0]


@pytest.mark.parametrize('name', ['../../outside.png', 'C:/secret.png', '/secret.png', 'https://example.com/a.png'])
def test_images_cannot_read_outside_tex(tmp_path, name):
    media = TexMedia(tmp_path)
    with pytest.raises(MediaError):
        media.resolve_image(name, 'main.tex', '')
    with pytest.raises(FileNotFoundError):
        media.cached_file('../outside')


def test_media_inside_display_math_and_figure_caption():
    html, warnings = render_tex(r'''Before\[\qprintmedia{0}\]
\begin{figure}\centering\qprintmedia{1}\caption{A $x^2$ caption}\label{fig:a}\end{figure}After''',
                                media=['<img alt="diagram">', '<img alt="photo">'])
    assert not warnings
    assert html.count('<img') == 2
    assert '<figure' in html and '<figcaption>' in html and 'caption' in html
    assert 'tex-label' in html and 'qprintmedia' not in html
    assert 'Before' in html and 'After' in html


def test_graphics_do_not_break_reference_number_index():
    labels, warnings = render_tex(r'\begin{figure}\includegraphics{plot.pdf}\caption{Plot}\label{fig:a}\end{figure}'
                                  r'\begin{tikzpicture}\node{X};\end{tikzpicture}', index_only=True)
    assert not warnings and labels['fig:a']['text'] == '1'


def test_malformed_image_is_reported_without_crashing(tmp_path):
    source = r'Before\includegraphics{broken'
    prepared, _, warnings = TexMedia(tmp_path).prepare(source, 'main.tex', '')
    assert prepared == source and len(warnings) == 1


def test_tikz_timeout_is_local_and_compiler_is_offline_untrusted(tmp_path, monkeypatch):
    import qprint.tex_media as module
    monkeypatch.setattr(module, 'compiler_path', lambda: 'tectonic')
    def timeout(command, **kwargs):
        assert '--untrusted' in command and '--only-cached' in command
        assert kwargs['timeout'] == 30
        raise subprocess.TimeoutExpired(command, 30)
    monkeypatch.setattr(module.subprocess, 'run', timeout)
    _, images, warnings = TexMedia(tmp_path).prepare(r'Before\begin{tikzpicture}\node{A};\end{tikzpicture}After', 'main.tex', '')
    assert len(warnings) == 1 and '30' in warnings[0]
    assert '<details' in images[0]


def test_workspace_serves_rasterized_pdf_and_keeps_source(tmp_path):
    (tmp_path / 'tex').mkdir()
    (tmp_path / 'blueprint').mkdir()
    Image.new('RGB', (60, 30), 'white').save(tmp_path / 'tex/plot.pdf')
    (tmp_path / 'blueprint/A.md').write_text('# Node\n```qprint\ntex: main#node\n```', encoding='utf-8')
    source = r'\bpnode{node}Before\begin{figure}\includegraphics{plot.pdf}\caption{Plot}\end{figure}After'
    (tmp_path / 'tex/main.tex').write_text(source, encoding='utf-8')
    workspace = Workspace(tmp_path)
    content = workspace.detail('A#Node')['tex_content']
    assert r'\includegraphics{plot.pdf}' in content['source']
    assert not content['warnings'] and '<img' in content['html']
    url = re.search(r'src="([^"]+)"', content['html'])[1]
    with TestClient(create_app(tmp_path, runtime_root=tmp_path)) as client:
        response = client.get(url)
        assert response.status_code == 200
        assert response.headers['content-type'] == 'image/png'
        assert response.content.startswith(b'\x89PNG')
        assert client.get('/api/tex-media/nope.png').status_code == 404
