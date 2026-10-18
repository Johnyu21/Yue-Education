"""Student assistant: model proposes, backend authorizes, user confirms through normal APIs."""
from datetime import datetime, timezone
from uuid import uuid4
from pydantic import ValidationError
from app.core.confirmation import sign_confirmation
from app.core.errors import AppError, ForbiddenError, NotFoundError
from app.core.transaction import with_business_transaction
from app.integrations.dify import ai_status, call_student_workflow
from app.repositories import student_repo
from app.schemas.assistant import AssistantResult, Proposal, SourceItem, WfStudentOutput
from app.schemas.service import ServiceCreateRequest
from app.schemas.feedback import FeedbackCreateRequest
from app.services import psych_service, student_service, feedback_service, academic_service
from app.services import assistant_session
from app.integrations.dify.contracts import validate_student


def _open_projects(db) -> list[dict]:
    """增值转化推荐用：已发布项目最小公开信息（与访客公开口径一致）。"""
    from sqlalchemy import select
    from app.models.course_project import CourseProject
    rows = db.scalars(
        select(CourseProject).where(CourseProject.is_published.is_(True))
        .order_by(CourseProject.id.asc()).limit(8)).all()
    return [{"id": str(p.id), "name": p.name, "country": p.country,
             "education_level": p.education_level} for p in rows]


# ---- 学生可见的中文渲染（聊天里不吐原始 JSON）----
_STATUS_CN = {"ENROLLED": "在读", "PAUSED": "暂停", "WITHDRAWN": "已退出"}
_ENROLL_CN = {"ENROLLED": "在读", "PAUSED": "暂停", "WITHDRAWN": "已退出", "COMPLETED": "已结业"}
_ITEM_CN = {"EXAM": "考试", "DEADLINE": "截止事项", "CLASS": "课程", "APPLICATION": "申请事项", "OTHER": "其他"}
_CASE_TYPE_CN = {"DOCUMENT": "文书", "SCHOOL": "院校", "VISA": "签证"}
_CASE_STAGE_CN = {"PROCESSING": "处理中", "COMPLETED": "已完成"}
_FB_CAT_CN = {"COMPLAINT": "投诉", "SUGGESTION": "建议", "CONSULTATION": "咨询"}
_FB_STATUS_CN = {"PENDING": "待处理", "PROCESSING": "处理中", "RESOLVED": "已解决", "CLOSED": "已关闭"}
_MATCH_CN = {"MATCH": "符合", "NO_MATCH": "不符合", "NEEDS_INFO": "待补充资料"}


def _fmt_dt(value) -> str:
    if not value:
        return ""
    from zoneinfo import ZoneInfo
    from app.core.config import settings as cfg
    return value.astimezone(ZoneInfo(cfg.business_timezone)).strftime("%m月%d日 %H:%M")


def _render_profile(dto) -> str:
    lines = [f"姓名：{dto.user.realName}｜状态：{_STATUS_CN.get(dto.status, dto.status)}"]
    if dto.classInfo:
        head = (dto.classInfo.headTeacher or {}).get("realName", "待分配")
        lines.append(f"班级：{dto.classInfo.name}｜班主任：{head}")
    if dto.advisor:
        lines.append(f"负责顾问：{dto.advisor.realName}（联系方式请通过班主任或机构获取）")
    for e in dto.enrollments:
        lines.append(f"在读项目：{e.projectName}（{_ENROLL_CN.get(e.status, e.status)}）")
    return "\n".join(lines)


def _render_scores(items, total: int) -> str:
    if not total:
        return "暂无你的成绩记录。"
    lines = [f"你共有 {total} 条成绩："]
    for x in items[:10]:
        piece = x.scoreText or (f"{x.scoreNumeric} 分" if x.scoreNumeric else "已登记")
        extra = f"（满分 {x.maxScore}）" if x.maxScore else ""
        when = f"｜评定 {x.gradedAt}" if x.gradedAt else ""
        lines.append(f"- {x.subject}：{piece}{extra}{when}")
    return "\n".join(lines)


def _render_schedules(items, total: int) -> str:
    if not total:
        return "近期没有你的日程安排。"
    lines = [f"近期日程共 {total} 项："]
    for x in items[:10]:
        when = _fmt_dt(x.startAt) or "时间待定"
        loc = f"｜地点 {x.location}" if x.location else ""
        lines.append(f"- [{_ITEM_CN.get(x.scheduleType, x.scheduleType)}] {x.title}：{when}{loc}")
    return "\n".join(lines)


def _render_cases(items, total: int) -> str:
    if not total:
        return "暂无你的留学申请进度记录。"
    lines = [f"你的留学申请共 {total} 项："]
    for x in items[:10]:
        lines.append(f"- {x.title}（{_CASE_TYPE_CN.get(x.itemType, x.itemType)}）："
                     f"{_CASE_STAGE_CN.get(x.stage, x.stage)}｜负责人：{x.assigneeDisplayName or '待分配'}")
    return "\n".join(lines)


def _render_assessment(data: dict) -> str:
    if not data.get("available"):
        return "暂无入学评估记录，完成评估并审核后可在此查看。"
    matches = data.get("projectMatches") or []
    if not matches:
        return "你的入学评估已完成，暂无可展示的项目匹配结果。"
    lines = ["你的入学评估摘要："]
    for m in matches:
        name = f"项目{m['projectId']}" if m.get("projectId") else "项目"
        lines.append(f"- {name}：{_MATCH_CN.get(m.get('decision'), m.get('decision') or '待评估')}")
    return "\n".join(lines)


def _render_feedback(items, total: int) -> str:
    if not total:
        return "你还没有提交过投诉或建议。"
    lines = [f"你共有 {total} 条反馈工单："]
    for x in items[:10]:
        res = f"｜处理结果：{x.resolution}" if x.resolution else ""
        lines.append(f"- {x.subject}（{_FB_CAT_CN.get(x.category, x.category)}）："
                     f"{_FB_STATUS_CN.get(x.status, x.status)}｜涉及教师 {x.teacherName}{res}")
    return "\n".join(lines)


def _handle_student_message(db,user,req,state,auth_token=None):
    if not user.is_student:raise ForbiddenError("仅学生可使用学生助手")
    actor_id=user.id
    profile=student_repo.get_profile_by_user(db,actor_id)
    if profile is None:raise NotFoundError("学生档案不存在")
    received=datetime.now(timezone.utc)
    consent=profile.psych_consent_status=="GRANTED"
    if consent:
        word=psych_service.detect_direct_word(req.message)
        if word:
            with with_business_transaction(db):
                psych_service.record_direct_risk(db,profile,source_event_key=psych_service._sub_key(str(req.message_id),"direct"),received_at=received,matched_word=word)
    payload={"schema_version":"1.0","message":req.message,"message_id":str(req.message_id),
        "conversation_id":req.conversation_id,"input_kind":req.input_kind,"observe_emotion":consent,
        "context":req.context.model_dump() if req.context else None,
        "open_projects":_open_projects(db)}
    payload.update(assistant_session.context(state))
    db.rollback()
    def result(answer,**kwargs):
        return AssistantResult(conversationId=req.conversation_id,messageId=str(req.message_id),answer=answer,**kwargs)
    try:
        raw=call_student_workflow(payload,actor_id)
        knowledge={k:raw.get(k,default) for k,default in (("answer",""),("sources",[]),("warnings",[]))}
        raw=validate_student(raw,payload)
        if raw["intent"] in {"FAQ","OTHER"}:
            raw.update(knowledge)
        wf=WfStudentOutput.model_validate(raw)
        state["_wf"]=wf.model_dump(exclude_none=True)
    except (AppError,ValidationError,ValueError,TypeError):
        return result("AI服务暂不可用，请使用业务表单办理。",aiStatus="UNAVAILABLE")
    profile=student_repo.get_profile_by_user(db,actor_id)
    if profile.psych_consent_status=="GRANTED" and wf.observation and wf.observation.emotion_state!="UNKNOWN":
        with with_business_transaction(db):
            psych_service.record_dify_observation(db,profile,source_event_key=psych_service._sub_key(str(req.message_id),"emotion"),received_at=received,
                emotion_state=wf.observation.emotion_state,confidence=wf.observation.confidence)
    status=ai_status()
    try:
        if wf.intent == "UPGRADE_INTEREST" and "course_project_id" in (wf.missing_fields or []):
            projects = _open_projects(db)
            if projects:
                lines = "\n".join(
                    f"{i + 1}. {p['name']}（编号 {p['id']}，{p['country'] or '国家待定'}"
                    f"{'，' + p['education_level'] if p.get('education_level') else ''}）"
                    for i, p in enumerate(projects))
                return result("目前可选的已发布升学项目如下，回复编号或项目名即可帮您登记意向：\n" + lines,
                              missingFields=wf.missing_fields, aiStatus=status)
        if wf.missing_fields:
            return result(wf.answer or "请补全业务信息。",missingFields=wf.missing_fields,aiStatus=status)
        if wf.intent=="PROFILE_QUERY":return result(_render_profile(student_service.get_self_overview(db,user)),aiStatus=status)
        if wf.intent=="FEEDBACK_QUERY":
            rows,total=feedback_service.list_my_tickets(db,user,page=1,page_size=10)
            return result(_render_feedback(rows,total),aiStatus=status)
        if wf.intent in {"SCORE_QUERY","SCHEDULE_QUERY","CASE_QUERY"}:
            handler={"SCORE_QUERY":academic_service.list_scores,"SCHEDULE_QUERY":academic_service.list_schedules,"CASE_QUERY":academic_service.list_application_cases}[wf.intent]
            render={"SCORE_QUERY":_render_scores,"SCHEDULE_QUERY":_render_schedules,"CASE_QUERY":_render_cases}[wf.intent]
            rows,total=handler(db,user,page=1,page_size=20)
            return result(render(rows,total),aiStatus=status)
        if wf.intent=="ASSESSMENT_QUERY":
            return result(_render_assessment(academic_service.get_initial_assessment(db,user)),aiStatus=status)
        draft=wf.draft or {};key=str(uuid4());operation=None
        if wf.intent=="SERVICE_DRAFT":
            data=ServiceCreateRequest(**{**draft,"request_key":key,"confirmed":True})
            student_service.validate_service_content(data)
            preview=student_service.canonical_service_payload(data);operation="SUBMIT_SERVICE"
        elif wf.intent=="FEEDBACK_DRAFT":
            data=FeedbackCreateRequest(**{**draft,"request_key":key,"confirmed":True})
            preview=feedback_service.canonical_feedback_payload(data);operation="SUBMIT_FEEDBACK"
        elif wf.intent=="UPGRADE_INTEREST":
            from app.schemas.student import UpgradeInterestRequest
            data=UpgradeInterestRequest(**{**draft,"request_key":key,"confirmed":True})
            project=student_repo.get_project(db,data.course_project_id)
            if project is None or not project.is_published:raise NotFoundError("项目不存在")
            preview={"course_project_id":data.course_project_id,"note":data.note};operation="UPGRADE_INTEREST"
        if operation:
            token=sign_confirmation(user,operation,entity_id=None,payload=preview,expected_version=None,request_key=key)
            from datetime import timedelta
            proposal=Proposal(operation=operation,preview=preview,requestKey=key,confirmationToken=token,expiresAt=received+timedelta(minutes=5))
            return result("请核对确认卡，确认后才会提交。",proposal=proposal,aiStatus=status)
        if wf.intent not in {"FAQ","OTHER",None}:return result("暂不支持该业务，请使用表单。",aiStatus=status)
        sources=[SourceItem(documentId=s.get("document_id",s.get("documentId")),title=s.get("title"),section=s.get("section")) for s in wf.sources]
        return result(wf.answer or "请描述您的问题。",sources=sources,missingFields=wf.missing_fields,aiStatus=status)
    except ValidationError as exc:
        return result("请补全业务信息后再确认。",missingFields=[str(e['loc'][0]) for e in exc.errors()],aiStatus=status)
    except AppError as exc:return result(exc.message,aiStatus=status)


def handle_student_message(db,user,req,auth_token=None):
    if not user.is_student:raise ForbiddenError("仅学生可使用学生助手")
    key,state=assistant_session.begin("student",user.id,req)
    if req.message.strip() in assistant_session.CANCEL:
        out=AssistantResult(conversationId=req.conversation_id,messageId=str(req.message_id),answer="已取消当前助手草稿。",aiStatus=ai_status())
        return assistant_session.finish(key,state,req,None,out)
    out=_handle_student_message(db,user,req,state,auth_token)
    wf=state.pop("_wf",None)
    return assistant_session.finish(key,state,req,wf,out)
