"""Fresh scoped snapshots for reporting. Sensitive sources remain capability gated."""
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from sqlalchemy import select,or_
from app.core.config import settings
from app.core.permissions import build_scope
from app.core.errors import ForbiddenError
from app.models.user import SysUser
from app.models.organization import SysDepartment,SysClass
from app.models.student import StudentProfile
from app.models.lead import CrmLead
from app.models.follow_up import CrmFollowUp
from app.models.psych import StudentPsychAlert,StudentPsychProfile
from app.models.feedback_ticket import StudentFeedbackTicket

def today():return datetime.now(ZoneInfo(settings.business_timezone)).date()
def day(value):
    if value is None:return None
    if isinstance(value,str):value=datetime.fromisoformat(value.replace('Z','+00:00'))
    if value.tzinfo is None:value=value.replace(tzinfo=timezone.utc)
    return value.astimezone(ZoneInfo(settings.business_timezone)).date().isoformat()


def context(db,actor,business=False):
    if not actor.is_employee or actor.status!='NORMAL':raise ForbiddenError('仅有效员工可访问报告')
    scope=build_scope(db,actor,'student');admin=actor.employee_role=='ADMIN';head=bool(scope.is_head_of)
    depts=list(scope.is_head_of) if head else [actor.dept_id] if actor.dept_id else []
    dept=db.get(SysDepartment,actor.dept_id) if actor.dept_id else None
    user={'id':actor.id,'dept_id':actor.dept_id,'real_name':actor.real_name,'role':'ADMIN' if admin else 'TEACHER' if scope.class_teacher_of else actor.employee_role,
        'is_admin':admin,'is_dept_head':admin or head,'actual_dept_head':head,'dept_ids':depts,
        'dept_name':'全域' if admin else dept.name if dept else '未分配部门',
        'psych_access_enabled':bool(actor.psych_access_enabled),'can_handle_feedback':bool(actor.can_handle_feedback),
        '_users':[],'_names':{},'_students':[],'_events':[],'_leads':[],'_observations':[],'_lead_events':[]}
    people_q=select(SysUser).where(SysUser.user_type=='EMPLOYEE')
    if not admin:people_q=people_q.where(SysUser.dept_id.in_(depts))
    heads=set(db.scalars(select(SysDepartment.head_user_id).where(SysDepartment.head_user_id.is_not(None))))
    for p in db.scalars(people_q):
        user['_users'].append({'id':p.id,'dept_id':p.dept_id,'role':p.employee_role,'status':p.status,'writes_daily':p.id not in heads and p.employee_role!='ADMIN'})
        user['_names'][p.id]=p.real_name
    q=select(StudentProfile,SysUser.real_name).join(SysUser,SysUser.id==StudentProfile.user_id)
    if not admin:
        conds=[StudentProfile.advisor_user_id==actor.id,StudentProfile.class_id.in_(scope.class_teacher_of)]
        if head:conds.append(StudentProfile.dept_id.in_(depts))
        q=q.where(or_(*conds))
    for p,name in db.execute(q):
        user['_students'].append({'id':str(p.id),'name':name,'owner_id':p.advisor_user_id,'teacher_id':db.get(SysClass,p.class_id).head_teacher_id if p.class_id else None,
            'dept_id':p.dept_id,'consent':p.psych_consent_status,'is_demo':p.is_demo})
    if not business:return user
    q=select(CrmLead)
    if not admin:q=q.where(or_(CrmLead.dept_id.in_(depts) if head else CrmLead.owner_user_id==actor.id,CrmLead.owner_user_id==actor.id))
    for l in db.scalars(q):
        user['_leads'].append({'id':str(l.id),'name':l.name,'dept_id':l.dept_id,'owner_id':l.owner_user_id,'created_date':day(l.create_time),
            'interest':l.status in {'NEW','FOLLOWING'} and bool(l.interest_level),'enrolled':l.status=='SIGNED','enrolled_date':day(l.signed_at),
            'lost_date':day(l.lost_at),'loss_reason':l.loss_reason,'source':l.source,'education':l.education,'status':l.status,
            'next_action':('计划跟进 '+day(l.next_follow_up_at)) if l.next_follow_up_at else '暂无跟进计划'})
    lead_ids=[int(l['id']) for l in user['_leads']]
    for e in db.scalars(select(CrmFollowUp).where(CrmFollowUp.lead_id.in_(lead_ids))):
        user['_lead_events'].append({'lead_id':str(e.lead_id),'date':day(e.create_time),'before':e.status_before,'after':e.status_after,'type':e.follow_up_type})
    ids=[int(s['id']) for s in user['_students'] if s['consent']=='GRANTED' and not s['is_demo']]
    if actor.psych_access_enabled:
        # RULE/UNKNOWN observations intentionally have is_valid=false; their alerts are still real.
        for e in db.scalars(select(StudentPsychAlert).where(StudentPsychAlert.student_profile_id.in_(ids))):
            user['_events'].append({'id':'P'+str(e.id),'kind':'PSYCH','student_id':str(e.student_profile_id),'dept_id':next(s['dept_id'] for s in user['_students'] if s['id']==str(e.student_profile_id)),
                'owner_id':e.follow_up_user_id,'created_date':day(e.create_time),'updated_date':day(e.update_time),'closed_date':day(e.closed_at),
                'status':e.status,'severity':e.severity,'signal_code':e.signal_code,'summary':'关怀事项','action':'需人工核对'})
        for o in db.scalars(select(StudentPsychProfile).where(StudentPsychProfile.student_profile_id.in_(ids),StudentPsychProfile.is_valid.is_(True)).order_by(StudentPsychProfile.observed_at,StudentPsychProfile.version_no)):
            user['_observations'].append({'id':str(o.id),'student_id':str(o.student_profile_id),'date':o.assessment_date.isoformat(),'emotion':o.emotion_state})
    if actor.can_handle_feedback:
        q=select(StudentFeedbackTicket).where(StudentFeedbackTicket.category=='COMPLAINT')
        if not admin:q=q.where(StudentFeedbackTicket.dept_id.in_(depts) if head else StudentFeedbackTicket.assignee_user_id==actor.id)
        for e in db.scalars(q):
            user['_events'].append({'id':'F'+str(e.id),'kind':'COMPLAINT','student_id':str(e.student_profile_id),'dept_id':e.dept_id,'owner_id':e.assignee_user_id,
                'created_date':day(e.create_time),'updated_date':day(e.update_time),'closed_date':day(e.closed_at),'resolved_date':day(e.resolved_at),
                'status':e.status,'summary':'投诉工单','action':'按工单核对','first_response_at':e.first_response_at.isoformat() if e.first_response_at else None,
                'created_at':e.create_time.isoformat(),'resolved_at':e.resolved_at.isoformat() if e.resolved_at else None,'due_at':e.due_at.isoformat() if e.due_at else None,
                'rating':e.satisfaction_rating,'rated_date':day(e.rated_at),'reopened':e.reopened_count,'reopened_dates':[day(h.get('at')) for h in e.handling_history or [] if isinstance(h,dict) and h.get('action')=='REOPEN' and h.get('at')]})
    return user
