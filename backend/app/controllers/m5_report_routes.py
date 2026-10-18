"""M5 report routes only. No lab auth, fixtures or frontend mounts."""
import hashlib
import logging
import re
from copy import deepcopy
from datetime import date, timedelta
from uuid import uuid4
from urllib.parse import quote
import httpx
from fastapi import APIRouter, Depends, Query
from fastapi.encoders import jsonable_encoder
from app.core.idempotency import idempotent
from app.models.user import SysUser
from fastapi.responses import Response
from sqlalchemy import select, update
from app.core.deps import require_password_changed
from app.core.errors import ForbiddenError,NotFoundError,ValidationError,StateConflictError,VersionConflictError
from app.core.responses import ok
from app.db.session import get_db
from app.models.m5_report_models import Daily,Report,Chat,GeneratedSnapshot,now,utcnow
from app.schemas.m5_report_schemas import (DailyContent,DailyIn,DailySaveIn,DecisionIn,GenerateIn,ReportSaveIn,VersionRequest,ChatIn,AIDraftIn,ReturnRequest)
from app.repositories.m5_report_repository import context,today
from app.services.m5_report_config import get_m5_settings
from app.services.m5_report_policy import (REPORT_NAMES,employee,visible_students,report_access,report_record_access,capabilities,required_access)
from app.services.m5_report_service import (daily_dto,scoped_daily_query,validate_content,save_daily,decide,metrics_for,report_dto,required_caps,snapshot_caps)
from app.services.m5_report_transactions import m5_database
from app.services.m5_report_exports import export_docx,export_pdf
from app.integrations.dify import m5_report_ai as ai
logger=logging.getLogger(__name__)
PREFIX='/api/v1/m5'

def auth_signature(user):
    return {'dept_id':user['dept_id'],'dept_ids':sorted(user['dept_ids']),'admin':user['is_admin'],'head':user['is_dept_head'],'caps':required_caps(user),'students':sorted((s['id'],s['consent']) for s in user['_students'])}


def scoped_report(db,user,rid):
    q=select(Report).where(Report.id==rid)
    if not user['is_admin']:q=q.where(Report.dept_id.in_(user['dept_ids']))
    if not user['is_dept_head']:q=q.where(Report.owner_id==user['id'])
    return db.scalar(q)

def create_m5_router(config=None):
    config=config or get_m5_settings()
    app=APIRouter(tags=['M5 日报与智能报告'])
    database=m5_database
    def actor(db=Depends(get_db),user=Depends(require_password_changed)):
        return context(db,user,business=True)

    @app.get(PREFIX+'/capabilities')
    def m5_capabilities(user=Depends(actor)):
        return ok(capabilities(user))

    @app.get(PREFIX+"/dailies")
    def daily_list(user=Depends(actor),db=Depends(database),offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=200)):
        return ok([daily_dto(d,user) for d in db.scalars(scoped_daily_query(user).order_by(Daily.report_date.desc(),Daily.id).offset(offset).limit(limit))])

    @app.get(PREFIX+"/dailies/{did}/history")
    def daily_history(did:str,user=Depends(actor),db=Depends(database)):
        from app.models.m5_report_models import DailyRevision
        from app.services.m5_report_service import restricted_daily
        d=db.scalar(scoped_daily_query(user).where(Daily.id==did))
        if not d:raise NotFoundError()
        if restricted_daily(user,d):raise ForbiddenError()
        rows=list(db.scalars(select(DailyRevision).where(DailyRevision.daily_id==did).order_by(DailyRevision.version.desc()).limit(200)))
        return ok([{'version':r.version,'approved_by':str(r.approved_by),'approved_at':r.approved_at,'content':r.content} for r in rows if required_access(user,r.required_capabilities)])

    @app.put(PREFIX+"/dailies")
    def daily_save(body:DailyIn,user=Depends(actor),db=Depends(database)):
        return ok(save_daily(db,user,body))

    @app.post(PREFIX+"/dailies/{did}/action")
    def daily_action(did:str,body:DecisionIn,user=Depends(actor),db=Depends(database)):
        return ok(decide(db,user,db.scalar(scoped_daily_query(user).where(Daily.id==did)),body))

    @app.post(PREFIX+"/reports/preview")
    def preview(body:GenerateIn,user=Depends(actor),db=Depends(database)):
        metrics,facts,warnings,scope=metrics_for(db,user,body)
        narrative="\n\n".join(x["section"]+"\n"+x["text"] for x in facts)
        state="MOCK" if config.ai_mode=="DEMO" else "UNAVAILABLE"
        db.rollback()  # Release read transaction before external AI call.
        if config.ai_mode=="DIFY":
            try:
                payload={"task":"REPORT_GENERATE","type":body.type,"start_date":body.start_date.isoformat(),"end_date":body.end_date.isoformat(),
                         "scope":scope,"metrics":metrics,"facts":facts,"warnings":warnings}
                result=ai.workflow(config,config.report_key,payload,user["id"])
                candidate=result.get("narrative")
                if not isinstance(candidate,str) or not candidate.strip():raise ValueError("Empty narrative")
                narrative=candidate;state="LIVE"
            except (httpx.HTTPError,ValueError,KeyError,TypeError) as exc:
                logger.warning("M5_REPORT_AI_FALLBACK type=%s exception=%s", body.type, type(exc).__name__)
                state="UNAVAILABLE";warnings.append("Dify不可用，已保留确定性指标和事实文本")
        else:warnings.append("当前未调用Dify，保留确定性事实文本")
        fresh=context(db,db.get(SysUser,user["id"],populate_existing=True),business=False)
        if auth_signature(fresh)!=auth_signature(user):raise StateConflictError("权限范围已变化，请重新生成")
        snapshot_id=str(uuid4())
        response={"snapshot_id":snapshot_id,"type":body.type,"title":REPORT_NAMES[body.type],"start_date":body.start_date.isoformat(),"end_date":body.end_date.isoformat(),
                   "scope":scope,"as_of":now(),"generated_at":now(),"metrics":metrics,"narrative":narrative,"ai_status":state,
                   "warnings":warnings,"facts":facts}
        db.add(GeneratedSnapshot(id=snapshot_id,owner_id=user["id"],request_data={**body.model_dump(mode="json"),"authorization":auth_signature(user)},response_data=jsonable_encoder(response),student_ids=[s["id"] for s in user["_students"] if body.type!="PSYCH_WEEK" or s["consent"]=="GRANTED"],required_capabilities=snapshot_caps(user,body.type)))
        db.flush()
        return ok(response)

    @app.get(PREFIX+"/reports")
    def report_list(user=Depends(actor),db=Depends(database)):
        employee(user)
        q=select(Report)
        if not user["is_admin"]:q=q.where(Report.dept_id.in_(user["dept_ids"]))
        if not user["is_dept_head"]:q=q.where(Report.owner_id==user["id"])
        visible=[]
        for r in db.scalars(q.order_by(Report.updated_at.desc()).limit(200)):
            try:report_access(user,r.kind)
            except ForbiddenError:continue
            try:report_record_access(user,r)
            except (ForbiddenError,NotFoundError):continue
            visible.append(report_dto(r))
        return ok(visible)

    @app.get(PREFIX+"/reports/{rid}")
    def report_detail(rid:str,user=Depends(actor),db=Depends(database)):
        r=scoped_report(db,user,rid);report_record_access(user,r);return ok(report_dto(r))

    @app.post(PREFIX+"/reports")
    @idempotent('report.save')
    def save_report(body:ReportSaveIn,user=Depends(actor),db=Depends(database)):
        report_access(user,body.type)
        if body.end_date<body.start_date or body.end_date>today():raise ValidationError("报告日期范围不正确")
        if body.id:
            r=scoped_report(db,user,body.id);report_record_access(user,r)
            if r.owner_id!=user["id"]:raise ForbiddenError("不能覆盖他人报告，请另存")
            if body.expected_version!=r.version:raise VersionConflictError(r.version)
            if r.status=="SUBMITTED":raise StateConflictError("已提交周报不提供修改功能")
            if set(r.scope_employee_ids or [])!=set(body.employee_user_ids):raise ValidationError("更新报告不能更换员工范围，请另存")
            if r.kind!=body.type or r.start_date!=body.start_date or r.end_date!=body.end_date:
                raise ValidationError("更新报告不能更换类型或统计范围，请另存")
            result=db.execute(update(Report).where(Report.id==r.id,Report.version==body.expected_version).values(
                narrative=body.narrative,title=body.title,version=r.version+1,updated_at=utcnow()))
            if result.rowcount!=1:raise VersionConflictError()
            db.flush();db.expire_all();r=db.get(Report,r.id)
        else:
            snapshot=db.get(GeneratedSnapshot,body.snapshot_id) if body.snapshot_id else None
            if not snapshot or snapshot.owner_id!=user["id"]:raise ValidationError("请先生成预览，并提供本人的snapshot_id")
            expected=GenerateIn(type=body.type,start_date=body.start_date,end_date=body.end_date,employee_user_ids=body.employee_user_ids).model_dump(mode="json")
            if {k:v for k,v in snapshot.request_data.items() if k!="authorization"}!=expected:raise ValidationError("保存条件与预览不一致，请重新生成")
            if snapshot.request_data.get("authorization")!=jsonable_encoder(auth_signature(user)) or not required_access(user,snapshot.required_capabilities):raise ForbiddenError("权限范围已变化，请重新生成")
            data=snapshot.response_data
            r=Report(id=str(uuid4()),owner_id=user["id"],dept_id=user["dept_id"],kind=body.type,title=body.title,
                start_date=body.start_date,end_date=body.end_date,narrative=body.narrative,
                metrics=data["metrics"],scope=data["scope"],scope_employee_ids=body.employee_user_ids,scope_student_ids=snapshot.student_ids,
                required_capabilities=snapshot.required_capabilities,snapshot_id=snapshot.id,warnings=data["warnings"],ai_status=data["ai_status"],status="DRAFT",version=1)
            db.add(r);db.flush()
        return ok(report_dto(r))

    @app.post(PREFIX+"/reports/{rid}/submit")
    @idempotent('report.submit')
    def submit_report(rid:str,body:VersionRequest,user=Depends(actor),db=Depends(database)):
        r=scoped_report(db,user,rid);report_record_access(user,r)
        if r.owner_id!=user["id"] or r.kind!="MANAGER_WEEK":raise ForbiddenError("仅本人主管周报需要提交")
        if r.version!=body.expected_version:raise VersionConflictError(r.version)
        if r.status!="DRAFT":raise StateConflictError("周报已提交")
        result=db.execute(update(Report).where(Report.id==rid,Report.version==body.expected_version).values(
            status="SUBMITTED",version=r.version+1,updated_at=utcnow()))
        if result.rowcount!=1:raise VersionConflictError()
        db.flush();db.expire_all();return ok(report_dto(scoped_report(db,user,rid)))

    @app.get(PREFIX+"/reports/{rid}/export/{fmt}")
    def export(rid:str,fmt:str,user=Depends(actor),db=Depends(database)):
        r=scoped_report(db,user,rid);report_record_access(user,r)
        if fmt not in {"docx","pdf"}:raise ValidationError("仅支持Word和PDF")
        content=export_docx(r) if fmt=="docx" else export_pdf(r)
        media="application/vnd.openxmlformats-officedocument.wordprocessingml.document" if fmt=="docx" else "application/pdf"
        return Response(content,media_type=media,headers={"Content-Disposition":"attachment; filename*=UTF-8''"+quote(r.title+"."+fmt)})

    @app.get(PREFIX+"/chat")
    def chat_get(user=Depends(actor),db=Depends(database)):
        employee(user)
        c=db.get(Chat,user["id"])
        if c and c.draft.get("_authorization")!=jsonable_encoder(auth_signature(user)):
            c.messages=[];c.draft={"_authorization":jsonable_encoder(auth_signature(user))};c.last_key="";c.last_result={};c.version+=1
            db.flush()
        if not c:
            c=Chat(user_id=user["id"],messages=[],draft={"_authorization":jsonable_encoder(auth_signature(user)),"report_date":today().isoformat(),"content":DailyContent().model_dump()},version=1)
            db.add(c);db.flush()
        return ok({"messages":c.messages,"draft":c.draft,"version":c.version,"ai_mode":config.ai_mode})

    @app.post(PREFIX+"/chat/messages")
    def chat_post(body:ChatIn,user=Depends(actor),db=Depends(database)):
        employee(user)
        c=db.get(Chat,user["id"])
        if not c:raise StateConflictError("请先加载会话")
        key=str(body.request_key)
        payload_hash=hashlib.sha256(body.model_dump_json().encode()).hexdigest()
        if c.last_key==key:
            if c.last_result.get("fingerprint")!=payload_hash:raise StateConflictError("请求键已被其他消息使用")
            return ok(c.last_result["response"])
        if c.version!=body.expected_version:raise VersionConflictError(c.version)
        if body.student_id and body.student_id not in {s["id"] for s in visible_students(user)}:raise NotFoundError("学生不存在")
        state=deepcopy(c.draft)
        state.pop("_authorization",None)
        if body.report_date:
            if body.report_date>today():raise ValidationError("工作日期不能晚于今天")
            state["report_date"]=body.report_date.isoformat()
        text=body.message
        history=deepcopy(c.messages)
        conversation_version=c.version
        db.rollback()  # Do not hold a database transaction while waiting for Dify.
        from app.services.m5_assistant_routing import classify, period
        route=classify(text)
        period_error=None
        try:
            requested_start,requested_end=period(text,today(),weekly=route=="REPORT") if route in {"QUERY","REPORT"} else (today(),today())
        except ValueError as exc:
            period_error=str(exc)
        if period_error:
            result={"answer":period_error,"draft":state,"missing_fields":["date_range"],"ai_status":"DETERMINISTIC","warnings":["DATE_RANGE_NEEDS_CLARIFICATION"]}
        elif route=="QUERY":
            allowed=[l for l in user["_leads"] if (user["is_admin"] or l["dept_id"] in user["dept_ids"]) and (user["is_dept_head"] or l["owner_id"]==user["id"])]
            if "新增客户" in text:
                period_start,period_end=requested_start,requested_end
                subset=[l for l in allowed if period_start.isoformat()<=l["created_date"]<=period_end.isoformat()]
                answer=period_start.isoformat()+" 至 "+period_end.isoformat()+"新增客户："+("、".join(l["name"] for l in subset) or "无")+"，共"+str(len(subset))+"人。"
            else:
                subset=[l for l in allowed if l["interest"] and not l["enrolled"]]
                answer="截至今天，当前未签约意向客户共"+str(len(subset))+"人："+("、".join(l["name"] for l in subset) or "无")+"。"
                if requested_start!=today() or requested_end!=today():
                    answer="当前意向客户只支持截至今天的状态查询，不支持还原历史状态，请到客户经营报告查看已有历史指标。"
            result={"answer":answer+" 查询范围："+("本部门" if user["is_dept_head"] else "本人")+"；来源：正式业务数据。","draft":state,"missing_fields":[],"ai_status":"DETERMINISTIC","warnings":[]}
            if config.ai_mode=="DIFY":
                try:
                    out=ai.workflow(config,config.assistant_key,{"task":"QUERY","message":text,"verified_answer":answer,"scope":user["dept_name"],"report_date":today().isoformat()},user["id"])
                    result["answer"]=answer+" 来源：正式业务数据。";result["ai_status"]="LIVE"
                except (httpx.HTTPError,ValueError,KeyError,TypeError):
                    result["warnings"]=["Dify不可用，显示后端核实结果"];result["ai_status"]="UNAVAILABLE"
        elif route=="REPORT":
            kind="PSYCH_WEEK" if "心理" in text else "COMPLAINT_WEEK" if "投诉" in text else "CUSTOMER_OPERATION" if "客户" in text else "DAILY_DAY" if "日汇总" in text else "MANAGER_WEEK" if user["is_dept_head"] else "DAILY_WEEK"
            report_access(user,kind)
            start,d=requested_start,requested_end
            if kind=="DAILY_DAY":
                if start!=d and not any(k in text for k in ("本周","这周","上周","本月","上月","上个月","这个月")) and not re.search(r"\d{4}-\d{2}-\d{2}",text):start=d
                if start!=d:raise ValidationError("日报日汇总只能选择一天，请到报告中心核对日期")
            result={"answer":"已准备"+REPORT_NAMES[kind]+"的生成条件。请点击下方按钮，到报告中心核对时间范围并生成。","draft":state,
                "proposal":{"type":kind,"start_date":start.isoformat(),"end_date":d.isoformat()},"missing_fields":[],"ai_status":"DETERMINISTIC","warnings":[]}
        elif user["is_dept_head"]:
            result={"answer":"主管无需写日报。可以询问客户数据，或输入“生成周报”准备本部门周报。","draft":state,"missing_fields":[],"ai_status":"DETERMINISTIC","warnings":[]}
        else:
            result=ai.collect(config,text,state,user["id"],history,body.student_id)
            validate_content(user,DailyContent.model_validate(result["draft"].get("content",{})).model_dump())
        fresh=context(db,db.get(SysUser,user["id"],populate_existing=True),business=False)
        if auth_signature(fresh)!=auth_signature(user):raise StateConflictError("权限范围已变化，请重新加载")
        result["draft"]["_authorization"]=jsonable_encoder(auth_signature(user))
        messages=history[-98:]+[{"role":"user","content":text,"at":now()},{"role":"assistant","content":result["answer"],"at":now(),"ai_status":result["ai_status"],"proposal":result.get("proposal")}]
        result["version"]=conversation_version+1
        updated=db.execute(update(Chat).where(Chat.user_id==user["id"],Chat.version==body.expected_version).values(
            messages=messages,draft=result["draft"],last_key=key,last_result={"fingerprint":payload_hash,"response":result},version=conversation_version+1))
        if updated.rowcount!=1:raise VersionConflictError()
        return ok(result)


    # Implement only untouched API082-087/API091 placeholders through the additive entry.
    app.add_api_route('/api/v1/reports/preview',preview,methods=['POST'])
    app.add_api_route('/api/v1/me/daily-reports',daily_list,methods=['GET'])

    @app.put('/api/v1/me/daily-reports/{report_date}')
    def m5_save_daily(report_date:date,body:DailySaveIn,user=Depends(actor),db=Depends(database)):
        return ok(save_daily(db,user,DailyIn(report_date=report_date,**body.model_dump())))

    @app.post('/api/v1/me/daily-reports/{report_date}/ai-draft')
    def m5_ai_draft(report_date:date,body:AIDraftIn,user=Depends(actor),db=Depends(database)):
        if user['is_dept_head']:raise ForbiddenError('主管填写周报，无需填写日报')
        if report_date>today():raise ValidationError('不能填写未来日期')
        if body.student_id and body.student_id not in {s['id'] for s in user['_students']}:raise NotFoundError('学生不存在')
        state={'report_date':report_date.isoformat(),'content':body.content.model_dump()}
        db.rollback()
        result=ai.collect(config,body.message,state,user['id'],[],body.student_id)
        validate_content(user,DailyContent.model_validate(result['draft']['content']).model_dump())
        return ok(result)

    def act_daily(did,action,body,user,db):
        d=db.scalar(scoped_daily_query(user).where(Daily.id==did))
        return ok(decide(db,user,d,DecisionIn(action=action,**body.model_dump())))

    @app.post('/api/v1/me/daily-reports/{report_id}/submit')
    def m5_submit_daily(report_id:str,body:VersionRequest,user=Depends(actor),db=Depends(database)):
        return act_daily(report_id,'SUBMIT',body,user,db)

    @app.post('/api/v1/me/daily-reports/{report_id}/withdraw')
    def m5_withdraw_daily(report_id:str,body:VersionRequest,user=Depends(actor),db=Depends(database)):
        return act_daily(report_id,'WITHDRAW',body,user,db)

    @app.post('/api/v1/employees/daily-reports/{report_id}/approve')
    def m5_approve_daily(report_id:str,body:VersionRequest,user=Depends(actor),db=Depends(database)):
        return act_daily(report_id,'APPROVE',body,user,db)

    @app.post('/api/v1/employees/daily-reports/{report_id}/return')
    def m5_return_daily(report_id:str,body:ReturnRequest,user=Depends(actor),db=Depends(database)):
        return act_daily(report_id,'RETURN',body,user,db)

    @app.get('/api/v1/employees/daily-reports')
    def m5_department_dailies(user=Depends(actor),db=Depends(database)):
        if not user['is_dept_head']:raise ForbiddenError('仅部门主管可查看本部门日报')
        return daily_list(user,db,0,50)

    return app
