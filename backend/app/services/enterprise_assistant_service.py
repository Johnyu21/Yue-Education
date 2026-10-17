"""
企业智能助手（API029）消息编排

分工（02 文档 / M3 模块文档）：
  - Dify（WF_ENTERPRISE）：意图识别、参数提取、知识库问答；不执行写操作。
  - Python：权限校验、对象消歧、授权查询、文本渲染、写操作提议 + confirmation_token。
  - 写操作确认后由前端调普通业务接口，后端再次鉴权 + 乐观锁 + 幂等。
"""
import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from pydantic import ValidationError as SchemaValidationError
from app.core.config import settings
from app.core import runtime_state
from sqlalchemy.orm import Session

from app.core.confirmation import CONFIRM_TTL_MINUTES, new_request_key, sign_confirmation
from app.integrations.dify import ai_status as ai_status_fn
from app.core.errors import (
    AIBadResponseError,
    AITimeoutError,
    AIUnavailableError,
    AppError,
    ForbiddenError,
    InvalidRequestError,
    NotFoundError,
)
from app.integrations.dify import run_enterprise_workflow
from app.models.application_progress import StudentApplicationProgress
from app.models.organization import SysDepartment
from app.models.student import StudentProfile
from app.models.user import SysUser
from app.repositories.common import visible_student_ids
from app.schemas.application import ApplicationAdvanceIn
from app.schemas.assistant import AssistantRequest, AssistantResult, Proposal, SourceItem
from app.schemas.assistant_enterprise import (
    ALLOWED_INTENTS,
    READ_INTENTS,
    WRITE_INTENTS,
    WfEnterpriseOutput,
)
from app.schemas.feedback import FeedbackHandlingRequest
from app.schemas.lead import FollowUpIn, LeadManualIn, LeadTransitionIn
from app.schemas.psych import PsychActionRequest
from app.services import (
    academic_service,
    crm_service,
    m3_canonical,
    metric_service,
    psych_service,
    staff_feedback_service,
    student_service,
    todo_service,
)

logger = logging.getLogger(__name__)

# 短期会话缓存（15 分钟，仅存候选对象 id，不存聊天正文）
_CACHE_TTL = timedelta(minutes=15)

_KNOWLEDGE_REPLY = "该问题需要员工知识库支持，目前资料不足，请联系行政或查看制度文件。"


# =============================================================
# 工具
# =============================================================
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def _cache_put(conversation_id: str | None, kind: str, ids: list[int]) -> None:
    if not conversation_id:
        return
    runtime_state.put("employee:"+conversation_id,{"kind":kind,"ids":ids},900)


def _cache_get(conversation_id: str | None) -> dict | None:
    if not conversation_id:
        return None
    return runtime_state.get("employee:"+conversation_id)


def _is_head(db: Session, actor: SysUser) -> bool:
    return db.scalar(select(SysDepartment.id).where(
        SysDepartment.head_user_id == actor.id).limit(1)) is not None


def _build_payload(db: Session, actor: SysUser, req: AssistantRequest) -> dict:
    return {
        "schema_version": "1.0",
        "message": req.message,
        "message_id": str(req.message_id),
        "conversation_id": req.conversation_id,
        "context": req.context.model_dump() if req.context else None,
        "actor": {
            "id": str(actor.id),
            "real_name": actor.real_name,
            "employee_role": actor.employee_role,
            "dept_id": str(actor.dept_id) if actor.dept_id else None,
            "is_dept_head": _is_head(db, actor),
            "can_handle_feedback": bool(actor.can_handle_feedback),
            "psych_access_enabled": bool(actor.psych_access_enabled),
        },
    }


def _result(req: AssistantRequest, answer: str, *, proposal: Proposal | None = None,
            missing: list[str] | None = None, sources: list[dict] | None = None,
            warnings: list[str] | None = None, ai_status: str = "LIVE") -> AssistantResult:
    return AssistantResult(
        conversationId=req.conversation_id,
        messageId=str(req.message_id),
        answer=answer,
        sources=[SourceItem(documentId=s.get("document_id",s.get("documentId")),title=s.get("title"),section=s.get("section")) for s in (sources or []) if isinstance(s,dict)],
        missingFields=missing or [],
        proposal=proposal,
        aiStatus=ai_status if ai_status == "UNAVAILABLE" else ai_status_fn(),
        warnings=warnings or [],
    )


# =============================================================
# 文本渲染
# =============================================================
def _render_lead_list(items, total: int) -> str:
    lines = [f"找到 {total} 个客户："]
    for idx, item in enumerate(items[:10], start=1):
        owner = item.ownerDisplayName or "未分配"
        lines.append(f"{idx}. {item.name or '未命名'}｜{item.status}｜负责人：{owner}｜{item.mobileMasked}")
    if total > 10:
        lines.append(f"（仅显示前 10 条，共 {total} 条）")
    lines.append("回复编号可查看详情。")
    return "\n".join(lines)


def _render_lead_detail(dto) -> str:
    lines = [
        f"客户：{dto.name or '未命名'}（{dto.status}）",
        f"手机号：{dto.mobileMasked}",
        f"学历：{dto.education or '未填写'}｜城市：{dto.city or '未填写'}",
        f"负责人：{dto.ownerDisplayName or '未分配'}",
    ]
    if dto.nextFollowUpAt:
        lines.append(f"下次跟进：{_iso(dto.nextFollowUpAt)}")
    lines.append("需要看跟进记录请说“查跟进记录”。")
    return "\n".join(lines)


def _render_followups(items, total: int) -> str:
    if total == 0:
        return "该客户暂无跟进记录。"
    lines = [f"最近 {min(total, 10)} 条跟进（共 {total} 条）："]
    for item in items[:10]:
        when = _iso(item.createTime) or ""
        lines.append(f"- {when}｜{item.followUpType}｜{item.content}")
    return "\n".join(lines)


def _render_todos(items, total: int) -> str:
    if total == 0:
        return "当前没有待办事项。"
    lines = [f"你有 {total} 项待办："]
    for item in items[:10]:
        lines.append(f"- [{item.type}] {item.title}")
    return "\n".join(lines)


def _render_services(items, total: int) -> str:
    if total == 0:
        return "当前没有待处理申请。"
    lines = [f"共 {total} 条申请："]
    for item in items[:10]:
        lines.append(f"- #{item.id}｜{item.title}｜{item.status}｜处理人：{item.assigneeDisplayName or '未指派'}")
    return "\n".join(lines)


def _render_tickets(items, total: int) -> str:
    if total == 0:
        return "售后池暂无待受理工单。"
    lines = [f"共 {total} 条售后工单："]
    for item in items[:10]:
        lines.append(f"- #{item['id']}｜{item['category']}｜{item['status']}｜优先级：{item['priority']}")
    lines.append("要处理请说“解决编号 X 的工单”。")
    return "\n".join(lines)


def _render_alerts(items, total: int) -> str:
    if total == 0:
        return "当前没有待复核的关怀事项。"
    lines = [f"共 {total} 条待复核关怀事项："]
    for item in items[:10]:
        lines.append(f"- #{item.id}｜{item.studentDisplayName}｜{item.severity}｜{item.status}")
    lines.append("可记录跟进说明，但内容仅对有权限人员可见。")
    return "\n".join(lines)


def _render_metric(data: dict) -> str:
    rng = data.get("range", {}).get("label") or ""
    if data.get("items"):
        lines = [f"{data['label']}（{rng}）："]
        for item in data["items"]:
            lines.append(f"- {item['label']}：{item['value']}")
        return "\n".join(lines)
    return f"{data['label']}（{rng}）：{data.get('value', 0)}"


# =============================================================
# 对象解析
# =============================================================
def _search_leads(db: Session, actor: SysUser, params: dict):
    view = "pool" if params.get("view") == "pool" else "mine"
    items, total = crm_service.list_leads(
        db, actor, view=view,
        keyword=params.get("keyword") or params.get("lead_name") or params.get("name"),
        status=params.get("status"), page=1, page_size=10)
    if total == 0 and view == "mine":
        # 顾问在自己的客户里找不到时，再查本部门公共池（只给摘要）
        items, total = crm_service.list_leads(
            db, actor, view="pool",
            keyword=params.get("keyword") or params.get("lead_name") or params.get("name"),
            status=params.get("status"), page=1, page_size=10)
    return items, total


def _resolve_lead_id(db: Session, actor: SysUser, params: dict) -> int | None:
    if params.get("lead_id"):
        return int(params["lead_id"])
    items, total = _search_leads(db, actor, params)
    if total == 1:
        return int(items[0].id)
    return None


def _find_students(db: Session, actor: SysUser, name: str | None) -> list[StudentProfile]:
    if not name:
        return []
    ids = visible_student_ids(db, actor)
    stmt = (select(StudentProfile)
            .join(SysUser, StudentProfile.user_id == SysUser.id)
            .where(SysUser.real_name.ilike(f"%{name}%")))
    if ids is not None:
        stmt = stmt.where(StudentProfile.id.in_(ids))
    return list(db.scalars(stmt.limit(10)).all())


def _latest_case_event(db: Session, case_no: str) -> StudentApplicationProgress | None:
    try:
        cid = UUID(case_no)
    except ValueError:
        return None
    return db.scalar(select(StudentApplicationProgress)
                     .where(StudentApplicationProgress.case_no == cid)
                     .order_by(StudentApplicationProgress.sequence_no.desc())
                     .limit(1))


# =============================================================
# 读意图
# =============================================================
def _handle_read(db: Session, actor: SysUser, req: AssistantRequest,
                 wf: WfEnterpriseOutput) -> AssistantResult:
    params = wf.params or {}
    intent = wf.intent

    if intent=="ORG_SEARCH":
        q=select(SysUser).where(SysUser.user_type=='EMPLOYEE',SysUser.status=='NORMAL')
        keyword=str(params.get('keyword') or params.get('name') or '').strip()
        if keyword:q=q.where(SysUser.real_name.ilike('%'+keyword+'%'))
        people=list(db.scalars(q.order_by(SysUser.id).limit(30)))
        return _result(req,'组织通讯录：\n'+'\n'.join(str(p.id)+'｜'+p.real_name+'｜'+str(p.employee_role or '') for p in people))
    if intent=="DAILY_SEARCH":
        from app.repositories.m5_report_repository import context
        from app.services.m5_report_service import scoped_daily_query,daily_dto
        from app.models.m5_report_models import Daily
        user=context(db,actor)
        records=[daily_dto(d,user) for d in db.scalars(scoped_daily_query(user).order_by(Daily.report_date.desc()).limit(20))]
        return _result(req,'最近日报：\n'+'\n'.join(d['report_date']+'｜'+d['employee_display_name']+'｜'+d['status']+('｜专项内容无权限' if d['restricted'] else '｜'+d['content'].get('work_summary','')) for d in records))

    try:
        if intent in ("LEAD_SEARCH", "LEAD_DETAIL"):
            items, total = _search_leads(db, actor, params)
            if total == 0:
                return _result(req, "未找到符合条件的客户。")
            if total == 1:
                dto = crm_service.get_lead(db, actor, int(items[0].id))
                return _result(req, _render_lead_detail(dto))
            _cache_put((str(actor.id)+":"+req.conversation_id) if req.conversation_id else None, "lead", [int(i.id) for i in items])
            return _result(req, _render_lead_list(items, total),
                           missing=["selection"])

        if intent == "FOLLOWUP_LIST":
            lead_id = _resolve_lead_id(db, actor, params)
            if lead_id is None:
                return _result(req, "请提供客户姓名或编号，我帮你查跟进记录。",
                               missing=["lead_id"])
            items, total = crm_service.list_follow_ups(db, actor, lead_id, page_size=10)
            return _result(req, _render_followups(items, total))

        if intent == "TODO_LIST":
            items, total = todo_service.list_todos(db, actor, page_size=20)
            return _result(req, _render_todos(items, total))

        if intent == "SERVICE_LIST":
            items, total = student_service.list_services(
                db, actor, status=params.get("status"), page=1, page_size=10)
            return _result(req, _render_services(items, total))

        if intent == "FEEDBACK_LIST":
            items, total = staff_feedback_service.list_staff_tickets(
                db, actor, assignee=params.get("assignee", "pool"),
                status=params.get("status"), page=1, page_size=10)
            return _result(req, _render_tickets(items, total))

        if intent == "PSYCH_LIST":
            items, total = psych_service.list_alerts(
                db, actor, status=params.get("status"),
                severity=params.get("severity"), page=1, page_size=10)
            return _result(req, _render_alerts(items, total))

        if intent == "APPLICATION_SEARCH":
            students = _find_students(db, actor, params.get("student_name"))
            if not students:
                return _result(req, "请提供学生姓名，我帮你查申请进度。",
                               missing=["student_name"])
            if len(students) > 1:
                return _result(req, "找到多位同名/相近学生，请提供更精确的姓名。",
                               missing=["student_name"])
            items, total = academic_service.list_application_cases(
                db, actor, student_id=students[0].id, page=1, page_size=10)
            if total == 0:
                return _result(req, "该学生暂无申请进度记录。")
            lines = [f"共 {total} 个申请事项："]
            for item in items[:10]:
                lines.append(f"- {item.caseNo}｜{item.title}｜{item.stage}")
            return _result(req, "\n".join(lines))

        if intent == "METRIC_QUERY":
            data = metric_service.run_metric(
                db, actor,
                metric=params.get("metric") or "LEAD_COUNT",
                time_range=params.get("time_range") or "THIS_MONTH",
                filters=params.get("filters") or {},
                group_by=params.get("group_by"))
            return _result(req, _render_metric(data))
    except (ForbiddenError, NotFoundError, InvalidRequestError) as exc:
        return _result(req, exc.message, warnings=[exc.code])

    return _result(req, wf.answer or "暂不支持该查询。", warnings=["INTENT_NOT_HANDLED"])


# =============================================================
# 写意图：只签发提议，不写库
# =============================================================
def _proposal(actor: SysUser, operation: str, *, entity_id: int | None,
              payload: dict, expected_version: int | None, preview: dict,
              answer: str) -> tuple[Proposal, str]:
    rk = new_request_key()
    token = sign_confirmation(actor, operation, entity_id=entity_id,
                              payload=payload, expected_version=expected_version,
                              request_key=rk)
    return Proposal(
        operation=operation, entityId=str(entity_id) if entity_id is not None else None,
        preview=preview, expectedVersion=expected_version,
        requestKey=rk, confirmationToken=token,
        expiresAt=_now() + timedelta(minutes=CONFIRM_TTL_MINUTES),
    ), answer


def _handle_write(db: Session, actor: SysUser, req: AssistantRequest,
                  wf: WfEnterpriseOutput) -> AssistantResult:
    draft = wf.draft or {}
    params = wf.params or {}
    intent = wf.intent

    if intent == "DAILY_DRAFT":
        return _result(req,"请在日报助手核对日期并生成草稿；确认后再保存和提交审核。",proposal=Proposal(operation="DAILY_DRAFT",preview={"assistantEndpoint":"/api/v1/m5/chat/messages","saveEndpoint":"/api/v1/m5/dailies","draft":draft}))

    if intent == "LEAD_CREATE":
        name = str(draft.get("name") or "").strip()
        mobile = str(draft.get("mobile") or "").strip()
        missing = [k for k, v in (("name", name), ("mobile", mobile)) if not v]
        if missing:
            return _result(req, "请补充客户姓名和手机号后再确认。", missing=missing)
        try:
            data = LeadManualIn(
                name=name, mobile=mobile, request_key=UUID(new_request_key()),
                gender=draft.get("gender"), city=draft.get("city"),
                education=draft.get("education"),
                intended_project_id=draft.get("intended_project_id"),
                study_purpose=draft.get("study_purpose"),
                interest_level=draft.get("interest_level"),
                content=draft.get("content"))
        except Exception:
            return _result(req, "客户信息不完整或格式不正确，请补充后再试。",
                           missing=["name", "mobile"])
        proposal, answer = _proposal(
            actor, "CREATE_LEAD", entity_id=None,
            payload=m3_canonical.lead_create_payload(data),
            expected_version=None,
            preview=m3_canonical.lead_create_payload(data),
            answer=f"将创建客户「{name} / {mobile}」，请确认。")
        return _result(req, answer, proposal=proposal)

    if intent in ("FOLLOWUP_ADD", "LEAD_CHANGE_STATUS"):
        lead_id = _resolve_lead_id(db, actor, params)
        if lead_id is None:
            items, total = _search_leads(db, actor, params)
            if total > 1:
                _cache_put((str(actor.id)+":"+req.conversation_id) if req.conversation_id else None, "lead", [int(i.id) for i in items])
                return _result(req, _render_lead_list(items, total), missing=["selection"])
            return _result(req, "请提供客户姓名或编号。", missing=["lead_id"])
        lead = crm_service.get_lead(db, actor, lead_id)

        if intent == "FOLLOWUP_ADD":
            content = str(draft.get("content") or params.get("content") or "").strip()
            if not content:
                return _result(req, "请告诉我跟进内容。", missing=["content"])
            try:
                plan={"next_follow_up_at":params["next_follow_up_at"]} if "next_follow_up_at" in params else {}
                data = FollowUpIn(content=content, expected_version=lead.version,
                                  request_key=UUID(new_request_key()),**plan)
            except Exception:
                return _result(req, "跟进内容格式不正确，请重试。", missing=["content"])
            proposal, answer = _proposal(
                actor, "ADD_FOLLOWUP", entity_id=lead_id,
                payload=m3_canonical.follow_up_payload(data),
                expected_version=lead.version,
                preview={"leadId": str(lead_id), "content": content,
                         "nextFollowUpAt": _iso(data.next_follow_up_at),"nextFollowUpAtProvided":"next_follow_up_at" in data.model_fields_set},
                answer=f"将为客户「{lead.name}」记录跟进：{content}。请确认。")
            return _result(req, answer, proposal=proposal)

        target = str(params.get("target_status") or draft.get("target_status") or "").upper()
        if target not in ("FOLLOWING", "LOST"):
            target = "LOST" if "流失" in req.message else "FOLLOWING"
        reason = str(draft.get("reason") or params.get("reason") or "").strip()
        if not reason:
            return _result(req, "请说明变更原因。", missing=["reason"])
        try:
            data = LeadTransitionIn(target_status=target, reason=reason,
                                    expected_version=lead.version,
                                    request_key=UUID(new_request_key()))
        except Exception:
            return _result(req, "状态变更参数不正确。", missing=["target_status", "reason"])
        proposal, answer = _proposal(
            actor, "TRANSITION_LEAD", entity_id=lead_id,
            payload=m3_canonical.transition_payload(data),
            expected_version=lead.version,
            preview={"leadId": str(lead_id), "targetStatus": target, "reason": reason},
            answer=f"将把客户「{lead.name}」标记为 {target}，原因：{reason}。请确认。")
        return _result(req, answer, proposal=proposal)

    if intent == "LEAVE_DECIDE":
        service_id = params.get("service_id")
        if not service_id:
            items, total = student_service.list_services(
                db, actor, status="PENDING", page=1, page_size=10)
            if total == 0:
                return _result(req, "当前没有待你审批的申请。")
            return _result(req, _render_services(items, total), missing=["service_id"])
        dto = student_service.get_service(db, actor, int(service_id))
        decision = str(params.get("decision") or draft.get("decision") or "APPROVE").upper()
        if decision not in ("APPROVE", "REJECT"):
            decision = "APPROVE"
        note = str(params.get("note") or draft.get("note") or
                   ("同意" if decision == "APPROVE" else "驳回")).strip()
        payload = m3_canonical.decide_service_payload(decision, note)
        proposal, answer = _proposal(
            actor, "DECIDE_SERVICE", entity_id=int(service_id),
            payload=payload, expected_version=dto.version,
            preview={"serviceId": str(service_id), "title": dto.title,
                     "decision": decision, "note": note},
            answer=f"将{'批准' if decision == 'APPROVE' else '驳回'}申请「{dto.title}」。请确认。")
        return _result(req, answer, proposal=proposal)

    if intent == "FEEDBACK_HANDLE":
        ticket_id = params.get("ticket_id")
        if not ticket_id:
            items, total = staff_feedback_service.list_staff_tickets(
                db, actor, assignee="pool", page=1, page_size=10)
            if total == 0:
                return _result(req, "售后池当前没有待受理工单。")
            return _result(req, _render_tickets(items, total), missing=["ticket_id"])
        ticket = staff_feedback_service.get_staff_ticket(db, actor, int(ticket_id))
        action = str(params.get("action") or ("RESOLVE" if "解决" in req.message else "NOTE")).upper()
        note = str(params.get("note") or draft.get("note") or "已跟进").strip()
        resolution = params.get("resolution") or draft.get("resolution")
        if action == "RESOLVE" and not resolution:
            return _result(req, "解决工单需要填写处理结果。", missing=["resolution"])
        try:
            data = FeedbackHandlingRequest(
                action=action, note=note, resolution=resolution,
                assignee_user_id=params.get("assignee_user_id"),
                expected_version=ticket["version"], request_key=UUID(new_request_key()))
        except Exception:
            return _result(req, "工单处理参数不正确。", missing=["action", "note"])
        proposal, answer = _proposal(
            actor, "HANDLE_FEEDBACK", entity_id=int(ticket_id),
            payload=m3_canonical.feedback_handling_payload(data),
            expected_version=ticket["version"],
            preview={"ticketId": str(ticket_id), "action": action,
                     "note": note, "resolution": resolution},
            answer=f"将处理工单 #{ticket_id}（{action}）。请确认。")
        return _result(req, answer, proposal=proposal)

    if intent == "PSYCH_NOTE":
        alert_id = params.get("alert_id")
        if not alert_id:
            items, total = psych_service.list_alerts(db, actor, page=1, page_size=10)
            if total == 0:
                return _result(req, "当前没有待复核的关怀事项。")
            return _result(req, _render_alerts(items, total), missing=["alert_id"])
        alert = psych_service.get_alert(db, actor, int(alert_id))
        note = str(params.get("note") or draft.get("note") or "").strip()
        if not note:
            return _result(req, "请填写跟进说明。", missing=["note"])
        try:
            data = PsychActionRequest(action="NOTE", note=note,
                                      expected_version=alert.version,
                                      request_key=UUID(new_request_key()))
        except Exception:
            return _result(req, "跟进说明格式不正确。", missing=["note"])
        proposal, answer = _proposal(
            actor, "PSYCH_ALERT_NOTE", entity_id=int(alert_id),
            payload=m3_canonical.psych_note_payload(data),
            expected_version=alert.version,
            preview={"alertId": str(alert_id), "note": note},
            answer="将记录一条关怀跟进说明（不改变风险状态）。请确认。")
        return _result(req, answer, proposal=proposal)

    if intent == "APPLICATION_UPDATE":
        case_no = str(params.get("case_no") or draft.get("case_no") or "").strip()
        if not case_no:
            return _result(req, "请提供申请事项编号（case_no）。", missing=["case_no"])
        latest = _latest_case_event(db, case_no)
        if latest is None:
            return _result(req, "未找到该申请事项。", missing=["case_no"])
        event_kind = str(params.get("event_kind") or draft.get("event_kind") or "DETAIL").upper()
        detail = str(params.get("detail") or draft.get("detail") or "").strip()
        if not detail:
            return _result(req, "请填写进度说明。", missing=["detail"])
        stage = params.get("stage") or draft.get("stage")
        try:
            data = ApplicationAdvanceIn(
                expected_sequence=int(params.get("expected_sequence") or latest.sequence_no),
                request_key=UUID(new_request_key()), event_kind=event_kind,
                stage=stage, detail=detail,
                assignee_user_id=params.get("assignee_user_id"),
                occurred_at=_now())
        except Exception:
            return _result(req, "进度参数不正确。", missing=["event_kind", "detail"])
        proposal, answer = _proposal(
            actor, "ADVANCE_APPLICATION", entity_id=None,
            payload=m3_canonical.application_advance_payload(case_no, data),
            expected_version=None,
            preview={"caseNo": case_no, "eventKind": event_kind,
                     "stage": stage, "detail": detail},
            answer=f"将为申请 {case_no} 追加进度：{detail}。请确认。")
        return _result(req, answer, proposal=proposal)

    return _result(req, "暂不支持该操作。", warnings=["INTENT_NOT_HANDLED"])


# =============================================================
# 入口
# =============================================================
def handle_enterprise_message(db: Session, actor: SysUser,
                              req: AssistantRequest) -> AssistantResult:
    if not actor.is_employee:
        raise ForbiddenError("仅员工可使用企业助手")

    # 1) 同名消歧：会话缓存中的候选 + 用户回复编号
    cached = _cache_get((str(actor.id)+":"+req.conversation_id) if req.conversation_id else None)
    text = req.message.strip()
    if cached and re.fullmatch(r"\d{1,2}", text):
        idx = int(text) - 1
        if 0 <= idx < len(cached["ids"]):
            lead_id = cached["ids"][idx]
            try:
                dto = crm_service.get_lead(db, actor, lead_id)
                runtime_state.drop("employee:"+str(actor.id)+":"+str(req.conversation_id))
                return _result(req, _render_lead_detail(dto))
            except NotFoundError:
                return _result(req, "该客户已不在你的可见范围。")

    # 2) 调 Dify（事务外）
    payload = _build_payload(db, actor, req)
    actor_id=actor.id
    db.rollback()
    try:
        raw = run_enterprise_workflow(payload, user=actor_id)
        wf = WfEnterpriseOutput(**raw)
    except (AIUnavailableError, AITimeoutError, AIBadResponseError) as exc:
        logger.info("企业助手 AI 不可用：%s", exc.__class__.__name__)
        return _result(req, "AI 服务暂不可用，请使用表单或工作台操作。",
                       ai_status="UNAVAILABLE", warnings=["AI_UNAVAILABLE"])
    except Exception as exc:  # Schema 校验失败等
        logger.warning("企业助手输出异常：%s", exc.__class__.__name__)
        return _result(req, "AI 返回格式异常，请稍后重试。",
                       ai_status="UNAVAILABLE", warnings=["AI_BAD_RESPONSE"])

    if wf.intent not in ALLOWED_INTENTS:
        return _result(req, "暂不支持该指令，请换一种说法。",
                       warnings=["INTENT_NOT_ALLOWED"])

    try:
        if wf.intent in WRITE_INTENTS:
            return _handle_write(db, actor, req, wf)
        if wf.intent in READ_INTENTS:
            return _handle_read(db, actor, req, wf)
        return _result(req, wf.answer or _KNOWLEDGE_REPLY,
                       sources=wf.sources, warnings=wf.warnings)
    except AppError as exc:
        return _result(req, exc.message, warnings=[exc.code])
