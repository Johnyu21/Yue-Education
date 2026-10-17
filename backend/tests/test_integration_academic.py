from uuid import uuid4
from datetime import datetime,timedelta,timezone
from decimal import Decimal
import pytest
from app.core.transaction import with_business_transaction
from app.core.errors import ForbiddenError
from app.schemas.academic_admin import ScoreWrite,ScheduleWrite
from app.services import academic_admin_service as svc,academic_service


def test_manual_scores_and_student_readonly(student,advisor,m4_db,m4_env):
    data=ScoreWrite(request_key=uuid4(),subject='Math',score_type='NUMERIC',score_text='80/100',score_numeric=80,max_score=100)
    with with_business_transaction(m4_db):r=svc.create_score(m4_db,advisor,m4_env['profile'],data)
    assert r['dataSource']=='MANUAL'
    with pytest.raises(ForbiddenError):
        with with_business_transaction(m4_db):svc.create_score(m4_db,student,m4_env['profile'],data.model_copy(update={'request_key':uuid4()}))
    rows,total=academic_service.list_scores(m4_db,student)
    assert total==1 and rows[0].scoreNumeric=='80.00'
    with with_business_transaction(m4_db):
        changed=svc.update_score(m4_db,advisor,m4_env['profile'],int(r['id']),data.model_copy(update={'expected_version':1,'request_key':uuid4(),'score_numeric':Decimal(90)}))
    assert changed['version']==2


def test_manual_schedule_reminder(student,advisor,m4_db,m4_env):
    data=ScheduleWrite(request_key=uuid4(),schedule_type='EXAM',title='Math exam',start_at=datetime.now(timezone.utc)+timedelta(days=5))
    with with_business_transaction(m4_db):r=svc.create_schedule(m4_db,advisor,m4_env['profile'],data)
    from app.schemas.student import ReminderRequest
    with with_business_transaction(m4_db):
        reminder=academic_service.set_reminder(m4_db,student,int(r['id']),ReminderRequest(request_key=uuid4(),expected_version=1,remind_at=data.start_at-timedelta(days=1)))
    assert reminder['reminderRevision']==2


def test_excel_preview_apply(advisor,m4_db,tmp_path,monkeypatch):
    from openpyxl import Workbook
    from app.core import storage
    from app.schemas.lead_import import LeadImportIn
    from app.services import lead_import_service
    monkeypatch.setattr(storage,'_storage_root',lambda:tmp_path)
    folder=tmp_path/'u'/str(advisor.id);folder.mkdir(parents=True)
    book=Workbook();book.active.append(['姓名','手机号','学历']);book.active.append(['Synthetic','13812345678','本科']);book.save(folder/'leads.xlsx')
    data=LeadImportIn(object_key=f'u/{advisor.id}/leads.xlsx',mapping={'name':'姓名','mobile':'手机号','education':'学历'},request_key=uuid4())
    preview=lead_import_service.preview(m4_db,advisor,data)
    assert preview['canApply'] and len(preview['rows'])==1
    confirmed=data.model_copy(update={'confirmed':True,'fingerprint':preview['fingerprint']})
    with with_business_transaction(m4_db):r=lead_import_service.apply(m4_db,advisor,confirmed)
    with with_business_transaction(m4_db):again=lead_import_service.apply(m4_db,advisor,confirmed)
    assert r==again and r['count']==1


def test_alternative_rules_and_age():
    from types import SimpleNamespace
    from app.services.assessment_rules import evaluate_project
    p=SimpleNamespace(id=1,name='paths',rule_version='v1',rule_approved_at=datetime.now(timezone.utc),admission_rules={'criteria':[{'any_of':[{'field':'education','op':'IN','values':['本科']},{'all_of':[{'field':'education','op':'IN','values':['大专']},{'field':'age','op':'GTE','value':18}]}]}]})
    assert evaluate_project(p,{'education':'专科','date_of_birth':'2000-01-01'})['decision']=='MATCH'
    assert evaluate_project(p,{'education':'初中','date_of_birth':'2000-01-01'})['decision']=='NO_MATCH'
