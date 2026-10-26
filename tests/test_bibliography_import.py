from fastapi.testclient import TestClient
import pytest

from qprint.bibliography import reference_arxiv_id
from qprint.server import create_app
from qprint.workspace import Workspace


@pytest.mark.parametrize(('html', 'identifier'), [
    ('<p>arXiv preprint arXiv:1912.09029.</p>', '1912.09029'),
    ('<p>arXiv:<em>2506.00824v2</em>, 2025.</p>', '2506.00824v2'),
    ('arXiv:math.GT/0309136', 'math.GT/0309136'),
    ('<a href="https://arxiv.org/abs/1912.09029">Paper</a>', '1912.09029'),
    ('<a href="http://export.arxiv.org/pdf/math/0309136v1.pdf">PDF</a>', 'math/0309136v1'),
    ('<a href="https://www.arxiv.org/pdf/1912.09029.pdf?download=1">PDF</a>', '1912.09029'),
    ('https://arxiv.org/abs/1912.09029.', '1912.09029'),
    ('<a href="https://doi.org/10.48550/arXiv.1912.09029">DOI</a>', '1912.09029'),
    ('arXiv:1912.09029 <a href="https://arxiv.org/abs/1912.09029">Same</a>', '1912.09029'),
    ('arXiv:1912.09029 and arXiv:2506.00824', None),
    ('<a href="https://arxiv.org.example.com/abs/1912.09029">Paper</a>', None),
    ('<p>Journal 1912.09029</p>', None),
    ('<p>arXiv:1912.090291</p>', None),
    ('<p>arXiv:1912.09029v0</p>', None),
])
def test_arxiv_reference_detection(html, identifier):
    assert reference_arxiv_id(html) == identifier


def test_references_api_supplies_arxiv_and_project_context_for_nested_chapters(tmp_path):
    tex = tmp_path / 'tex/Topology/Ren25'
    blueprint = tmp_path / 'blueprint/Topology/Ren25'
    (tex / 'chapters').mkdir(parents=True)
    blueprint.mkdir(parents=True)
    (blueprint / 'index.md').write_text('# Ren25\n', encoding='utf-8')
    (blueprint / 'intro.md').write_text('# Result\n```qprint\ntex: Topology/Ren25/chapters/intro#result\n```', encoding='utf-8')
    (tex / 'chapters/intro.tex').write_text(r'\bpnode{result}\cite{budney2019knotted}', encoding='utf-8')
    (tex / 'main.tex').write_text(r'''\input{chapters/intro}
\begin{thebibliography}{9}
\bibitem[BG19]{budney2019knotted}Ryan Budney, David Gabai. arXiv:1912.09029.
\end{thebibliography}''', encoding='utf-8')
    workspace = Workspace(tmp_path)
    assert workspace.bibliography('Topology/Ren25/main.tex')['project_path'] == 'Topology/Ren25'
    with TestClient(create_app(tmp_path)) as client:
        data = client.get('/api/references', params={'path':'Topology/Ren25/chapters/intro.tex'}).json()
    assert data['project_path'] == 'Topology/Ren25'
    assert data['entries'][0]['key'] == 'budney2019knotted'
    assert data['entries'][0]['label'] == 'BG19'
    assert data['entries'][0]['arxiv_id'] == '1912.09029'
