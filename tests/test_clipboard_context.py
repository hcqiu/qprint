from fastapi.testclient import TestClient

from qprint.blueprint import Node
from qprint.clipboard_context import build_contexts, MAX_DEPENDENCY_CHARS
from qprint.server import create_app
from qprint.tex import TexDocument


def test_context_keeps_complete_tex_and_only_direct_dependencies():
    nodes = {
        'P#A': Node('P#A', 'A', 'P.md', 1, 'A summary', tex='P#a',
                    uses=['[[#B]]', '[[#B]]', '[[#Missing]]'], inspired_by=['[[#C]]']),
        'P#B': Node('P#B', 'B', 'P.md', 2, 'B summary', tex='P#b', uses=['[[#C]]']),
        'P#C': Node('P#C', 'C', 'P.md', 3, 'C summary'),
        'P#D': Node('P#D', 'D', 'P.md', 4, 'D summary', tex='P#d'),
    }
    document = TexDocument('P.tex', '\\bpnode{a}\n\\uses{b,d}\n' + 'Full proof.\n' * 2000
                           + '\\bpnode{b}\n\\bpdesc{B TeX description}\nDependency proof not copied.\n'
                           + '\\bpnode{d}\nD proof.')
    bundles = build_contexts(nodes, {'P#A': ('P.tex', 'a'), 'P#B': ('P.tex', 'b'),
                                     'P#D': ('P.tex', 'd')}, {'P.tex': document})
    context = bundles['P#A']
    assert context['tex'] == document.fragment('a')
    assert len(context['tex']) > 20000
    assert [d['node'] for d in context['dependencies']] == ['P#B', 'P#D']
    assert context['dependencies'][0]['description'] == 'B TeX description'
    assert all('tex' not in d for d in context['dependencies'])
    assert context['unresolved_dependencies'] == ['[[#Missing]]']
    assert context['dependencies_omitted'] == 0
    assert bundles['P#C']['tex'] is None


def test_dependency_budget_and_cycles_are_bounded():
    nodes = {f'P#{i}': Node(f'P#{i}', str(i), 'P.md', i + 1, 'summary ' * 1000,
                           uses=[f'[[#{j}]]' for j in range(50)]) for i in range(50)}
    context = build_contexts(nodes, {}, {})['P#0']
    assert len(context['dependencies']) <= 20
    assert sum(len(value) for d in context['dependencies'] for value in d.values()) <= MAX_DEPENDENCY_CHARS
    assert context['dependencies_omitted'] + len(context['dependencies']) == 49
    assert all(d['node'] != 'P#0' for d in context['dependencies'])


def test_context_is_prebuilt_and_refreshes_after_save_reload_and_deletion(tmp_path, monkeypatch):
    (tmp_path / 'blueprint').mkdir()
    (tmp_path / 'tex').mkdir()
    markdown = '# A\n```qprint\ntex: P#a\nuses: ["[[#B]]"]\n```\nA summary\n# B\nOld summary\n'
    (tmp_path / 'blueprint/P.md').write_text(markdown, encoding='utf-8')
    (tmp_path / 'tex/P.tex').write_text('\\bpnode{a}\nOriginal TeX.', encoding='utf-8')
    # No Navigator index/startup is needed for clipboard context.
    app = create_app(tmp_path)
    client = TestClient(app)
    client.headers['x-qprint-token'] = client.get('/api/project').json()['token']
    original = client.get('/api/context', params={'id': 'P#A'}).json()
    assert original['tex'] == 'Original TeX.'
    assert original['dependencies'][0]['description'] == 'Old summary'
    with monkeypatch.context() as patch:
        patch.setattr(TexDocument, 'fragment', lambda *a: (_ for _ in ()).throw(AssertionError('recomputed')))
        assert client.get('/api/context', params={'id': 'P#A'}).json() == original
    assert client.get('/api/node', params={'id': 'P#A'}).json()['copy_context'] == original
    doc = client.get('/api/document', params={'path': 'P.md'}).json()
    assert client.put('/api/document', json={**doc, 'text': markdown.replace('Old summary', 'New summary')}).status_code == 200
    assert client.get('/api/context', params={'id': 'P#A'}).json()['dependencies'][0]['description'] == 'New summary'
    (tmp_path / 'tex/P.tex').write_text('\\bpnode{a}\nUpdated TeX.', encoding='utf-8')
    assert client.post('/api/reload').status_code == 200
    assert client.get('/api/context', params={'id': 'P#A'}).json()['tex'] == 'Updated TeX.'
    (tmp_path / 'blueprint/P.md').unlink()
    assert client.post('/api/reload').status_code == 200
    assert client.get('/api/context', params={'id': 'P#A'}).status_code == 404
    assert client.get('/api/context', params={'id': '../secret'}).status_code == 404
