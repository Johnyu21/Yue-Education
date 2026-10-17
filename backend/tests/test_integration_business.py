"""Real PostgreSQL and HTTP regression tests for integrated business flows."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from sqlalchemy import select, func, text
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token
from app.core.errors import ForbiddenError,StateConflictError,NotFoundError
from app.core.transaction import with_business_transaction
from app.models.admin_service import StudentAdminService
from app.models.feedback_ticket import StudentFeedbackTicket
from app.models.user import SysUser
from app.schemas.service import ServiceCreateRequest,ServiceDecisionRequest
from app.schemas.feedback import FeedbackCreateRequest
from app.services import student_service,feedback_service,student_assistant_service


def test_student_cannot_read_internal_directory(student):
    token=create_access_token(student.id,student.token_version)
    with TestClient(app) as c:
        assert c.get('/api/v1/organization/users',headers={'Authorization':'Bearer '+token}).status_code==403


def test_public_draft_events_rejected():
    with TestClient(app) as c:
        assert c.get('/api/v1/public/events?status=DRAFT').status_code==422


def test_single_entry_contains_reports():
    paths=app.openapi()['paths']
    assert '/api/v1/m5/reports' in paths
    assert '/api/v1/reports/preview' in paths


def test_submit_same_key_different_content_rejected(student,m4_db):
    key=uuid4()
    one=ServiceCreateRequest(request_key=key,service_type='OTHER',title='one',description='one')
    # OTHER routes to head; the fixture has a teacher but no department head.
    one.service_type='EXAM'
    with with_business_transaction(m4_db):student_service.submit_service(m4_db,student,one)
    two=one.model_copy(update={'description':'changed'})
    with pytest.raises(StateConflictError):
        with with_business_transaction(m4_db):student_service.submit_service(m4_db,student,two)


def test_assistant_only_proposes_and_never_sends_jwt(student,m4_db,monkeypatch):
    seen={}
    def workflow(payload,uid):
        seen.update(payload)
        assert 'auth_token' not in payload
        return {'intent':'SERVICE_DRAFT','draft':{'service_type':'EXAM','title':'Exam question','description':'Please help'}}
    monkeypatch.setattr(student_assistant_service,'call_student_workflow',workflow)
    from app.schemas.assistant import AssistantRequest
    result=student_assistant_service.handle_student_message(m4_db,student,AssistantRequest(message_id=uuid4(),message='exam'))
    assert result.proposal and result.proposal.confirmationToken
    assert m4_db.scalar(select(func.count()).select_from(StudentAdminService))==0
    preview=result.proposal.preview
    request=ServiceCreateRequest(**preview,request_key=result.proposal.requestKey,confirmation_token=result.proposal.confirmationToken,confirmed=True)
    with with_business_transaction(m4_db):saved=student_service.submit_service(m4_db,student,request)
    assert saved['status']=='PENDING'


def test_service_requires_explicit_confirmation(student,m4_db):
    req=ServiceCreateRequest(request_key=uuid4(),service_type='EXAM',title='x',description='x',confirmed=False)
    from app.core.errors import InvalidRequestError
    with pytest.raises(InvalidRequestError):
        with with_business_transaction(m4_db):student_service.submit_service(m4_db,student,req)


def test_state_change_retry_returns_same_result(student,advisor,m4_db):
    req=ServiceCreateRequest(request_key=uuid4(),service_type='EXAM',title='x',description='x')
    with with_business_transaction(m4_db):saved=student_service.submit_service(m4_db,student,req)
    decision=ServiceDecisionRequest(decision='APPROVE',note='ok',expected_version=1,request_key=uuid4())
    with with_business_transaction(m4_db):one=student_service.decide_service(m4_db,advisor,int(saved['id']),decision)
    with with_business_transaction(m4_db):two=student_service.decide_service(m4_db,advisor,int(saved['id']),decision)
    assert one.model_dump()==two.model_dump()


def test_ordinary_advisor_cannot_correct_psych(m3_db,m3_env,m3_users):
    from app.services import psych_service
    from app.schemas.psych import PsychCorrectionRequest
    actor=m3_users['advisor'];actor.psych_access_enabled=True;m3_db.commit()
    with pytest.raises(ForbiddenError):
        with with_business_transaction(m3_db):
            psych_service.correct_observation(m3_db,actor,m3_env['profile'],PsychCorrectionRequest(replaces_profile_id=1,expected_latest_version=1,emotion_state='HEALTHY',reason='test',request_key=uuid4()))
