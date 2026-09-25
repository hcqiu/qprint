import json
from pathlib import Path, PureWindowsPath
import shutil
import subprocess
import sys

from fastapi.testclient import TestClient
import pytest

from qprint.agent_paths import relative_output
from qprint.knowledge import KnowledgeIndexer
from qprint.knowledge.runtime import active_runtime
from qprint.server import create_app


def make_workspace(root, *, indexed=True):
    (root / 'blueprint').mkdir(parents=True)
    (root / 'tex').mkdir()
    (root / 'blueprint/Note.md').write_text('# A\n```qprint\ntex: main.tex#a\n```\nA summary.\n# B\n```qprint\ntex: main.tex#b\n```\nB summary.\n', encoding='utf-8')
    (root / 'tex/main.tex').write_text('\\bpnode{a}\nAlpha.\n\\bpnode{b}\nBeta.\n', encoding='utf-8')
    if indexed:
        KnowledgeIndexer(root).update()


def query(root, *arguments):
    p = subprocess.run([sys.executable, '-m', 'qprint', 'agent', *arguments], cwd=root, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    assert str(root) not in p.stdout and root.as_posix() not in p.stdout
    return json.loads(p.stdout)


def focus(client, node, session, **extra):
    token = client.get('/api/project').json()['token']
    response = client.post('/api/navigator/focus', json={'node_id': node, 'session': session, **extra}, headers={'X-Qprint-Token': token})
    assert response.status_code == 200, response.text
    return response.json()


def test_ui_runtime_zero_argument_cli_and_relocation(tmp_path):
    root = tmp_path / 'Qprint'
    make_workspace(root / 'foo')
    make_workspace(root / 'bar')
    with TestClient(create_app(root / 'foo', runtime_root=root)) as foo, TestClient(create_app(root / 'bar', runtime_root=root)) as bar:
        focus(foo, 'Note#A', 'page-a', document='tex/main.tex', selection='Alpha')
        state = query(root, 'state')
        assert state['workspace'] == 'foo' and state['session'] == 'page-a'
        assert state['current_node']['id'] == 'main/a'
        assert state['current_document'] == 'foo/tex/main.tex'
        assert state['selection'] == 'Alpha'
        assert state['path_base'] == 'qprint'
        source = query(root, 'source', 'main/a')
        assert source['fragments'][0]['file'] == 'foo/tex/main.tex'
        query(root, 'open', 'main/b')
        assert query(root, 'state')['current_node']['id'] == 'main/a'
        focus(foo, 'Note#B', 'page-b', view='edit', document='blueprint/Note.md')
        assert query(root, 'state')['session'] == 'page-b'
        assert query(root, 'state')['current_document'] == 'foo/blueprint/Note.md'
        assert query(root, 'state', '--session', 'page-a')['current_node']['id'] == 'main/a'
        focus(bar, 'Note#A', 'another-workspace')
        assert query(root, 'state')['workspace'] == 'bar'
        focus(bar, None, 'another-workspace', view='paper', document='tex/main.tex')
        state = query(root, 'state')
        assert state['current_node'] is None and state['current_document'] == 'bar/tex/main.tex'
    # Moving the entire Qprint folder requires no edits to state or commands.
    moved = tmp_path / 'Moved Qprint'
    shutil.copytree(root, moved)
    assert query(moved, 'state') == state
    runtime = active_runtime(moved)
    assert runtime == {'version': 1, 'workspace': 'bar', 'session': 'another-workspace'}


def test_relative_overrides_and_no_absolute_error_leak(tmp_path):
    make_workspace(tmp_path / 'foo')
    assert query(tmp_path, 'state', '--workspace', 'foo')['workspace'] == 'foo'
    for value in [str((tmp_path / 'foo').resolve()), '../elsewhere', 'X:/private/folder']:
        p = subprocess.run([sys.executable, '-m', 'qprint', 'agent', 'state', '--workspace', value], cwd=tmp_path, capture_output=True, text=True)
        assert p.returncode != 0
        assert value not in p.stderr
    state = query(tmp_path, 'state')
    assert state['workspace'] == '.' and state['current_node'] is None
    assert state['index_status'] == 'unavailable'
    assert not (tmp_path / '.qprint').exists()


def test_shell_in_another_folder_does_not_attach_to_ui(tmp_path):
    opened = tmp_path / 'Qprint-opened'
    other = tmp_path / 'Qprint-other'
    make_workspace(opened / 'examples/demo', indexed=False)
    other.mkdir()
    with TestClient(create_app(opened / 'examples/demo', runtime_root=opened)) as client:
        focus(client, 'Note#A', 'browser', document='tex/main.tex')
        for args in [('state',), ('call', 'kb_state'),
                     ('batch', '--calls', '[{"tool":"kb_state","arguments":{}}]')]:
            result = query(other, *args)
            missing = result['results'][0]['result'] if args[0] == 'batch' else result
            assert missing['runtime_status'] == 'not_published'
            assert missing['current_node'] is None
            assert 'same Qprint folder' in missing['next_action']
        connected = query(opened, 'state')
        assert connected['runtime_status'] == 'published'
        assert connected['current_node']['id'] == 'main/a'
        # Missing runtime is distinct from a missing index in the right folder.
        (opened / 'examples/demo/.qprint/index/knowledge.sqlite').unlink()
        unavailable = query(opened, 'state')
        assert unavailable['runtime_status'] == 'published'
        assert unavailable['index_status'] == 'unavailable'
        assert 'UI runtime was found' in unavailable['next_action']
    assert not (other / '.qprint').exists()


def test_first_launch_bootstraps_state_for_new_processes(tmp_path):
    root = tmp_path / 'Qprint'
    workspace = root / 'examples/demo'
    make_workspace(workspace, indexed=False)
    # No index, runtime file, inherited shell variables or explicit session.
    for args in [('state',), ('call', 'kb_state'),
                 ('batch', '--calls', '[{"tool":"kb_state","arguments":{}}]')]:
        result = query(root, *args)
        state = result['results'][0]['result'] if args[0] == 'batch' else result
        assert state['index_status'] == 'unavailable'
    assert not (root / '.qprint').exists()
    with TestClient(create_app(workspace, runtime_root=root)) as client:
        # Host publishes even before the first page or node is opened.
        initial = query(root, 'state')
        assert initial['workspace'] == 'examples/demo'
        assert initial['index_status'] == 'ready'
        assert initial['current_node'] is None
        assert client.get('/api/project').json()['navigator_available']
        focus(client, 'Note#A', 'new-tab', document='tex/main.tex', selection='Alpha')
        for _ in range(2):
            state = query(root, 'state')
            assert state['current_node']['id'] == 'main/a'
            assert state['selection'] == 'Alpha'
            assert state['session'] == 'new-tab'
        assert query(root, 'source', 'main/a')['fragments'][0]['file'] == 'examples/demo/tex/main.tex'
        # Loss of the index must not hide an already published UI snapshot.
        (workspace / '.qprint/index/knowledge.sqlite').unlink()
        state = query(root, 'state')
        assert state['index_status'] == 'unavailable' and not state['focus_verified']
        assert state['current_node'] == {'id': 'main/a'}
        assert state['current_document'] == 'examples/demo/tex/main.tex'
        assert state['selection'] == 'Alpha'
    # Restart repairs the index and does not claim that an old page is active.
    with TestClient(create_app(workspace, runtime_root=root)):
        state = query(root, 'state')
        assert state['index_status'] == 'ready' and state['current_node'] is None


def test_new_powershell_local_python_follows_ui(local_python_shell):
    root, run_shell = local_python_shell
    workspace = root / 'examples/demo'
    make_workspace(workspace, indexed=False)

    def new_shell():
        result = run_shell(r'.\.conda\python.exe -m qprint agent state; exit $LASTEXITCODE')
        assert result.returncode == 0, result.stderr
        assert str(root) not in result.stdout
        return json.loads(result.stdout)

    assert new_shell()['index_status'] == 'unavailable'
    with TestClient(create_app(workspace, runtime_root=root)) as client:
        for node, expected, session in [('Note#A', 'main/a', 'first'), ('Note#B', 'main/b', 'second')]:
            focus(client, node, session, document='tex/main.tex', selection=expected)
            state = new_shell()
            assert state['workspace'] == 'examples/demo'
            assert state['session'] == session
            assert state['current_node']['id'] == expected
            assert state['current_document'] == 'examples/demo/tex/main.tex'
            assert state['selection'] == expected


def test_redaction_keeps_relative_source_and_hides_external_runtime(tmp_path):
    local = str(tmp_path / 'foo/a.tex')
    result = relative_output({'source': local, 'error': 'open X:/private/cache/file failed'}, tmp_path)
    assert result['source'].replace('\\', '/') == './foo/a.tex'
    assert 'X:' not in result['error']


def test_tampered_runtime_cannot_escape_qprint(tmp_path):
    folder = tmp_path / '.qprint/runtime'
    folder.mkdir(parents=True)
    (folder / 'navigation.json').write_text(json.dumps({'version': 1, 'workspace': '../outside', 'session': 'x'}))
    with pytest.raises(ValueError, match='Invalid Qprint runtime'):
        active_runtime(tmp_path)
