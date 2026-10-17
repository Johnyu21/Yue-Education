from datetime import datetime,timedelta,timezone
from uuid import uuid4
from sqlalchemy import text
from app.db.session import SessionLocal
from app.models.admin_service import StudentAdminService
from app.core.transaction import with_business_transaction
from app.core.errors import VersionConflictError
from app.schemas.service import ServiceCreateRequest
from app.services.student_service import submit_service
import pytest


def test_orm_version_prevents_lost_update(student,m4_db):
    with with_business_transaction(m4_db):
        row=submit_service(m4_db,student,ServiceCreateRequest(request_key=uuid4(),service_type='EXAM',title='x',description='x'))
    with SessionLocal() as one,SessionLocal() as two:
        a=one.get(StudentAdminService,int(row['id']));b=two.get(StudentAdminService,int(row['id']))
        with with_business_transaction(one):a.description='first';a.version+=1
        with pytest.raises(VersionConflictError):
            with with_business_transaction(two):b.description='second';b.version+=1
    m4_db.expire_all()
    assert m4_db.get(StudentAdminService,int(row['id'])).description=='first'


def test_reminder_batches_and_revisions(m4_db,m4_env):
    db=m4_db
    db.execute(text("""INSERT INTO student_academic_schedule(student_profile_id,schedule_type,title,start_at,remind_at,created_by_user_id,data_source)
        SELECT :p,'EXAM','batch reminder',now()+interval '2 day',now()-interval '1 minute',:u,'TEST' FROM generate_series(1,205)"""),{'p':m4_env['profile'],'u':m4_env['advisor']})
    db.commit()
    from app.core.scheduler import scan_schedule_reminders
    assert scan_schedule_reminders()==200
    assert scan_schedule_reminders()==5
    assert scan_schedule_reminders()==0
    sid=db.scalar(text('SELECT min(id) FROM student_academic_schedule WHERE student_profile_id=:p'),{'p':m4_env['profile']})
    db.execute(text('UPDATE student_academic_schedule SET reminder_revision=reminder_revision+1 WHERE id=:s'),{'s':sid});db.commit()
    assert scan_schedule_reminders()==1
    assert scan_schedule_reminders()==0


def test_parallel_overlapping_leave_only_one_accepted(m4_env):
    from concurrent.futures import ThreadPoolExecutor
    from datetime import datetime,timedelta,timezone
    from uuid import uuid4
    from app.db.session import SessionLocal
    from app.models.user import SysUser
    from app.schemas.service import ServiceCreateRequest
    from app.services.student_service import submit_service
    from app.core.transaction import with_business_transaction
    from app.core.errors import AppError
    start=datetime.now(timezone.utc)+timedelta(days=5)
    def submit(index):
        with SessionLocal() as db:
            user=db.get(SysUser,m4_env['student_user'])
            try:
                with with_business_transaction(db):return ('ok',submit_service(db,user,ServiceCreateRequest(request_key=uuid4(),service_type='LEAVE',title='Parallel leave',description='Synthetic',start_at=start,end_at=start+timedelta(hours=1))))
            except AppError as exc:return ('error',exc.code)
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(submit,range(2)))
    assert sorted(x[0] for x in results)==['error','ok'],results

def test_parallel_same_request_replays_single_write(m4_env):
    from concurrent.futures import ThreadPoolExecutor
    from uuid import uuid4
    from sqlalchemy import select,func
    from app.db.session import SessionLocal
    from app.models.user import SysUser
    from app.models.admin_service import StudentAdminService
    from app.schemas.service import ServiceCreateRequest
    from app.services.student_service import submit_service
    from app.core.transaction import with_business_transaction
    request=ServiceCreateRequest(request_key=uuid4(),service_type='EXAM',title='Parallel retry',description='Synthetic')
    def submit(index):
        with SessionLocal() as db:
            user=db.get(SysUser,m4_env['student_user'])
            with with_business_transaction(db):return submit_service(db,user,request)
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(submit,range(2)))
    assert results[0]==results[1]
    with SessionLocal() as db:assert db.scalar(select(func.count()).select_from(StudentAdminService).where(StudentAdminService.request_key==request.request_key))==1


def test_parallel_registration_capacity_not_oversold(m2_env):
    from concurrent.futures import ThreadPoolExecutor
    from uuid import uuid4
    from sqlalchemy import select,func
    from app.db.session import SessionLocal
    from app.models.event import EventRegistration
    from app.schemas.event import RegistrationIn
    from app.services.registration_service import register_event
    from app.core.errors import AppError
    def submit(index):
        with SessionLocal() as db:
            try:
                register_event(db,m2_env['event1'],RegistrationIn(request_key=uuid4(),confirmed=True,name='Synthetic capacity',mobile='1370000080'+str(index)))
                return 'ok'
            except AppError as exc:return exc.code
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(submit,range(2)))
    assert results.count('ok')==1,results
    with SessionLocal() as db:assert db.scalar(select(func.count()).select_from(EventRegistration).where(EventRegistration.event_id==m2_env['event1'],EventRegistration.status=='REGISTERED'))==1
