from uuid import uuid4
import pytest,httpx
from sqlalchemy import text
from starlette.requests import Request
from app.core.config import settings
from app.core.errors import AIBadResponseError,AIUnavailableError,StateConflictError,NotFoundError,InvalidRequestError
from app.db.session import engine
from app.services import rate_limit,visitor_session,registration_service,lead_service,organization_service
from app.integrations.dify.client import DifyClient
from app.schemas.event import RegistrationIn,RegistrationCancelIn
from app.schemas.lead import LeadCaptureIn
from app.core.transaction import with_business_transaction

def test_forwarded_header_only_from_trusted_proxy(monkeypatch):
    r=Request({'type':'http','client':('127.0.0.9',123),'headers':[(b'x-forwarded-for',b'1.2.3.4')]})
    monkeypatch.setattr(settings,'trusted_proxy_ips','')
    assert rate_limit.client_key(r,'test')=='test:127.0.0.9'
    monkeypatch.setattr(settings,'trusted_proxy_ips','127.0.0.9')
    assert rate_limit.client_key(r,'test')=='test:1.2.3.4'

def test_shared_rate_bucket():
    key='test:'+str(uuid4())
    rate_limit.check(key,1)
    from app.services.m2_errors import RateLimitedError
    with pytest.raises(RateLimitedError):rate_limit.check(key,1)

def test_expired_visitor_draft_not_resurrected():
    cid=visitor_session.new_conversation_id()
    visitor_session.merge(cid,{'name':'Synthetic','not_allowed':'secret'})
    assert visitor_session.get(cid)=={'name':'Synthetic'}
    with engine.begin() as c:c.execute(text("UPDATE runtime_state SET expires_at=now()-interval '1 minute' WHERE key=:k"),{'k':'visitor:'+cid})
    assert visitor_session.merge(cid,{'event_id':'1'})=={'event_id':'1'}
    visitor_session.drop(cid);assert visitor_session.get(cid)=={}

@pytest.mark.parametrize('status,payload,error',[(401,{},AIUnavailableError),(429,{},AIUnavailableError),(503,{},AIUnavailableError),(200,[],AIBadResponseError),(200,{'data':{'status':'failed'}},AIBadResponseError),(200,{'data':{'outputs':[]}},AIBadResponseError)])
def test_dify_errors_are_explicit(monkeypatch,status,payload,error):
    monkeypatch.setattr(httpx,'post',lambda *a,**k:httpx.Response(status,json=payload))
    with pytest.raises(error):DifyClient('http://example.invalid',timeout=3).run_workflow('fake-key',{},'test')

def test_registration_request_binding_and_voucher_rotation(m2_db,m2_env):
    data=RegistrationIn(name='Synthetic',mobile='13700000991',confirmed=True,request_key=uuid4())
    first=registration_service.register_event(m2_db,m2_env['event2'],data)
    with pytest.raises(StateConflictError):registration_service.register_event(m2_db,m2_env['event1'],data)
    cancelled=registration_service.cancel_registration(m2_db,int(first['registrationId']),RegistrationCancelIn(request_key=uuid4(),expected_version=first['version'],cancel_token=first['cancelToken']))
    again=registration_service.register_event(m2_db,m2_env['event2'],data.model_copy(update={'request_key':uuid4()}))
    assert again['cancelToken']!=first['cancelToken']
    with pytest.raises(NotFoundError):registration_service.cancel_registration(m2_db,int(again['registrationId']),RegistrationCancelIn(request_key=uuid4(),expected_version=again['version'],cancel_token=first['cancelToken']))
    with pytest.raises(StateConflictError):registration_service.register_event(m2_db,m2_env['event2'],data)

def test_public_lead_request_content_binding(m2_db,m2_env):
    data=LeadCaptureIn(name='Synthetic',mobile='13700000992',channel='ASSISTANT',confirmed=True,request_key=uuid4())
    assert lead_service.capture_lead(m2_db,data)['accepted']
    with pytest.raises(StateConflictError):lead_service.capture_lead(m2_db,data.model_copy(update={'mobile':'13700000993'}))

def test_department_head_cannot_promote_admin(m3_db,m3_users,m3_env):
    with pytest.raises(InvalidRequestError):
        with with_business_transaction(m3_db):organization_service.update_user(m3_db,m3_env['advisor2'],m3_users['head'],employee_role='ADMIN')

def test_migrations_repeat_without_changes():
    from app.db.migrate import migrate
    with engine.begin() as c:assert migrate(c)==[]


@pytest.mark.parametrize('events,succeeds',[([],False),([{'event':'workflow_finished','data':{'status':'failed','outputs':{}}}],False),([{'event':'workflow_finished','data':{'status':'succeeded','outputs':{'output_json':'{"narrative":"Synthetic verified result"}'}}}],True)])
def test_m5_stream_requires_successful_final_event(monkeypatch,events,succeeds):
    import json
    from types import SimpleNamespace
    from app.integrations.dify import m5_report_ai
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def raise_for_status(self):pass
        def iter_lines(self):return iter('data:'+json.dumps(e) for e in events)
    class Client:
        def __init__(self,*args,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def stream(self,*args,**kwargs):return Response()
    monkeypatch.setattr(httpx,'Client',Client)
    config=SimpleNamespace(ai_timeout=1,dify_base='http://example.invalid/v1')
    if succeeds:assert m5_report_ai.workflow(config,'synthetic-key',{},1)['narrative']=='Synthetic verified result'
    else:
        with pytest.raises(ValueError):m5_report_ai.workflow(config,'synthetic-key',{},1)

def test_unconfigured_asr_is_explicitly_unavailable(monkeypatch):
    from app.services.transcription_service import transcribe
    monkeypatch.setattr(settings,'asr_enabled',False)
    with pytest.raises(AIUnavailableError):transcribe(None)
