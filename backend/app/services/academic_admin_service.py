"""Authorized manual data sources. Students only read these records."""
import json
from sqlalchemy import select,text
from app.core.errors import ForbiddenError,NotFoundError,VersionConflictError,InvalidRequestError
from app.core.idempotency import idempotent
from app.models.score import StudentScore
from app.models.academic_schedule import StudentAcademicSchedule
from app.models.enrollment import StudentCourseEnrollment
from app.repositories.common import require_student_visible
from app.services.employee_student_service import _schedule_to_dto
from app.services.academic_service import _score_to_dto


def _authorize(db,user,student_id,data):
    if not user.is_employee or user.employee_role=='NEWCOMER':raise ForbiddenError()
    require_student_visible(db,user,student_id)
    if data.enrollment_id:
        e=db.get(StudentCourseEnrollment,data.enrollment_id)
        if e is None or e.student_profile_id!=student_id:raise NotFoundError('课程关联不存在')
    if getattr(data,'schedule_id',None):
        s=db.get(StudentAcademicSchedule,data.schedule_id)
        if s is None or s.student_profile_id!=student_id:raise NotFoundError('日程不存在')


def _audit(db,user,kind,record,action,before,after):
    db.execute(text('INSERT INTO business_audit(actor_id,object_kind,object_id,action,before_data,after_data) VALUES (:a,:k,:i,:op,CAST(:b AS jsonb),CAST(:n AS jsonb))'),
        {'a':user.id,'k':kind,'i':str(record.id),'op':action,'b':json.dumps(before,default=str) if before else None,'n':json.dumps(after,default=str)})


@idempotent('academic.score.create')
def create_score(db,user,student_id,data):
    _authorize(db,user,student_id,data)
    r=StudentScore(student_profile_id=student_id,recorded_by_user_id=user.id,data_source='MANUAL',**data.model_dump(exclude={'request_key','expected_version'}))
    db.add(r);db.flush();result=_score_to_dto(r).model_dump(mode='json');result['version']=r.version
    _audit(db,user,'score',r,'CREATE',None,result);return result


@idempotent('academic.score.update')
def update_score(db,user,student_id,score_id,data):
    _authorize(db,user,student_id,data)
    r=db.get(StudentScore,score_id)
    if r is None or r.student_profile_id!=student_id:raise NotFoundError()
    if r.version!=data.expected_version:raise VersionConflictError(r.version)
    before=_score_to_dto(r).model_dump(mode='json')
    for k,v in data.model_dump(exclude={'request_key','expected_version'}).items():setattr(r,k,v)
    r.data_source='MANUAL';r.recorded_by_user_id=user.id;r.version+=1;db.flush()
    result=_score_to_dto(r).model_dump(mode='json');result['version']=r.version
    _audit(db,user,'score',r,'UPDATE',before,result);return result


@idempotent('academic.schedule.create')
def create_schedule(db,user,student_id,data):
    _authorize(db,user,student_id,data)
    r=StudentAcademicSchedule(student_profile_id=student_id,created_by_user_id=user.id,data_source='MANUAL',**data.model_dump(exclude={'request_key','expected_version'}))
    db.add(r);db.flush();result=_schedule_to_dto(r).model_dump(mode='json')
    _audit(db,user,'schedule',r,'CREATE',None,result);return result


@idempotent('academic.schedule.update')
def update_schedule(db,user,student_id,schedule_id,data):
    _authorize(db,user,student_id,data)
    r=db.get(StudentAcademicSchedule,schedule_id,with_for_update=True,populate_existing=True)
    if r is None or r.student_profile_id!=student_id:raise NotFoundError()
    if r.version!=data.expected_version:raise VersionConflictError(r.version)
    before=_schedule_to_dto(r).model_dump(mode='json')
    for k,v in data.model_dump(exclude={'request_key','expected_version'}).items():setattr(r,k,v)
    if r.remind_at and (r.remind_at>r.start_at or r.status!='SCHEDULED'):r.remind_at=None
    r.version+=1;r.reminder_revision+=1;db.flush();result=_schedule_to_dto(r).model_dump(mode='json')
    _audit(db,user,'schedule',r,'UPDATE',before,result);return result
