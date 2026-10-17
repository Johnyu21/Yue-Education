from uuid import uuid4
from datetime import date
from sqlalchemy import select,func
from fastapi.testclient import TestClient
from app.main import app
from app.core.transaction import with_business_transaction
from app.schemas.lead import LeadCaptureIn,ConversionIn
from app.models.lead import CrmLead
from app.models.notification import Notification
from app.models.student import StudentProfile
from app.services import lead_service,crm_service

def test_capture_claim_convert_first_login_and_contact(m3_db,m3_env,m3_users):
    mobile='19900000123'
    lead_service.capture_lead(m3_db,LeadCaptureIn(name='Synthetic delivery',mobile=mobile,channel='ASSISTANT',confirmed=True,intended_project_id=m3_env['project'],request_key=uuid4()))
    lead=m3_db.scalar(select(CrmLead).where(CrmLead.mobile==mobile))
    with with_business_transaction(m3_db):
        claimed=crm_service.claim_lead(m3_db,m3_users['advisor'],lead.id,expected_version=lead.version,request_key=uuid4())
    data=ConversionIn(request_key=uuid4(),expected_version=claimed['version'],contract_confirmed=True,course_project_id=m3_env['project'],class_id=m3_env['cls'],advisor_user_id=m3_env['advisor2'],enrollment_date=date.today(),contract_amount='100.00',contract_currency='CNY')
    with with_business_transaction(m3_db):converted=crm_service.convert_to_student(m3_db,m3_users['advisor'],lead.id,data)
    assert converted['initial_credentials']['username']==mobile
    with with_business_transaction(m3_db):replayed=crm_service.convert_to_student(m3_db,m3_users['advisor'],lead.id,data)
    assert replayed['already_converted'] and 'initial_credentials' not in replayed
    assert m3_db.scalar(select(func.count()).select_from(StudentProfile).where(StudentProfile.converted_lead_id==lead.id))==1
    with TestClient(app) as client:
        login=client.post('/api/v1/auth/login',json={'username':mobile,'password':converted['initial_credentials']['temporary_password']})
        assert login.status_code==200,login.text
        old_token=login.json()['data']['accessToken'];headers={'Authorization':'Bearer '+old_token}
        assert client.get('/api/v1/me/student-profile',headers=headers).status_code==403
        changed=client.post('/api/v1/auth/password-change',headers=headers,json={'old_password':converted['initial_credentials']['temporary_password'],'new_password':'Synthetic-new-password-123'})
        assert changed.status_code==200,changed.text
        assert client.get('/api/v1/auth/me',headers=headers).status_code==401
        login=client.post('/api/v1/auth/login',json={'username':mobile,'password':'Synthetic-new-password-123'})
        headers={'Authorization':'Bearer '+login.json()['data']['accessToken']}
        assert client.get('/api/v1/me/student-profile',headers=headers).status_code==200
        interest=client.post('/api/v1/me/upgrade-interests',headers=headers,json={'request_key':str(uuid4()),'course_project_id':m3_env['project'],'note':'Synthetic contact','confirmed':True})
        assert interest.status_code==201,interest.text
    m3_db.expire_all()
    notice=m3_db.scalar(select(Notification).where(Notification.business_event_key.like('lead:'+str(lead.id)+':upgrade:%')))
    assert notice.recipient_user_id==m3_env['advisor2']


def test_handover_then_relationship_change_is_allowed(m3_db,m3_env,m3_users):
    import pytest
    from app.schemas.service import ServiceCreateRequest
    from app.schemas.student import RelationshipUpdateIn
    from app.services import student_service,employee_student_service
    from app.services.m3_errors import PendingRequestsRequireReassignError
    with with_business_transaction(m3_db):
        pending=student_service.submit_service(m3_db,m3_users['student_user'],ServiceCreateRequest(request_key=uuid4(),service_type='EXAM',title='Synthetic handover',description='Synthetic'))
    data=RelationshipUpdateIn(request_key=uuid4(),advisor_user_id=m3_env['advisor2'],expected_version=1,reason='Synthetic handover')
    with pytest.raises(PendingRequestsRequireReassignError):
        with with_business_transaction(m3_db):employee_student_service.update_relationship(m3_db,m3_users['head'],m3_env['profile'],data)
    with with_business_transaction(m3_db):
        student_service.assign_service(m3_db,m3_users['head'],int(pending['id']),assignee_user_id=m3_env['advisor2'],expected_version=1,reason='Synthetic handover',request_key=uuid4())
    with with_business_transaction(m3_db):
        result=employee_student_service.update_relationship(m3_db,m3_users['head'],m3_env['profile'],data)
    assert result['advisorUserId']==str(m3_env['advisor2'])

def test_disabling_employee_with_relationship_is_blocked(m3_db,m3_env,m3_users):
    import pytest
    from app.services.organization_service import update_user
    from app.core.errors import StateConflictError
    from app.models.user import SysUser
    with pytest.raises(StateConflictError):
        with with_business_transaction(m3_db):update_user(m3_db,m3_env['advisor'],m3_users['admin'],status='DISABLED')
    assert m3_db.get(SysUser,m3_env['advisor']).status=='NORMAL'


def test_employee_assistant_followup_keeps_existing_plan(m3_db,m3_env,m3_users,monkeypatch):
    from datetime import datetime,timedelta,timezone
    from app.schemas.lead import LeadManualIn,FollowUpIn
    from app.schemas.assistant import AssistantRequest
    from app.services import enterprise_assistant_service
    with with_business_transaction(m3_db):
        saved=crm_service.create_lead(m3_db,m3_users['advisor'],LeadManualIn(name='Synthetic assistant',mobile='19900000124',request_key=uuid4()))
    lead=m3_db.get(CrmLead,int(saved['lead_id']))
    plan=datetime.now(timezone.utc)+timedelta(days=5)
    with with_business_transaction(m3_db):lead.next_follow_up_at=plan;m3_db.flush()
    # Copy ID before the ORM is expired by the transaction boundary.
    lead_id=lead.id
    def workflow(payload,**kwargs):
        assert not m3_db.in_transaction()
        return {'intent':'FOLLOWUP_ADD','params':{'lead_id':str(lead_id)},'draft':{'content':'Synthetic followup'}}
    monkeypatch.setattr(enterprise_assistant_service,'run_enterprise_workflow',workflow)
    result=enterprise_assistant_service.handle_enterprise_message(m3_db,m3_users['advisor'],AssistantRequest(message_id=uuid4(),message='Record synthetic followup'))
    assert result.proposal and result.proposal.preview['nextFollowUpAtProvided'] is False
    card=result.proposal
    data=FollowUpIn(content=card.preview['content'],expected_version=card.expectedVersion,request_key=card.requestKey,confirmation_token=card.confirmationToken)
    with with_business_transaction(m3_db):crm_service.add_follow_up(m3_db,m3_users['advisor'],lead_id,data)
    assert m3_db.get(CrmLead,lead_id).next_follow_up_at==plan
