"""Transactional idempotency: reserve, mutate and store result in one caller-owned transaction."""
import hashlib
import inspect
import json
from functools import wraps
from typing import get_type_hints
from pydantic import BaseModel
from pydantic_core import to_jsonable_python
from sqlalchemy import text
from app.core.errors import StateConflictError, NotFoundError, ForbiddenError


def _authorize_replay(db, actor, values, response):
    # Replays never retain obsolete access after reassignment or capability removal.
    if isinstance(actor,dict):
        from app.models.m5_report_models import Daily,Report
        from app.services.m5_report_policy import report_record_access
        from app.services.m5_report_service import restricted_daily,scoped_daily_query
        from sqlalchemy import select
        data=response.get('data',response) if isinstance(response,dict) else {}
        rid=data.get('id')
        module=values.get('_module','')
        if 'm5_report_routes' in module and rid:
            record=db.get(Report,rid)
            report_record_access(actor,record)
        elif 'm5_report_service' in module and rid:
            record=db.scalar(scoped_daily_query(actor).where(Daily.id==rid))
            if not record:raise NotFoundError()
            if restricted_daily(actor,record):raise ForbiddenError()
        return
    from app.models.lead import CrmLead
    from app.models.student import StudentProfile
    from app.models.admin_service import StudentAdminService
    from app.models.feedback_ticket import StudentFeedbackTicket
    from app.models.psych import StudentPsychAlert
    from app.models.organization import SysDepartment
    from app.repositories.common import require_student_visible, my_profile_id
    from app.core.permissions import build_scope
    from sqlalchemy import select
    module=values.get('_module','')
    if 'psych_service' in module and values.get('req') is not None and not actor.psych_access_enabled and not actor.is_student:raise ForbiddenError()
    if actor.is_employee and actor.employee_role=='NEWCOMER' and any(name in module for name in ('crm_service','employee_student_service','academic_admin_service','lead_import_service','progress_service')):raise ForbiddenError()
    if 'lead_import_service' in module and isinstance(response,dict):
        for row in response.get('items',[]):
            if row.get('lead_id'):build_scope(db,actor,'lead').get_or_404(db,CrmLead,int(row['lead_id']))
    lid=values.get('lead_id')
    if lid is None and isinstance(response,dict):lid=response.get('lead_id')
    if lid is not None:
        build_scope(db,actor,'lead').get_or_404(db,CrmLead,int(lid))
    sid=values.get('student_id') or values.get('student_profile_id')
    if sid is not None:
        profile=require_student_visible(db,actor,int(sid))
        if "psych_service" in module and not actor.is_student and profile.psych_consent_status!="GRANTED":raise NotFoundError()
    for name,model in [('service_id',StudentAdminService),('ticket_id',StudentFeedbackTicket),('alert_id',StudentPsychAlert)]:
        rid=values.get(name)
        if rid is None:continue
        obj=db.get(model,rid)
        if obj is None:raise NotFoundError()
        if actor.is_student:
            if obj.student_profile_id != my_profile_id(db,actor):raise NotFoundError()
        else:
            if name=='ticket_id':
                from app.services.staff_feedback_service import _require_ticket_visible
                _require_ticket_visible(db,actor,obj)
            elif name=='service_id':
                from app.services.student_service import _check_decider_permission
                _check_decider_permission(db,actor,obj)
            else:
                if not actor.psych_access_enabled:raise ForbiddenError()
                profile=require_student_visible(db,actor,obj.student_profile_id)
                if profile.psych_consent_status!="GRANTED":raise NotFoundError()
    case=values.get('case_no_str')
    if case:
        from uuid import UUID
        from app.models.application_progress import StudentApplicationProgress
        event=db.scalar(select(StudentApplicationProgress).where(StudentApplicationProgress.case_no==UUID(case)))
        if event is None:raise NotFoundError()
        require_student_visible(db,actor,event.student_profile_id)


def idempotent(operation):
    def decorate(fn):
        signature=inspect.signature(fn)
        @wraps(fn)
        def wrapped(*args,**kwargs):
            bound=signature.bind(*args,**kwargs);bound.apply_defaults();values=bound.arguments
            db=values['db'];actor=values.get('actor',values.get('user'))
            body=values.get('req',values.get('data',values.get('body')))
            key=getattr(body,'request_key',None) if body is not None else values.get('request_key')
            if key is None:return fn(*args,**kwargs)
            actor_id=actor['id'] if isinstance(actor,dict) else actor.id
            payload={}
            for name,value in values.items():
                if name in {'db','actor','user','confirmation_token'}:continue
                if isinstance(value,BaseModel):value={'value':value.model_dump(mode='json',exclude={'confirmation_token'}),'provided_fields':sorted(value.model_fields_set-{'confirmation_token'})}
                elif hasattr(value,'_sa_instance_state'):value={'id':value.id}
                payload[name]=to_jsonable_python(value)
            fingerprint=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
            params={'a':actor_id,'o':operation,'k':str(key),'f':fingerprint}
            fresh=db.execute(text('INSERT INTO business_request(actor_id,operation,request_key,fingerprint) VALUES (:a,:o,CAST(:k AS uuid),:f) ON CONFLICT DO NOTHING RETURNING request_key'),params).first()
            if not fresh:
                row=db.execute(text('SELECT fingerprint,response FROM business_request WHERE actor_id=:a AND operation=:o AND request_key=CAST(:k AS uuid)'),params).one()
                if row.fingerprint!=fingerprint:raise StateConflictError('请求键已被其他内容使用')
                if row.response is None:raise StateConflictError('请求正在处理中')
                _authorize_replay(db,actor,{**values,'_module':fn.__module__},row.response)
                result_type=get_type_hints(fn).get('return')
                if inspect.isclass(result_type) and issubclass(result_type,BaseModel):return result_type.model_validate(row.response)
                return row.response
            result=fn(*args,**kwargs)
            stored=to_jsonable_python(result)
            if isinstance(stored,dict):
                one_time_credentials='initial_credentials' in stored
                stored={k:v for k,v in stored.items() if k not in {'initial_credentials','temporaryPassword','temporary_password'}}
                if one_time_credentials:stored['already_converted']=True
            db.execute(text('UPDATE business_request SET response=CAST(:r AS jsonb) WHERE actor_id=:a AND operation=:o AND request_key=CAST(:k AS uuid)'),{**params,'r':json.dumps(stored,ensure_ascii=False)})
            return result
        return wrapped
    return decorate
