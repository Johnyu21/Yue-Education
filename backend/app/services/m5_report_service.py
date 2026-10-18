from copy import deepcopy
from datetime import timedelta
from uuid import uuid4
from sqlalchemy import select, update
from app.core.errors import ValidationError, ForbiddenError, StateConflictError, VersionConflictError, NotFoundError
from app.models.m5_report_models import Daily, Report, DailyRevision, now, utcnow
from app.core.idempotency import idempotent
from app.core.notification import notify
from app.models.organization import SysDepartment
from app.repositories.m5_report_repository import today,day
from app.services.m5_report_policy import employee, visible_students, own_daily, manager_daily, report_access, report_record_access, REPORT_NAMES, required_access

def daily_dto(d,user):
    hidden=restricted_daily(user,d)
    content={} if hidden else d.content
    return {"restricted":hidden,"id":d.id,"employee_user_id":str(d.user_id),"employee_display_name":user["_names"].get(d.user_id,"未知员工"),"dept_id":str(d.dept_id),
        "report_date":d.report_date.isoformat(),"original_text":"" if hidden else d.original_text,"content":content,"structured_content":content,
        "status":d.status,"version":d.version,"approved_version":d.approved_version,"approved_at":d.approved_at.isoformat() if d.approved_at else None,"return_reason":"" if hidden else d.return_reason,"submitted_at":d.submitted_at.isoformat() if d.submitted_at else None,"updated_at":d.updated_at.isoformat()}

def scoped_daily_query(user):
    employee(user)
    q=select(Daily)
    if not user["is_admin"]:q=q.where(Daily.dept_id.in_(user["dept_ids"]))
    return q if user["is_dept_head"] else q.where(Daily.user_id==user["id"])

def validate_content(user,content):
    allowed={s["id"] for s in visible_students(user)}
    events={e["id"]:e for e in user["_events"]}
    seen=set()
    for item in content["items"]:
        if item["category"] in {"PSYCH","COMPLAINT"} or item.get("source_event_id"):
            raise ValidationError("日报仅记录普通工作；心理与投诉明细请在专项模块记录")
        if not set(item["student_ids"])<=allowed:
            raise NotFoundError("关联学生不存在")
        eid=item.get("source_event_id")
        if eid:
            event=events.get(eid)
            if not event or event["dept_id"]!=user["dept_id"] or event["student_id"] not in item["student_ids"] or event["kind"]!=item["category"]:
                raise ValidationError("来源事件与学生或工作类型不匹配")
            if not user["is_dept_head"] and event["owner_id"]!=user["id"] and not (event["kind"]=="PSYCH" and user["role"]=="TEACHER"):
                raise ForbiddenError("不能关联他人的业务事件")
            if eid in seen:raise ValidationError("同一日报不能重复关联同一事件")
            seen.add(eid)

@idempotent("daily.save")
def save_daily(db,user,body):
    employee(user)
    if user["is_dept_head"]:raise ForbiddenError("主管填写周报，无需填写日报")
    if body.report_date>today():raise ValidationError("不能填写未来日期的日报")
    content=body.content.model_dump()
    validate_content(user,content)
    d=db.scalar(select(Daily).where(Daily.user_id==user["id"],Daily.report_date==body.report_date))
    if d:
        if d.dept_id!=user["dept_id"]:raise StateConflictError("历史日报归属原部门，调岗后请联系原部门主管")
        if d.status=="SUBMITTED":raise StateConflictError("请先撤回日报")
        if body.expected_version!=d.version:raise VersionConflictError(d.version)
        new_status="DRAFT" if d.status=="APPROVED" else d.status
        result=db.execute(update(Daily).where(Daily.id==d.id,Daily.version==body.expected_version).values(
            original_text=body.original_text,content=content,required_capabilities=[],status=new_status,version=d.version+1,updated_at=utcnow()))
        if result.rowcount!=1:raise VersionConflictError()
        db.flush();db.expire_all(); d=db.get(Daily,d.id)
    else:
        if body.expected_version is not None:raise VersionConflictError()
        d=Daily(id=str(uuid4()),user_id=user["id"],dept_id=user["dept_id"],report_date=body.report_date,
                original_text=body.original_text,content=content,required_capabilities=[],status="DRAFT",version=1)
        db.add(d);db.flush()
    return daily_dto(d,user)

@idempotent("daily.decide")
def decide(db,user,d,body):
    if not d:raise NotFoundError("日报不存在")
    if restricted_daily(user,d):raise ForbiddenError("该日报包含未授权的专项内容")
    if body.action in {"APPROVE","RETURN"}:manager_daily(user,d)
    else:own_daily(user,d)
    if d.user_id==user["id"] and body.action in {"APPROVE","RETURN"}:raise ForbiddenError("不能审核自己的日报")
    if body.action in {"APPROVE","RETURN"} and restricted_daily(user,d):raise ForbiddenError("该日报包含未授权的专项内容")
    if d.version!=body.expected_version:raise VersionConflictError(d.version)
    allowed={"SUBMIT":{"DRAFT","RETURNED"},"WITHDRAW":{"SUBMITTED"},"APPROVE":{"SUBMITTED"},"RETURN":{"SUBMITTED"}}
    if d.status not in allowed[body.action]:raise StateConflictError()
    if body.action=="SUBMIT" and (not d.content.get("work_summary","").strip() or not d.content.get("difficulties","").strip()):
        raise ValidationError("请补全今日工作和困难支持；没有困难可填写“无”")
    if body.action=="RETURN" and not body.reason.strip():raise ValidationError("请填写退回原因")
    values={"status":{"SUBMIT":"SUBMITTED","WITHDRAW":"DRAFT","APPROVE":"APPROVED","RETURN":"RETURNED"}[body.action],"version":d.version+1,"updated_at":utcnow()}
    if body.action=="SUBMIT":values["submitted_at"]=utcnow()
    if body.action=="RETURN":values["return_reason"]=body.reason
    if body.action=="APPROVE":
        values.update(approved_snapshot=deepcopy(d.content),approved_required_capabilities=d.required_capabilities,approved_version=d.version,approved_at=utcnow(),return_reason="")
        db.add(DailyRevision(id=str(uuid4()),daily_id=d.id,version=d.version,approved_by=user["id"],approved_at=values["approved_at"],content=deepcopy(d.content),required_capabilities=d.required_capabilities))
    result=db.execute(update(Daily).where(Daily.id==d.id,Daily.version==body.expected_version).values(**values))
    if result.rowcount!=1:raise VersionConflictError()
    if body.action=="SUBMIT":
        head=db.scalar(select(SysDepartment.head_user_id).where(SysDepartment.id==d.dept_id))
        if not head:raise StateConflictError("部门尚未指定主管，无法提交审核")
        notify(db,"daily:"+d.id+":submit:"+str(d.version+1),[head],category="SYSTEM",title="有日报待审核")
    elif body.action in {"RETURN","APPROVE"}:
        notify(db,"daily:"+d.id+":"+body.action+":"+str(d.version+1),[d.user_id],category="DAILY_REPORT_RETURN" if body.action=="RETURN" else "SYSTEM",title="日报已退回，请修改后重提" if body.action=="RETURN" else "日报审核已通过")
    db.flush();db.expire_all()
    return daily_dto(db.get(Daily,d.id),user)

def metrics_for(db,user,body):
    report_access(user,body.type)
    start=body.start_date.isoformat(); end=body.end_date.isoformat()
    if body.end_date>today():raise ValidationError("结束日期不能晚于今天")
    allowed_users={u["id"] for u in user["_users"] if u["status"]=="NORMAL"}
    if not user["is_dept_head"]:allowed_users={user["id"]}
    requested={int(x) for x in body.employee_user_ids if x.isdecimal()}
    if len(requested)!=len(set(body.employee_user_ids)):raise ValidationError("员工ID必须为数字")
    if not requested<=allowed_users:raise ForbiddenError("统计员工超出权限范围")
    scope_users=requested if body.employee_user_ids else allowed_users
    if body.type=="DAILY_DAY" and body.start_date!=body.end_date:raise ValidationError("日汇总请选择同一天")
    q=scoped_daily_query(user).where(Daily.report_date>=body.start_date,Daily.report_date<=body.end_date,Daily.user_id.in_(scope_users),Daily.approved_snapshot.is_not(None))
    records=[d for d in db.scalars(q) if not d.approved_required_capabilities]
    source_leads=[x for x in user["_leads"] if (user["is_admin"] or x["dept_id"] in user["dept_ids"]) and ((user["is_dept_head"] and not body.employee_user_ids) or x["owner_id"] in scope_users)]
    metrics=[]; facts=[]; warnings=["来源：正式业务表与M5审核通过的日报；客户意向为当前状态，签约不等同于实际入学"]
    def metric(key,label,value,unit="项",formula=""):
        metrics.append({"key":key,"label":label,"value":value,"unit":unit,"formula":formula,"available":True})
    if body.type=="CUSTOMER_OPERATION":
        new=[x for x in source_leads if start<=x["created_date"]<=end]
        active=[x for x in source_leads if x["interest"] and not x["enrolled"] and x["created_date"]<=end]
        converted=[x for x in source_leads if x["enrolled_date"] and start<=x["enrolled_date"]<=end]
        metric("new_customers","期间新增客户",len(new),"人","created_date在统计范围内，按客户ID去重")
        metric("intent_students","当前未签约意向客户",len(active),"人","当前意向已填写且状态为NEW/FOLLOWING；不提供历史状态快照")
        metric("enrolled","期间签约客户",len(converted),"人","signed_at在统计范围内")
        warnings.append("意向人数为当前状态；无法还原过去某日的意向状态")
        from collections import Counter
        lead_ids={l['id'] for l in source_leads}
        transitions={}
        for event in user['_lead_events']:
            if event['lead_id'] in lead_ids and start<=event['date']<=end and event['before'] and event['after'] and event['before']!=event['after']:
                transitions.setdefault(event['before']+'→'+event['after'],set()).add(event['lead_id'])
        trend=Counter(x['created_date'] for x in new)
        path_facts=[{'section':'期间转化路径','text':'；'.join(k+'：'+str(len(v))+'人' for k,v in sorted(transitions.items())) or '无状态迁移事件'},
                    {'section':'新增客户日期趋势','text':'；'.join(k+'：'+str(v)+'人' for k,v in sorted(trend.items())) or '无新增'}]

        facts=[{"section":"新增客户","text":"、".join(x["name"] for x in new) or "无"},
               {"section":"接待与跟进","text":"；".join(x["name"]+"："+x["next_action"] for x in source_leads) or "无记录"},
               {"section":"意向学生","text":"、".join(x["name"] for x in active) or "无"},
               {"section":"签约转化","text":"、".join(x["name"] for x in converted) or "无"},
               {"section":"待跟进事项","text":"；".join(x["next_action"] for x in source_leads if not x["enrolled"]) or "无"}]+path_facts
    else:
        metric("approved_daily","已通过有效日报",len(records),"篇","每员工每日一份，使用最近通过内容")
        items=[i for d in records for i in d.approved_snapshot.get("items",[])]
        if body.type in {"PSYCH_WEEK","COMPLAINT_WEEK"}:
            kind="PSYCH" if body.type=="PSYCH_WEEK" else "COMPLAINT"
            teacher_psych=body.type=="PSYCH_WEEK" and user["role"]=="TEACHER" and not user["is_dept_head"]
            assigned_students={s["id"] for s in visible_students(user) if s["teacher_id"]==user["id"]} if teacher_psych else set()
            upstream=[e for e in user["_events"] if e["kind"]==kind and (user["is_admin"] or e["dept_id"] in user["dept_ids"]) and (e["student_id"] in assigned_students if teacher_psych else ((user["is_dept_head"] and not body.employee_user_ids) or e["owner_id"] in scope_users)) and e["created_date"]<=end and (e["updated_date"]>=start or e["status"] not in {"CLOSED","RESOLVED","DISMISSED"})]
            linked={e["id"] for e in upstream}; daily_only=[]
            seen=set()
            for d in records:
                for index,i in enumerate(d.approved_snapshot.get("items",[])):
                    if i["category"]!=kind:continue
                    if teacher_psych and (not i.get("student_ids") or not set(i["student_ids"])<=assigned_students):
                        if "未关联负责学生的日报心理工作不计入本周报" not in warnings:warnings.append("未关联负责学生的日报心理工作不计入本周报")
                        continue
                    eid=i.get("source_event_id")
                    key=eid or d.id+":"+str(index)
                    if key in linked or key in seen:continue
                    seen.add(key);daily_only.append(i)
            new=[e for e in upstream if e["created_date"]>=start]
            continuing=[e for e in upstream if e["created_date"]<start]
            previous_end=body.start_date-timedelta(days=1);previous_start=previous_end-(body.end_date-body.start_date)
            previous_events=[e for e in user["_events"] if e["kind"]==kind and previous_start.isoformat()<=e["created_date"]<=previous_end.isoformat() and (user["is_admin"] or e["dept_id"] in user["dept_ids"]) and (e["student_id"] in assigned_students if teacher_psych else ((user["is_dept_head"] and not body.employee_user_ids) or e["owner_id"] in scope_users))]
            metric("previous_new_events","上一等长期间新增业务事件",len(previous_events),"项",str(previous_start)+" 至 "+str(previous_end))
            metric("new_events","期间新增业务事件",len(new))
            metric("continuing","此前发生本期跟进",len(continuing))
            metric("daily_supplements","日报补充待核对",sum(i["count"] for i in daily_only))
            metric("resolved","期间解决业务事件",sum(bool(e.get("closed_date") or e.get("resolved_date")) and start<=(e.get("closed_date") or e.get("resolved_date"))<=end for e in upstream))
            for section,entries in [("本期新增",new),("此前发生仍在跟进",continuing)]:
                facts.append({"section":section,"text":"；".join(e["id"]+"："+e["summary"]+"，"+e["action"] for e in entries) or "无记录"})
            facts.append({"section":"日报补充","text":"；".join(i["description"] for i in daily_only) or "无未关联事项"})
            facts.append({"section":"待跟进与协调","text":"；".join(e["summary"] for e in upstream if e["status"] not in {"CLOSED","RESOLVED","DISMISSED"}) or "无未解决记录"})
            if daily_only:warnings.append("未关联业务事件的日报补充单独列示，不直接计入事件总数，避免重复统计")
        else:
            for category,label in [("CUSTOMER","客户跟进"),("DELIVERY","学生交付"),("ENROLLMENT","入学跟踪"),("PSYCH","心理相关工作"),("COMPLAINT","投诉处理"),("LEAVE","请假处理")]:
                relevant=[i for i in items if i["category"]==category]
                if category=="PSYCH" and not user["psych_access_enabled"]:continue
                if category=="COMPLAINT" and not user["can_handle_feedback"]:continue
                metric(category.lower(),label,sum(i["count"] for i in relevant),"次","日报申报工作量，不等同于新增业务事件或去重人数")
            for d in records:
                facts.append({"section":"审核依据","text":d.id+"：通过版本 "+str(d.approved_version)+"，审核时间 "+str(d.approved_at)})
                approved=d.approved_snapshot
                all_items=approved.get("items",[])
                visible=[i for i in all_items if not (i["category"]=="PSYCH" and not user["psych_access_enabled"]) and not (i["category"]=="COMPLAINT" and not user["can_handle_feedback"])]
                summary="；".join(i["description"] for i in visible) if len(visible)!=len(all_items) else approved.get("work_summary","")
                facts.append({"section":user["_names"].get(d.user_id,"未知员工")+" "+d.report_date.isoformat(),"text":summary or "无可展示工作明细"})
                if len(visible)==len(all_items) and approved.get("next_plan", "").strip():
                    facts.append({"section":"明日计划", "text":user["_names"].get(d.user_id,"未知员工")+"："+approved["next_plan"]})
            facts.extend([{"section":"未完成事项","text":"请根据实际工作补充，系统不自动推断完成情况"},
                          {"section":"困难与支持","text":"；".join(dict.fromkeys(d.approved_snapshot.get("difficulties","") for d in records if not (any((i["category"]=="PSYCH" and not user["psych_access_enabled"]) or (i["category"]=="COMPLAINT" and not user["can_handle_feedback"]) for i in d.approved_snapshot.get("items",[]))))) or "暂无可展示的困难记录"}])
            if body.type=="MANAGER_WEEK":
                metric("new_customers","期间新增客户",sum(start<=x["created_date"]<=end for x in source_leads),"人","按创建日期与客户ID统计")
                metric("enrolled_students","期间签约客户",sum(bool(x["enrolled_date"]) and start<=x["enrolled_date"]<=end for x in source_leads),"人","按签约日期统计")
                facts.extend([{"section":"团队管理情况","text":"待主管补充人员安排、新人培养与协作情况"},
                              {"section":"主要问题及处理措施","text":"待主管核对补充"},
                              {"section":"需要协调的支持","text":"待主管填写，没有可填无"},
                              {"section":"下周工作安排","text":"选填"}])
    if body.type=="CUSTOMER_OPERATION":
        lost=[x for x in source_leads if x["lost_date"] and start<=x["lost_date"]<=end]
        metric("lost_customers","期间流失客户",len(lost),"人","lost_at在统计范围内")
        metric("conversion_rate","新增客户当前签约率",round(100*sum(x["enrolled"] for x in new)/len(new),2) if new else None,"%","新增客户中当前已签约人数/本期新增客户数；分母为0时无值")
        from collections import Counter
        for field,label in [("source","来源分布"),("education","学历分布"),("loss_reason","流失原因")]:
            grouped=Counter((x.get(field) or "未填写") for x in (lost if field=="loss_reason" else new))
            facts.append({"section":label,"text":"；".join(str(k)+"："+str(v) for k,v in sorted(grouped.items())) or "无记录"})
        previous_end=body.start_date-timedelta(days=1);previous_start=previous_end-(body.end_date-body.start_date)
        previous=[x for x in source_leads if previous_start.isoformat()<=x["created_date"]<=previous_end.isoformat()]
        metric("previous_new_customers","上一等长期间新增客户",len(previous),"人",str(previous_start)+" 至 "+str(previous_end))
    if body.type in {"DAILY_DAY","DAILY_WEEK","MANAGER_WEEK"}:
        daily_users={u["id"] for u in user["_users"] if u.get("writes_daily",True)} & scope_users
        expected=len(daily_users)*((body.end_date-body.start_date).days+1)
        metric("expected_daily","范围员工自然日应报基数",expected,"篇","所选有效员工数×自然日数，未接入排班日历")
        metric("daily_coverage","审核通过覆盖率",round(len(records)*100/expected,2) if expected else None,"%","已通过日报/自然日应报基数")
    if body.type=="PSYCH_WEEK":
        final={}
        observed_ids={s["id"] for s in user["_students"] if not body.employee_user_ids or s["owner_id"] in scope_users or s["teacher_id"] in scope_users}
        if user["role"]=="TEACHER" and not user["is_dept_head"]:observed_ids={s["id"] for s in user["_students"] if s["teacher_id"]==user["id"]}
        for observation in user["_observations"]:
            if observation["student_id"] in observed_ids and start<=observation["date"]<=end:final[(observation["student_id"],observation["date"])]=observation
        denominator=sum(s["id"] in observed_ids and s["consent"]=="GRANTED" and not s["is_demo"] for s in user["_students"])*((body.end_date-body.start_date).days+1)
        metric("observed_student_days","有效观测学生日",len(final),"学生日","同一学生同一自然日取最后有效版本")
        metric("unobserved_student_days","缺少有效观测的学生日",max(0,denominator-len(final)),"学生日","不将未观测自动判为健康")
        metric("observation_coverage","有效观测覆盖率",round(100*len(final)/denominator,2) if denominator else None,"%","有效观测学生日/有当前同意的非演示学生自然日基数")
        for emotion in ("HEALTHY","NEGATIVE","VERY_NEGATIVE","UNKNOWN"):
            metric("emotion_"+emotion.lower(),emotion,sum(o["emotion"]==emotion for o in final.values()),"学生日")
        metric("high_risk","高优先级关怀事件",sum(e.get("severity")=="HIGH" for e in upstream),"项","包括规则直接触发事件")
    if body.type=="COMPLAINT_WEEK":
        from datetime import datetime,timezone
        current=datetime.now(timezone.utc)
        metric("open_tickets","未关闭投诉",sum(e["status"] not in {"CLOSED","RESOLVED"} for e in upstream))
        metric("overdue_tickets","当前超期未解决投诉",sum(e["status"] not in {"CLOSED","RESOLVED"} and bool(e.get("due_at")) and datetime.fromisoformat(e["due_at"])<current for e in upstream))
        ratings=[e["rating"] for e in upstream if e.get("rating") is not None and e.get("rated_date") and start<=e["rated_date"]<=end]
        metric("rating_count","满意度样本",len(ratings),"份")
        metric("rating_average","平均满意度",round(sum(ratings)/len(ratings),2) if ratings else None,"分","仅统计已评分工单")
        metric("reopened","重开次数",sum(start<=d<=end for e in upstream for d in e.get("reopened_dates",[])),"次")
        for key,label,end_key in [("first_response_hours","平均首次响应时长","first_response_at"),("resolution_hours","平均解决时长","resolved_at")]:
            hours=[(datetime.fromisoformat(e[end_key])-datetime.fromisoformat(e["created_at"])).total_seconds()/3600 for e in upstream if e.get(end_key) and start<=day(e[end_key])<=end]
            metric(key,label,round(sum(hours)/len(hours),2) if hours else None,"小时","仅统计已有对应时间戳的工单")
    if not records and body.type!="CUSTOMER_OPERATION":warnings.append("当前范围没有已通过日报；相关业务记录仍按权限独立统计")
    scope="本部门" if user["is_dept_head"] else "本人负责的学生" if body.type=="PSYCH_WEEK" and user["role"]=="TEACHER" else "本人"
    return metrics,facts,warnings,scope+" · "+user["dept_name"]

def report_dto(r):
    return {"id":r.id,"snapshot_id":r.snapshot_id,"owner_id":str(r.owner_id),"type":r.kind,"title":r.title,"start_date":r.start_date.isoformat(),"end_date":r.end_date.isoformat(),"narrative":r.narrative,
            "metrics":r.metrics,"scope":r.scope,"employee_user_ids":r.scope_employee_ids,"ai_status":r.ai_status,"warnings":r.warnings,"status":r.status,
            "version":r.version,"created_at":r.created_at.isoformat(),"updated_at":r.updated_at.isoformat()}

def snapshot_caps(user,kind):
    if kind=="CUSTOMER_OPERATION":return []
    if kind=="PSYCH_WEEK":return ["psych_access_enabled"]
    if kind=="COMPLAINT_WEEK":return ["can_handle_feedback"]
    return []

def required_caps(user):
    # Free text can include sensitive material even without a tagged work item.
    return [key for key in ('psych_access_enabled','can_handle_feedback') if user.get(key)]

def restricted_daily(user,d):
    return bool(d) and not required_access(user,d.required_capabilities)
