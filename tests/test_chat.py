import json
from pathlib import Path
import sys
import threading
import time

from fastapi.testclient import TestClient
import pytest

from qprint.chat import AgentSettings, ChatService, Message, NewSession
from qprint.chat_agents import Process, executable_command, replay_prompt, validate_base_url
from qprint.paths import WorkspaceError
from qprint.server import create_app
from qprint.workspace import Workspace


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / 'blueprint').mkdir()
    (tmp_path / 'blueprint/notes.md').write_text('# Lemma\nThe selected mathematical statement.\n', encoding='utf-8')
    return Workspace(tmp_path)


def new_session(service):
    return service.create(NewSession(anchor={'node': 'notes#Lemma', 'view': 'rendered',
                                             'quote': 'selected', 'start': 4, 'end': 12}, context='EXACT CLIPBOARD CONTEXT'))


def wait_for(service, identifier, predicate):
    end = time.monotonic() + 8
    while time.monotonic() < end:
        session = service.get(identifier)
        if predicate(session):
            return session
        time.sleep(.02)
    raise AssertionError(service.get(identifier))


def test_settings_secrets_and_workspace_isolation(workspace, tmp_path, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    service = ChatService(workspace, tmp_path)
    configured = service.configure(AgentSettings(selected='api', model='my-model', api_key='secret-for-test'))
    assert 'secret-for-test' not in json.dumps(configured)
    assert next(p for p in configured['profiles'] if p['id'] == 'api')['available']
    session = new_session(service)
    assert service.get(session['id'])['context'] == 'EXACT CLIPBOARD CONTEXT'
    assert b'secret-for-test' not in service.path.read_bytes()
    restarted = ChatService(workspace, tmp_path)
    assert restarted.get(session['id'])['anchor']['quote'] == 'selected'
    assert not next(p for p in restarted.settings()['profiles'] if p['id'] == 'api')['has_key']
    other_root = tmp_path / 'other'; other_root.mkdir()
    other = ChatService(Workspace(other_root), tmp_path)
    assert other.listing() == []


def test_chat_routes_require_token_and_validate_node(workspace, tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        assert client.post('/api/chat/discover').status_code == 403
        client.headers['x-qprint-token'] = client.get('/api/project').json()['token']
        assert client.post('/api/chat/discover', headers={'origin': 'https://foreign.example'}).status_code == 403
        assert client.put('/api/chat/settings', json={'selected': 'invalid'}).status_code == 400
        assert client.get('/api/chat/sessions/missing').status_code == 404
        assert client.post('/api/chat/sessions', json={'anchor': {'node': 'missing', 'view': 'rendered', 'quote': 'q', 'start': 0, 'end': 1}, 'context': 'context'}).status_code == 404


def test_turn_idempotency_busy_stop_and_persistence(workspace, tmp_path, monkeypatch):
    service = ChatService(workspace, tmp_path)
    service.configure(AgentSettings(selected='api', model='test', api_key='test'))
    seen = []
    def runner(profile, session, prompt, run):
        seen.append(prompt)
        run.append('partial answer')
        while not run.cancelled.wait(.01):
            pass
        raise InterruptedError()
    monkeypatch.setitem(__import__('qprint.chat', fromlist=['RUNNERS']).RUNNERS, 'api', runner)
    identifier = new_session(service)['id']
    message = Message(text='Why?', request_id='same-request')
    service.send(identifier, message)
    service.send(identifier, message)
    with pytest.raises(Exception, match='当前回答'):
        service.send(identifier, Message(text='Again', request_id='second'))
    service.stop(identifier)
    stopped = wait_for(service, identifier, lambda s: s['status'] == 'interrupted')
    assert len(stopped['messages']) == 2
    assert seen == ['EXACT CLIPBOARD CONTEXT\n\nFollow-up question:\nWhy?']
    assert stopped['messages'][-1]['text'] == 'partial answer'
    assert ChatService(workspace, tmp_path).get(identifier)['status'] == 'interrupted'


def test_restart_never_replays_running_turn(workspace, tmp_path):
    service = ChatService(workspace, tmp_path)
    session = new_session(service)
    session['status'] = 'running'
    service.write('session', session['id'], session)
    recovered = ChatService(workspace, tmp_path).get(session['id'])
    assert recovered['status'] == 'interrupted'
    assert recovered['messages'] == []


MOCK_AGENT = r'''
import json, sys
def send(value):
    print(json.dumps(value), flush=True)
for line in sys.stdin:
    request = json.loads(line)
    method = request.get('method')
    if not method:
        if request.get('id') == 'permission':
            assert request['result']['decision'] == 'decline'
            send({'method':'item/agentMessage/delta','params':{'itemId':'answer','delta':'Answer from mock'}})
            send({'method':'item/completed','params':{'item':{'id':'answer','type':'agentMessage','text':'Answer from mock'}}})
            send({'method':'turn/completed','params':{'turn':{'status':'completed'}}})
        continue
    if 'id' not in request:
        continue
    result = {}
    if method in ('thread/start','thread/resume'):
        assert request['params']['sandbox'] == 'read-only'
        result = {'thread':{'id':'native-session'}}
    send({'id':request['id'],'result':result})
    if method == 'turn/start':
        send({'id':'permission','method':'item/commandExecution/requestApproval','params':{'command':'test command'}})
'''


def test_codex_transport_stream_approval_and_native_resume(workspace, tmp_path, monkeypatch):
    from qprint.chat import Answer
    script = tmp_path / 'fake_agent.py'; script.write_text(MOCK_AGENT, encoding='utf-8')
    monkeypatch.setattr('qprint.chat.discover', lambda _: [sys.executable, str(script)])
    service = ChatService(workspace, tmp_path)
    identifier = new_session(service)['id']
    for turn in range(2):
        service.send(identifier, Message(text='Explain', request_id=str(turn)))
        waiting = wait_for(service, identifier, lambda s: s['status'] == 'waiting')
        assert waiting['remote_id'] == 'native-session'
        service.answer(identifier, Answer(request_id=waiting['pending']['id'], option='decline'))
        complete = wait_for(service, identifier, lambda s: s['status'] == 'idle')
        assert complete['messages'][-1]['text'] == 'Answer from mock'
    assert len(complete['messages']) == 4


def test_acp_stream_and_history_fallback(workspace, tmp_path, monkeypatch):
    script = tmp_path / 'acp.py'
    script.write_text('''import json,sys
for line in sys.stdin:
 r=json.loads(line); m=r.get('method'); result={}
 if m=='initialize': result={'agentCapabilities':{}}
 if m=='session/new': result={'sessionId':'acp-session'}
 if m=='session/prompt':
  print(json.dumps({'method':'session/update','params':{'update':{'sessionUpdate':'agent_message_chunk','content':{'type':'text','text':'ACP answer'}}}}),flush=True)
  result={'stopReason':'end_turn'}
 print(json.dumps({'id':r['id'],'result':result}),flush=True)
''', encoding='utf-8')
    monkeypatch.setattr('qprint.chat.discover', lambda _: [sys.executable, str(script)])
    service = ChatService(workspace, tmp_path)
    service.configure(AgentSettings(selected='hermes'))
    identifier = new_session(service)['id']
    for turn in range(2):
        service.send(identifier, Message(text=f'Question {turn}', request_id=str(turn)))
        complete = wait_for(service, identifier, lambda s: s['status'] == 'idle')
        assert complete['messages'][-1]['text'] == 'ACP answer'
    replay = replay_prompt(complete, 'unused')
    assert 'EXACT CLIPBOARD CONTEXT' in replay and 'Question 0' in replay and 'ACP answer' in replay


def test_api_stream_carries_context_and_history(workspace, tmp_path, monkeypatch):
    import httpx
    from qprint import chat_agents
    actual_client = httpx.AsyncClient
    requests = []
    def handle(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, text='data: {"choices":[{"delta":{"content":"answer"}}]}\n\ndata: [DONE]\n\n')
    monkeypatch.setattr(chat_agents.httpx, 'AsyncClient', lambda **kw: actual_client(transport=httpx.MockTransport(handle), **kw))
    service = ChatService(workspace, tmp_path)
    service.configure(AgentSettings(selected='api', model='configured-model', api_key='private-key'))
    identifier = new_session(service)['id']
    for turn in range(2):
        service.send(identifier, Message(text=f'Question {turn}', request_id=str(turn)))
        wait_for(service, identifier, lambda s: s['status'] == 'idle')
    assert requests[0]['messages'][0]['content'] == 'EXACT CLIPBOARD CONTEXT'
    assert requests[1]['messages'] == [{'role':'user','content':'EXACT CLIPBOARD CONTEXT'}, {'role':'user','content':'Question 0'}, {'role':'assistant','content':'answer'}, {'role':'user','content':'Question 1'}]


def test_api_validation_and_batch_launcher_rejection(tmp_path):
    for url in ('http://remote.example/v1', 'https://user:secret@example.com', 'https://example.com?key=secret'):
        with pytest.raises(WorkspaceError): validate_base_url(url)
    assert validate_base_url('http://127.0.0.1:8000/v1/') == 'http://127.0.0.1:8000/v1'
    script = tmp_path / 'untrusted.cmd'; script.write_text('@echo no')
    with pytest.raises(WorkspaceError, match='shell'):
        executable_command(str(script))


def test_api_stop_interrupts_waiting_for_headers(workspace, tmp_path, monkeypatch):
    import asyncio
    import httpx
    from qprint import chat_agents
    actual_client = httpx.AsyncClient
    entered = threading.Event()
    async def stalled(request):
        entered.set()
        await asyncio.sleep(60)
        return httpx.Response(200)
    monkeypatch.setattr(chat_agents.httpx, 'AsyncClient', lambda **kw: actual_client(transport=httpx.MockTransport(stalled), **kw))
    service = ChatService(workspace, tmp_path)
    service.configure(AgentSettings(selected='api', model='test', api_key='test'))
    identifier = new_session(service)['id']
    service.send(identifier, Message(text='Question', request_id='request'))
    assert entered.wait(3)
    before = time.monotonic()
    service.stop(identifier)
    wait_for(service, identifier, lambda s: s['status'] == 'interrupted')
    assert time.monotonic() - before < 2


def test_claude_structured_output_and_resume(workspace, tmp_path, monkeypatch):
    script = tmp_path / 'claude.py'
    script.write_text('''import json,sys
prompt=sys.stdin.read()
assert '--permission-mode' in sys.argv and 'dontAsk' in sys.argv
if '--resume' in sys.argv:
 assert sys.argv[sys.argv.index('--resume')+1]=='claude-session'
 assert prompt=='Follow up'
else:
 assert 'EXACT CLIPBOARD CONTEXT' in prompt
print(json.dumps({'type':'assistant','session_id':'claude-session','message':{'content':[{'type':'text','text':'Claude answer'}]}}),flush=True)
print(json.dumps({'type':'result','result':'Claude answer','is_error':False}),flush=True)
''', encoding='utf-8')
    monkeypatch.setattr('qprint.chat.discover', lambda _: [sys.executable, str(script)])
    service = ChatService(workspace, tmp_path)
    service.configure(AgentSettings(selected='claude'))
    identifier = new_session(service)['id']
    for index, message in enumerate(['First question', 'Follow up']):
        service.send(identifier, Message(text=message, request_id=str(index)))
        completed = wait_for(service, identifier, lambda s: s['status'] == 'idle')
        assert completed['remote_id'] == 'claude-session'
        assert completed['messages'][-1]['text'] == 'Claude answer'
