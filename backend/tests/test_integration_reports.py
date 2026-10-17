from uuid import uuid4
import pytest
from sqlalchemy import text,select,func
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token
from app.repositories.m5_report_repository import today
from app.models.m5_report_models import DailyRevision

@pytest.fixture
def reports(m3_db,m3_env,m3_users):
    with TestClient(app) as client:
        def call(who,method,url,body=None):
            user=m3_users[who]
            return getattr(client,method)(url,headers={'Authorization':'Bearer '+create_access_token(user.id,user.token_version)},**({'json':body} if body is not None else {}))
        yield call
    m3_db.rollback()
    m3_db.execute(text("DELETE FROM crm_lead WHERE mobile='13800009876'"))
    for table in ('m5_daily_revision','m5_report','m5_report_snapshot','m5_daily','m5_chat'):
        m3_db.execute(text('DELETE FROM '+table))
    m3_db.commit()

def daily_body():
    return {'report_date':today().isoformat(),'request_key':str(uuid4()),'content':{'work_summary':'Followed up customers','difficulties':'None'}}

def test_daily_approval_version_and_replay(reports,m3_db):
    body=daily_body();response=reports('advisor','put','/api/v1/m5/dailies',body)
    assert response.status_code==200,response.text
    d=response.json()['data']
    assert reports('advisor','put','/api/v1/m5/dailies',body).json()['data']==d
    def action(who,name,version):
        r=reports(who,'post','/api/v1/m5/dailies/'+d['id']+'/action',{'action':name,'expected_version':version,'request_key':str(uuid4())})
        assert r.status_code==200,r.text
        return r.json()['data']
    action('advisor','SUBMIT',1)
    action('head','APPROVE',2)
    assert m3_db.scalar(select(func.count()).select_from(DailyRevision))==1
    body['expected_version']=3;body['request_key']=str(uuid4());body['content']['work_summary']='Unapproved revision'
    assert reports('advisor','put','/api/v1/m5/dailies',body).status_code==200
    preview=reports('head','post','/api/v1/reports/preview',{'type':'DAILY_DAY','start_date':today().isoformat(),'end_date':today().isoformat()})
    assert preview.status_code==200,preview.text
    facts=str(preview.json()['data']['facts'])
    assert 'Followed up customers' in facts and 'Unapproved revision' not in facts

def test_preview_saved_snapshot_and_export(reports,m3_db,m3_env):
    request={'type':'CUSTOMER_OPERATION','start_date':today().isoformat(),'end_date':today().isoformat()}
    response=reports('admin','post','/api/v1/reports/preview',request)
    assert response.status_code==200,response.text
    preview=response.json()['data']
    # Change ordinary source data after preview; saving must not recalculate metrics.
    m3_db.execute(text("INSERT INTO crm_lead(name,mobile,source,status,dept_id,owner_user_id,request_key) VALUES ('Snapshot changed','13800009876','MANUAL','NEW',:d,:u,:k)"),{'d':m3_env['dept_a'],'u':m3_env['advisor'],'k':uuid4()});m3_db.commit()
    body={**request,'snapshot_id':preview['snapshot_id'],'title':'Synthetic report','narrative':preview['narrative'],'request_key':str(uuid4())}
    response=reports('admin','post','/api/v1/m5/reports',body)
    assert response.status_code==200,response.text
    saved=response.json()['data'];assert saved['metrics']==preview['metrics']
    assert reports('admin','post','/api/v1/m5/reports',body).json()['data']==saved
    for fmt in ('docx','pdf'):
        exported=reports('admin','get','/api/v1/m5/reports/'+saved['id']+'/export/'+fmt)
        assert exported.status_code==200 and len(exported.content)>500
    m3_db.execute(text("DELETE FROM crm_lead WHERE mobile='13800009876'"));m3_db.commit()

def test_sensitive_report_rechecks_capability(reports,m3_db,m3_env):
    request={'type':'PSYCH_WEEK','start_date':today().isoformat(),'end_date':today().isoformat()}
    preview=reports('head','post','/api/v1/reports/preview',request)
    assert preview.status_code==200,preview.text
    p=preview.json()['data']
    body={**request,'snapshot_id':p['snapshot_id'],'title':'Psych','narrative':p['narrative'],'request_key':str(uuid4())}
    saved=reports('head','post','/api/v1/m5/reports',body)
    assert saved.status_code==200,saved.text
    rid=saved.json()['data']['id']
    m3_db.execute(text('UPDATE sys_user SET psych_access_enabled=false WHERE id=:id'),{'id':m3_env['head']});m3_db.commit()
    assert reports('head','get','/api/v1/m5/reports/'+rid).status_code==403
    assert reports('admin','get','/api/v1/m5/reports/'+rid+'/export/pdf').status_code==403


def test_specialist_ordinary_daily_reviewed_by_ordinary_head(reports,m3_db,m3_env):
    m3_db.execute(text('UPDATE sys_user SET psych_access_enabled=false,can_handle_feedback=false WHERE id=:id'),{'id':m3_env['head']});m3_db.commit()
    saved=reports('psych_advisor','put','/api/v1/m5/dailies',daily_body())
    assert saved.status_code==200,saved.text
    d=saved.json()['data']
    for who,action,version in [('psych_advisor','SUBMIT',1),('head','APPROVE',2)]:
        response=reports(who,'post','/api/v1/m5/dailies/'+d['id']+'/action',{'action':action,'expected_version':version,'request_key':str(uuid4())})
        assert response.status_code==200,response.text
    history=reports('head','get','/api/v1/m5/dailies/'+d['id']+'/history')
    assert history.status_code==200 and len(history.json()['data'])==1

def test_daily_rejects_sensitive_module_details(reports):
    body=daily_body();body['content']['items']=[{'category':'PSYCH','description':'Sensitive work','student_ids':[]}]
    assert reports('psych_advisor','put','/api/v1/m5/dailies',body).status_code==422


def test_global_customer_metrics_and_previous_period(reports,m3_db,m3_env):
    m3_db.execute(text('UPDATE sys_user SET dept_id=NULL WHERE id=:id'),{'id':m3_env['admin']})
    for i,dept,when in [(1,m3_env['dept_a'],'now()'),(2,m3_env['dept_b'],'now()'),(3,m3_env['dept_a'],"now()-interval '1 day'")]:
        m3_db.execute(text("INSERT INTO crm_lead(name,mobile,source,status,dept_id,owner_user_id,request_key,create_time) VALUES (:n,:m,'MANUAL','NEW',:d,:u,:k,"+when+")"),{'n':'Synthetic '+str(i),'m':'1990000099'+str(i),'d':dept,'u':None,'k':uuid4()})
    m3_db.commit()
    request={'type':'CUSTOMER_OPERATION','start_date':today().isoformat(),'end_date':today().isoformat()}
    response=reports('admin','post','/api/v1/reports/preview',request)
    assert response.status_code==200,response.text
    metrics={m['key']:m['value'] for m in response.json()['data']['metrics']}
    assert metrics['new_customers']==2 and metrics['previous_new_customers']==1
    head=reports('head','post','/api/v1/reports/preview',request)
    assert next(m['value'] for m in head.json()['data']['metrics'] if m['key']=='new_customers')==1

def test_direct_risk_counted_without_valid_emotion(reports,m3_db,m3_env):
    from datetime import datetime,timezone
    from app.models.student import StudentProfile
    from app.core.transaction import with_business_transaction
    from app.services.psych_service import record_direct_risk
    profile=m3_db.get(StudentProfile,m3_env['profile'])
    with with_business_transaction(m3_db):
        profile.psych_consent_status='GRANTED';profile.psych_consent_version='v1';profile.psych_consent_at=datetime.now(timezone.utc);profile.version+=1;m3_db.flush()
        record_direct_risk(m3_db,profile,source_event_key=uuid4(),received_at=datetime.now(timezone.utc),matched_word='synthetic fixture')
    request={'type':'PSYCH_WEEK','start_date':today().isoformat(),'end_date':today().isoformat()}
    response=reports('head','post','/api/v1/reports/preview',request)
    assert response.status_code==200,response.text
    metrics={m['key']:m['value'] for m in response.json()['data']['metrics']}
    assert metrics['high_risk']==1 and metrics['new_events']==1 and metrics['observed_student_days']==0

def test_complaint_sla_and_ratings(reports,m3_db,m3_env,m3_users):
    from datetime import datetime,timedelta,timezone
    from app.core.transaction import with_business_transaction
    from app.services.feedback_service import submit_feedback
    from app.schemas.feedback import FeedbackCreateRequest
    for i in range(2):
        with with_business_transaction(m3_db):
            result=submit_feedback(m3_db,m3_users['student_user'],FeedbackCreateRequest(request_key=uuid4(),category='COMPLAINT',subject='Synthetic',teacher_name='Synthetic',project_category='Teaching',content='Synthetic'))
        if i==0:
            m3_db.execute(text("UPDATE student_feedback_ticket SET due_at=now()-interval '1 hour' WHERE id=:id"),{'id':int(result.id)})
        else:
            m3_db.execute(text("UPDATE student_feedback_ticket SET status='CLOSED',is_notified=true,resolution='Synthetic',resolved_at=now(),closed_at=now(),satisfaction_rating=4,rated_at=now(),first_resolved_at=now(),first_response_at=create_time WHERE id=:id"),{'id':int(result.id)})
        m3_db.commit()
    response=reports('head','post','/api/v1/reports/preview',{'type':'COMPLAINT_WEEK','start_date':today().isoformat(),'end_date':today().isoformat()})
    assert response.status_code==200,response.text
    metrics={m['key']:m['value'] for m in response.json()['data']['metrics']}
    assert metrics['new_events']==2 and metrics['overdue_tickets']==1 and metrics['rating_average']==4 and metrics['rating_count']==1
