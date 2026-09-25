import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
import pytest

from qprint.knowledge import KnowledgeIndexer, KnowledgeNavigator
from qprint.knowledge.tools import call_tool
from qprint.paths import WorkspaceError
from qprint.server import create_app


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / 'blueprint').mkdir()
    (tmp_path / 'blueprint/One.md').write_text('# First\nOne.\n# Second\nTwo.\n', encoding='utf-8')
    KnowledgeIndexer(tmp_path).update()
    return tmp_path


def test_focus_history_isolation_and_deleted_focus(workspace):
    with KnowledgeNavigator(workspace, session='page') as nav:
        assert nav.kb_state()['current_node'] is None
        assert not (workspace / '.qprint/state').exists()
        nav.set_focus('One#First', selection='One.', origin='browser')
        nav.kb_source('One#Second', source='md')
        state = nav.kb_state(limit=1)
        assert state['current_node']['id'] == 'One#First'
        assert state['selection'] == 'One.'
        assert state['recent_nodes'][0]['id'] == 'One#Second'
        assert state['recent_truncated']
        assert nav.kb_state()['focus_updated_ns'] == state['focus_updated_ns']
    with KnowledgeNavigator(workspace, session='other') as nav:
        assert nav.kb_state()['current_node'] is None
        assert nav.kb_state()['recent_nodes'] == []
        nav.kb_open('One#Second')
        assert nav.kb_state()['focus_origin'] == 'navigator'
    (workspace / 'blueprint/One.md').write_text('# Second\nTwo.\n', encoding='utf-8')
    KnowledgeIndexer(workspace).update()
    with KnowledgeNavigator(workspace, session='page') as nav:
        state = nav.kb_state()
        assert state['current_node'] is None and state['stale_focus']
        assert state['stale_node_id'] == 'One#First'
        assert [r['id'] for r in state['recent_nodes']] == ['One#Second']
        nav.set_focus(None, view='references')
        assert nav.kb_state()['current_node'] is None
        assert not nav.kb_state()['stale_focus']


def test_queries_readonly_and_cwd_independent(workspace):
    path = workspace / '.qprint/index/knowledge.sqlite'
    before = path.read_bytes()
    with KnowledgeNavigator(workspace) as nav:
        with pytest.raises(sqlite3.OperationalError, match='readonly'):
            nav.db.execute("DELETE FROM nodes")
        nav.kb_open('One#First')
        nav.kb_source('One#First', source='md')
        with pytest.raises(WorkspaceError):
            call_tool(nav, 'set_focus', {'node': 'One#Second'})
    for arguments in [[], ['--workspace', '.']]:
        result = subprocess.run([sys.executable, '-m', 'qprint', 'agent', 'state', *arguments], cwd=workspace, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)['current_node']['id'] == 'One#First'
    assert path.read_bytes() == before
    assert not Path(str(path) + '-wal').exists()
    assert not Path(str(path) + '-shm').exists()


def test_concurrent_sessions_do_not_mix_or_lock_index(workspace):
    def run(i):
        with KnowledgeNavigator(workspace, session=str(i)) as nav:
            nav.set_focus('One#First' if i % 2 else 'One#Second')
            return nav.kb_state()['current_node']['id']
    with ThreadPoolExecutor(max_workers=6) as pool:
        assert list(pool.map(run, range(12))) == ['One#First' if i % 2 else 'One#Second' for i in range(12)]


def test_history_write_failure_does_not_block_reading(workspace, monkeypatch):
    with KnowledgeNavigator(workspace) as nav:
        nav.set_focus('One#First')
        def denied(*args, **kwargs):
            raise sqlite3.OperationalError('attempt to write a readonly database')
        monkeypatch.setattr(nav.state, 'write', denied)
        assert 'state_warning' in nav.kb_open('One#Second')
        source = nav.kb_source('One#Second', source='md')
        assert 'Two.' in source['fragments'][0]['text']
        assert 'state_warning' in source
        assert nav.kb_state()['current_node']['id'] == 'One#First'
        for budget in [128, 300, 6000]:
            from qprint.knowledge.index import packed
            assert len(packed(nav.kb_context('One#Second', budget)).encode('utf-8')) <= budget


def test_browser_focus_api_shared_with_cli_and_guarded(workspace):
    with TestClient(create_app(workspace)) as client:
        project = client.get('/api/project').json()
        assert project['navigator_available']
        payload = {'session': 'browser', 'node_id': 'One#First', 'selection': 'One.'}
        assert client.post('/api/navigator/focus', json=payload).status_code == 403
        headers = {'X-Qprint-Token': project['token']}
        assert client.post('/api/navigator/focus', json=payload, headers={**headers, 'Origin': 'http://elsewhere'}).status_code == 403
        result = client.post('/api/navigator/focus', json=payload, headers=headers)
        assert result.status_code == 200, result.text
        with KnowledgeNavigator(workspace, session='browser') as nav:
            assert nav.kb_state()['current_node']['id'] == 'One#First'
            nav.kb_open('One#Second')
        assert client.get('/api/navigator/state?session=browser').json()['current_node']['id'] == 'One#First'
        assert client.post('/api/navigator/focus', json={**payload, 'node_id': 'Unknown'}, headers=headers).status_code == 404
        assert client.get('/api/navigator/state?session=other').json()['current_node'] is None
        assert client.post('/api/navigator/focus', json={**payload, 'node_id': None, 'view': 'paper', 'selection': ''}, headers=headers).json()['current_node'] is None


def test_batch_reports_each_error_without_exposing_mutations(workspace):
    calls = [{'tool': 'kb_open', 'arguments': {'node': 'One#First'}},
             {'tool': 'set_focus', 'arguments': {'node': 'One#Second'}},
             {'tool': 'kb_state', 'arguments': {}}]
    result = subprocess.run([sys.executable, '-m', 'qprint', 'agent', 'batch', '--calls', json.dumps(calls)], cwd=workspace, capture_output=True, text=True)
    assert result.returncode == 1
    results = json.loads(result.stdout)['results']
    assert 'error' in results[1]
    assert results[2]['result']['current_node']['id'] == 'One#First'
