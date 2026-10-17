"""Offline checks for response-only backend additions approved for UI integration."""
import os
os.environ['JWT_SECRET']='frontend-offline-confirmation-test-secret-at-least-32-bytes'
os.environ['DIFY_MODE']='mock'
from types import SimpleNamespace
from uuid import uuid4
from app.core.confirmation import verify_confirmation
from app.models.user import SysUser
from app.schemas.assistant import AssistantRequest
from app.schemas.assistant_enterprise import WfEnterpriseOutput
from app.schemas.application import ApplicationAdvanceIn
from app.schemas.feedback import FeedbackHandlingRequest
from app.schemas.student import StudentEnrollmentItem
from app.services import enterprise_assistant_service as service,m3_canonical

def actor():return SysUser(id=1001,user_type='EMPLOYEE',employee_role='ADMIN',real_name='Synthetic actor',status='NORMAL',token_version=0)

def test_application_preview_reconstructs_exact_signed_payload(monkeypatch):
    monkeypatch.setattr(service,'_latest_case_event',lambda *args:SimpleNamespace(sequence_no=4))
    user=actor()
    req=AssistantRequest(message_id=uuid4(),message='update case')
    wf=WfEnterpriseOutput(intent='APPLICATION_UPDATE',params={'case_no':'CASE-QA','event_kind':'DETAIL','detail':'Synthetic progress','assignee_user_id':1002})
    card=service._handle_write(None,user,req,wf).proposal
    assert card is not None
    v=card.preview
    data=ApplicationAdvanceIn(expected_sequence=v['expectedSequence'],event_kind=v['eventKind'],stage=v['stage'],detail=v['detail'],assignee_user_id=v['assigneeUserId'],occurred_at=v['occurredAt'],request_key=card.requestKey,confirmation_token=card.confirmationToken)
    verify_confirmation(user,card.confirmationToken,operation='ADVANCE_APPLICATION',entity_id=None,payload=m3_canonical.application_advance_payload(v['caseNo'],data),request_key=card.requestKey)

def test_feedback_assignment_preview_reconstructs_exact_signed_payload(monkeypatch):
    monkeypatch.setattr(service.staff_feedback_service,'get_staff_ticket',lambda *args:{'version':7})
    user=actor()
    req=AssistantRequest(message_id=uuid4(),message='assign ticket')
    wf=WfEnterpriseOutput(intent='FEEDBACK_HANDLE',params={'ticket_id':31,'action':'ASSIGN','note':'Synthetic handoff','assignee_user_id':1002})
    card=service._handle_write(None,user,req,wf).proposal
    assert card is not None
    v=card.preview
    data=FeedbackHandlingRequest(action=v['action'],note=v['note'],resolution=v['resolution'],assignee_user_id=v['assigneeUserId'],expected_version=card.expectedVersion,request_key=card.requestKey,confirmation_token=card.confirmationToken)
    verify_confirmation(user,card.confirmationToken,operation='HANDLE_FEEDBACK',entity_id=31,payload=m3_canonical.feedback_handling_payload(data),expected_version=7,request_key=card.requestKey)

def test_enrollment_response_keeps_actual_version():
    dto=StudentEnrollmentItem(id='1',courseProjectId='2',projectName='Synthetic project',status='ENROLLED',version=9)
    assert dto.model_dump()['version']==9
