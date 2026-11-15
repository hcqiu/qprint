from pathlib import Path
import threading

import httpx
import pytest

from qprint import chat_models as models
from qprint.chat import AgentSettings, ChatService, Message, ModelQuery
from qprint.chat_agents import run_codex, run_claude, run_acp, run_api
from qprint.paths import WorkspaceError
from test_chat import new_session, wait_for, workspace


CATALOG = {"models": [models.model('fast', 'Fast', ['low', 'high'], 'low'),
                      models.model('deep', 'Deep', ['medium', 'max'], 'medium')],
           "default_model": 'fast', "default_effort": 'high', "error": ''}


def test_selection_validation_and_model_specific_defaults():
    assert models.resolve_selection(CATALOG, '', '') == ('fast', 'high')
    assert models.resolve_selection(CATALOG, 'deep', '') == ('deep', 'medium')
    assert models.resolve_selection(CATALOG, 'deep', 'max') == ('deep', 'max')
    with pytest.raises(WorkspaceError): models.resolve_selection(CATALOG, 'deep', 'high')
    with pytest.raises(WorkspaceError): models.resolve_selection(CATALOG, 'removed', '')


def test_catalog_cache_refresh_and_key_redaction(workspace, tmp_path, monkeypatch):
    service = ChatService(workspace, tmp_path)
    service.configure(AgentSettings(selected='api', model='fast', api_key='private-token'))
    identifier = new_session(service)['id']
    calls = []
    def discover(profile, cwd, selected):
        calls.append(selected)
        return CATALOG.copy()
    monkeypatch.setattr('qprint.chat.discover_models', discover)
    assert service.models(identifier, ModelQuery())['default_model'] == 'fast'
    service.models(identifier, ModelQuery(model='deep'))
    assert len(calls) == 1
    service.models(identifier, ModelQuery(refresh=True))
    assert len(calls) == 2
    service.configure(AgentSettings(selected='api', model='deep'))
    service.models(identifier, ModelQuery())
    assert len(calls) == 3
    def failure(*args): raise ValueError('server failure private-token')
    monkeypatch.setattr('qprint.chat.discover_models', failure)
    result = service.models(identifier, ModelQuery(refresh=True))
    assert 'private-token' not in str(result) and '[redacted]' in result['error']
    assert result['models'][0]['id'] == 'deep'


def test_api_key_alone_enables_model_picker(workspace, tmp_path, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    service = ChatService(workspace, tmp_path)
    settings = service.configure(AgentSettings(selected='api', api_key='test'))
    assert next(p for p in settings['profiles'] if p['id']=='api')['available']
    identifier = new_session(service)['id']
    monkeypatch.setattr('qprint.chat.discover_models', lambda *args: {'models':CATALOG['models'],'default_model':'','default_effort':''})
    assert service.models(identifier, ModelQuery())['requires_model']
    with pytest.raises(WorkspaceError, match='选择模型'):
        service.send(identifier, Message(text='question', request_id='none', model='', effort=''))


def test_choices_persist_per_session_and_per_message(workspace, tmp_path, monkeypatch):
    service = ChatService(workspace, tmp_path)
    service.configure(AgentSettings(selected='api', model='fast', api_key='test'))
    monkeypatch.setattr('qprint.chat.discover_models', lambda *args: CATALOG.copy())
    seen = []
    def runner(profile, session, prompt, run):
        seen.append((profile['model'], profile['effort']))
        run.append('answer')
    monkeypatch.setitem(__import__('qprint.chat', fromlist=['RUNNERS']).RUNNERS, 'api', runner)
    identifier = new_session(service)['id']
    service.send(identifier, Message(text='one', request_id='1', model='deep', effort='max'))
    wait_for(service, identifier, lambda s: s['status'] == 'idle')
    service.send(identifier, Message(text='two', request_id='2', model='fast', effort='low'))
    wait_for(service, identifier, lambda s: s['status'] == 'idle')
    service.send(identifier, Message(text='three', request_id='3', model='', effort=''))
    result = wait_for(service, identifier, lambda s: s['status'] == 'idle')
    assert seen == [('deep','max'), ('fast','low'), ('fast','high')]
    assert [(m['model'],m['effort']) for m in result['messages'] if m['role']=='assistant'] == seen
    assert result['selection'] == {'model':'', 'effort':''}
    assert ChatService(workspace, tmp_path).get(identifier)['messages'] == result['messages']
    with pytest.raises(WorkspaceError):
        service.send(identifier, Message(text='bad', request_id='4', model='deep', effort='low'))
    assert len(service.get(identifier)['messages']) == 6


class FakeProcess:
    instances = []
    def __init__(self, command, cwd):
        self.command, self.calls, self.sent, self.closed = command, [], [], False
        self.instances.append(self)
    def close(self): self.closed = True
    def send(self, data): self.sent.append(data)
    def rpc(self, method, params, run, **kwargs):
        self.calls.append((method, params))
        if method == 'model/list':
            if not params.get('cursor'):
                return {'data':[{'id':'id-fast','model':'fast','isDefault':True,'supportedReasoningEfforts':[{'reasoningEffort':'low'}], 'defaultReasoningEffort':'low'}], 'nextCursor':'next'}
            return {'data':[{'id':'deep','supportedReasoningEfforts':[{'reasoningEffort':'max'}], 'defaultReasoningEffort':'max'}]}
        if method == 'config/read': return {'config':{'model':'deep','model_reasoning_effort':'max'}}
        if method in {'thread/start','thread/resume'}: return {'thread':{'id':'thread'}}
        return {}
    def next(self, *args): return {'method':'turn/completed','params':{'turn':{'status':'completed'}}}


class RunStub:
    cwd = Path.cwd()
    cancelled = threading.Event()
    def remote(self, identifier): pass
    def context_sent(self): pass
    def event(self, proc, event): pass
    def append(self, text): pass


def test_codex_catalog_pagination_and_turn_overrides_on_resume(monkeypatch):
    monkeypatch.setattr(models, 'Process', FakeProcess)
    result = models.codex_models({'resolved':['codex']}, Path.cwd())
    assert [m['id'] for m in result['models']] == ['fast','deep']
    assert result['default_model'] == 'deep' and result['default_effort'] == 'max'
    assert FakeProcess.instances[-1].closed
    monkeypatch.setattr('qprint.chat_agents.Process', FakeProcess)
    run_codex({'resolved':['codex'], 'model':'deep','effort':'max'}, {'remote_id':'existing'}, 'question', RunStub())
    calls = dict(FakeProcess.instances[-1].calls)
    assert calls['thread/resume']['threadId'] == 'existing'
    assert calls['turn/start']['model'] == 'deep' and calls['turn/start']['effort'] == 'max'


def acp_info(selected='fast'):
    return {'sessionId':'s', 'configOptions':[
        {'id':'model-choice','category':'model','type':'select','currentValue':selected,
         'options':[{'group':'all','options':[{'value':'fast','name':'Fast'},{'value':'deep','name':'Deep'}]}]},
        {'id':'thinking','category':'thought_level','type':'select','currentValue':'max' if selected=='deep' else 'low',
         'options':[{'value':level,'name':level} for level in (['medium','max'] if selected=='deep' else ['low','high'])]}]}


class AcpProcess(FakeProcess):
    def rpc(self, method, params, run, **kwargs):
        self.calls.append((method, params))
        if method in {'session/new','session/load'}: return acp_info()
        if method == 'session/set_config_option': return acp_info(params['value']) if params['configId']=='model-choice' else {}
        return {'agentCapabilities':{'loadSession':True}}


def test_acp_dependent_capabilities_and_applied_config(monkeypatch):
    monkeypatch.setattr(models,'Process',AcpProcess)
    catalog = models.acp_models({'resolved':['hermes'],'args':['acp']},Path.cwd(),'deep')
    assert catalog['default_model']=='fast'
    assert catalog['models'][0]['efforts_loaded'] is False
    assert [e['id'] for e in catalog['models'][1]['efforts']] == ['medium','max']
    monkeypatch.setattr('qprint.chat_agents.Process', AcpProcess)
    run_acp({'resolved':['hermes'],'model':'deep','effort':'max'}, {'remote_id':'s'}, 'question', RunStub())
    changes = [params for method,params in FakeProcess.instances[-1].calls if method=='session/set_config_option']
    assert changes == [{'sessionId':'s','configId':'model-choice','value':'deep'}, {'sessionId':'s','configId':'thinking','value':'max'}]


def test_claude_catalog_uses_control_init_without_prompt(monkeypatch):
    class Claude(FakeProcess):
        def next(self, *args):
            return {'type':'control_response','response':{'request_id':'qprint-model-discovery','subtype':'success','response':{
                'models':[{'value':'sonnet','displayName':'Sonnet','supportedEffortLevels':['low','high']} ]}}}
    monkeypatch.setattr(models,'Process',Claude)
    result = models.claude_models({'resolved':['claude']},Path.cwd())
    assert [e['id'] for e in result['models'][0]['efforts']] == ['low','high']
    assert FakeProcess.instances[-1].sent[0]['request']['subtype']=='initialize'


def test_api_catalog_does_not_guess_efforts_and_passes_explicit_selection(monkeypatch):
    original, original_async = httpx.Client, httpx.AsyncClient
    requests=[]
    def handle(request):
        requests.append(request)
        if request.method=='GET':
            return httpx.Response(200,json={'data':[{'id':'plain'},{'id':'reasoner','supported_reasoning_efforts':['low','high']}]})
        return httpx.Response(200,text='data: {"choices":[{"delta":{"content":"ok"}}]}\n\ndata: [DONE]\n\n')
    monkeypatch.setattr(httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(handle),**kw))
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:original_async(transport=httpx.MockTransport(handle),**kw))
    profile={'key':'secret','base_url':'https://api.example/v1','model':'reasoner','effort':'high'}
    result=models.api_models(profile)
    assert result['models'][0]['efforts']==[]
    assert result['models'][1]['efforts'][1]['id']=='high'
    run_api(profile,{'context':'context','messages':[{'role':'user','text':'question'},{'role':'assistant','text':''}]},'question',RunStub())
    import json
    assert json.loads(requests[-1].content)['reasoning_effort']=='high'
