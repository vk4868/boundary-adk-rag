"""Independent service/audit boundary tests. All model execution is replaced."""
import json
from pathlib import Path
import pytest
from google.adk.events import Event,EventActions
from pydantic import ValidationError
from app.audit import AuditLogger,AuditWriteError
from app.config import Settings
from app.models import ResearchDraft
from app.service import APP_NAME,ChatService,ServiceUnavailable,SessionOwnershipError,UnknownSession

@pytest.fixture
def service(tmp_path,monkeypatch):
    settings=Settings(_env_file=None,app_enable_model_calls=True,app_model_provider='ollama',app_audit_path=tmp_path/'audit.jsonl',app_max_session_turns=1)
    service=ChatService(settings)
    monkeypatch.setattr(service.repository,'load',lambda:None)
    # Any unexpected real agent construction fails before SDK/network use.
    def deny_agent(*args,**kwargs):raise AssertionError('Unexpected model pipeline construction in offline test')
    monkeypatch.setattr('app.service.build_agent',deny_agent)
    return service

@pytest.mark.asyncio
async def test_session_owner_binding(service):
    record,_=await service._resolve_session(None,'owner-a')
    with pytest.raises(SessionOwnershipError):await service._resolve_session(record.public_id,'owner-b')
    with pytest.raises(UnknownSession):await service._resolve_session('missing','owner-a')

@pytest.mark.asyncio
async def test_session_history_rotation_replaces_internal_session(service):
    record,_=await service._resolve_session(None,'owner-a');previous=record.internal_id;record.turns=1
    assert await service._rotate_if_bounded(record)
    assert record.internal_id!=previous and record.turns==0

@pytest.mark.asyncio
async def test_audit_preflight_failure_prevents_model_construction(service,monkeypatch):
    async def fail(_):raise AuditWriteError('disk unavailable')
    monkeypatch.setattr(service.audit,'append',fail)
    with pytest.raises(AuditWriteError):await service.chat(message='private question',requested_session_id=None,principal='owner-a')

@pytest.mark.asyncio
async def test_stale_session_response_is_not_released(service,monkeypatch):
    monkeypatch.setattr('app.service.build_agent',lambda *a,**kw:object())
    class FakeRunner:
        def __init__(self,*,agent,app_name,session_service):self.sessions=session_service;self.app_name=app_name
        async def run_async(self,*,user_id,session_id,new_message,state_delta,run_config):
            assert all(state_delta[key] is None for key in ('research_draft','review_decision','governed_response'))
            assert run_config.max_llm_calls==service.settings.app_max_model_calls
            session=await self.sessions.get_session(app_name=self.app_name,user_id=user_id,session_id=session_id)
            payload={'request_id':'stale-request-must-fail-0000','session_id':'stale-session-000000000000','status':'insufficient_evidence','answer':'Do not release stale content','claims':[],'citations':[],'sources':[],'trace':[],'usage':{'input_tokens':0,'output_tokens':0,'model_calls':0,'tool_calls':0},'governance':{'review_passed':True,'citation_gate_passed':True,'scope_gate_passed':True},'warnings':[]}
            event=Event(author='document_researcher',actions=EventActions(state_delta={'governed_response':payload}))
            await self.sessions.append_event(session=session,event=event)
            yield event
        async def close(self):pass
    monkeypatch.setattr('app.service.Runner',FakeRunner)
    with pytest.raises(ServiceUnavailable,match='stale'):
        await service.chat(message='private question must stay out of audit',requested_session_id=None,principal='owner-a')
    assert next(iter(service._registry.values())).turns==1
    audit=service.settings.app_audit_path.read_text()
    assert 'private question' not in audit and 'Do not release' not in audit
    assert 'ServiceUnavailable' in audit
    terminal=json.loads(audit.splitlines()[-1])
    assert {key:terminal[key] for key in ('model','model_provider','model_location')}==service.settings.audit_model_metadata

@pytest.mark.asyncio
async def test_success_terminal_audit_identifies_configured_model(service,monkeypatch):
    monkeypatch.setattr('app.service.build_agent',lambda *a,**kw:object())
    class FakeRunner:
        def __init__(self,*,agent,app_name,session_service):self.sessions=session_service;self.app_name=app_name
        async def run_async(self,*,user_id,session_id,new_message,state_delta,run_config):
            record=next(record for record in service._registry.values() if record.internal_id==session_id)
            payload={'request_id':state_delta['request_id'],'session_id':record.public_id,'status':'insufficient_evidence','answer':'No supported answer.','claims':[],'citations':[],'sources':[],'trace':[],'usage':{'input_tokens':0,'output_tokens':0,'model_calls':0,'tool_calls':0},'governance':{'review_passed':True,'citation_gate_passed':True,'scope_gate_passed':True},'warnings':[]}
            session=await self.sessions.get_session(app_name=self.app_name,user_id=user_id,session_id=session_id)
            event=Event(author='deterministic_evidence_gate',actions=EventActions(state_delta={'governed_response':payload}))
            await self.sessions.append_event(session=session,event=event)
            yield event
        async def close(self):pass
    monkeypatch.setattr('app.service.Runner',FakeRunner)

    response=await service.chat(message='offline governed question',requested_session_id=None,principal='owner-a')

    assert response.status=='insufficient_evidence'
    terminal=json.loads(service.settings.app_audit_path.read_text().splitlines()[-1])
    assert terminal['status']=='insufficient_evidence'
    assert {key:terminal[key] for key in ('model','model_provider','model_location')}==service.settings.audit_model_metadata

@pytest.mark.asyncio
async def test_forced_tool_prose_fails_closed_without_publishing_content(service,monkeypatch):
    raw_prose='RAW MODEL PROSE MUST NOT BE PUBLISHED OR LOGGED'
    monkeypatch.setattr('app.service.build_agent',lambda *a,**kw:object())
    class ProseRunner:
        def __init__(self,*,agent,app_name,session_service):self.sessions=session_service;self.app_name=app_name
        async def run_async(self,**kwargs):
            ResearchDraft.model_validate_json(raw_prose)
            yield
        async def close(self):pass
    monkeypatch.setattr('app.service.Runner',ProseRunner)

    with pytest.raises(ValidationError,match='Invalid JSON'):
        await service.chat(message='offline forced tool test',requested_session_id=None,principal='owner-a')

    record=next(iter(service._registry.values()))
    session=await service.sessions.get_session(app_name=APP_NAME,user_id=record.owner,session_id=record.internal_id)
    assert session is not None
    assert not session.state.get('research_draft')
    assert not session.state.get('governed_response')
    assert raw_prose not in service.settings.app_audit_path.read_text()

def test_audit_rejects_raw_content_and_arbitrary_toolname(tmp_path):
    logger=AuditLogger(tmp_path/'audit.jsonl')
    with pytest.raises(AuditWriteError):logger.append_sync({'event':'chat_request','answer':'private passage'})
    with pytest.raises(AuditWriteError):logger.append_sync({'event':'chat_request','event_flow':[{'author':'document_researcher','function_calls':['raw untrusted passage']} ]})
    with pytest.raises(AuditWriteError):logger.append_sync({'event':'chat_request','model':'model\nraw content'})
    assert not (tmp_path/'audit.jsonl').exists()

def test_audit_file_is_private_durable_json(tmp_path):
    path=tmp_path/'audit.jsonl';AuditLogger(path).append_sync({'event':'chat_request','request_id':'x'*24,'status':'rejected','model_calls':0})
    assert path.stat().st_mode&0o777==0o600
    assert json.loads(path.read_text())['request_id']=='x'*24

def test_audit_really_emits_json_stdout_after_write(tmp_path):
    import os,subprocess,sys
    project=Path(__file__).resolve().parents[1]
    code="from pathlib import Path; from app.audit import AuditLogger; AuditLogger(Path('audit.jsonl')).append_sync({'event':'chat_request','request_id':'offline-stdout-check-000000','status':'rejected'})"
    result=subprocess.run([sys.executable,'-c',code],cwd=tmp_path,env={'PATH':os.environ.get('PATH',''),'PYTHONPATH':str(project)},capture_output=True,text=True,check=True)
    record=json.loads(result.stdout)
    assert record['event']=='chat_request'
    assert (tmp_path/'audit.jsonl').read_text().strip()==result.stdout.strip()

def test_api_auth_role_and_security_headers(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    import importlib
    safe=Settings(_env_file=None,app_enable_model_calls=False,app_model_provider='disabled',app_embedding_provider='lexical',app_token='offline-test-token-no-real-secret',app_index_path=tmp_path/'missing-index.json',app_audit_path=tmp_path/'audit.jsonl')
    monkeypatch.setattr('app.config.get_settings',lambda:safe)
    main=importlib.import_module('app.main')
    monkeypatch.setattr(main,'settings',safe);monkeypatch.setattr(main,'service',ChatService(safe))
    with TestClient(main.app) as client:
        r=client.get('/api/sources');assert r.status_code==401
        assert r.headers['x-content-type-options']=='nosniff'
        assert r.headers['referrer-policy']=='no-referrer'
        assert r.headers['cache-control']=='no-store'
        assert "frame-ancestors 'none'" in r.headers['content-security-policy']
        assert client.post('/api/chat',headers={'X-App-Token':safe.app_token.get_secret_value()},json={'message':'No call','role':'admin'}).status_code==400

        async def prose_failure(**kwargs):
            ResearchDraft.model_validate_json('RAW FORCED TOOL PROSE')
        monkeypatch.setattr(main.service,'chat',prose_failure)
        failed=client.post('/api/chat',headers={'X-App-Token':safe.app_token.get_secret_value()},json={'message':'Trigger safe failure'})
        assert failed.status_code==502
        assert failed.json()=={'detail':'model workflow failed closed'}
        assert 'RAW FORCED TOOL PROSE' not in failed.text
