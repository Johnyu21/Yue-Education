"""
学生智能助手（API030）消息编排

意图分类/查询/草稿由 WF_STUDENT（Dify）完成；后端负责：
  - 情绪观测（直接词先行 + Dify 情绪落库，事务外调用）
  - 写操作生成提议卡片 + 确认令牌（不直接写库）
  - 返回前删除内部 observation（不向学生回显情绪/风险）
"""
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.confirmation import CONFIRM_TTL_MINUTES, new_request_key, sign_confirmation
from app.core.errors import AIBadResponseError, AITimeoutError, AIUnavailableError, NotFoundError
from app.core.transaction import with_business_transaction
from app.integrations.dify import call_student_workflow
from app.models.organization import SysClass
from app.models.student import StudentProfile
from app.models.user import SysUser
from app.repositories import student_repo
from app.schemas.assistant import AssistantRequest, AssistantResult, Proposal, SourceItem, WfStudentOutput
from app.schemas.feedback import FeedbackCreateRequest
from app.schemas.service import ServiceCreateRequest
from app.services import psych_service
from app.services.feedback_service import canonical_feedback_payload
from app.services.student_service import canonical_service_payload

logger = logging.getLogger(__name__)

_OPERATIONS = {"SERVICE_DRAFT": "SUBMIT_SERVICE", "FEEDBACK_DRAFT": "SUBMIT_FEEDBACK",
               "UPGRADE_INTEREST": "UPGRADE_INTEREST"}


def _build_payload(db: Session, profile: StudentProfile, user: SysUser,
                   req: AssistantRequest, consent_granted: bool) -> dict:
    enrollments = student_repo.list_enrollments(db, profile.id)
    names = student_repo.get_project_names(db, [e.course_project_id for e in enrollments])
    cls = db.get(SysClass, profile.class_id) if profile.class_id else None
    advisor = db.get(SysUser, profile.advisor_user_id) if profile.advisor_user_id else None

    return {
        "schema_version": "1.0",
        "message": req.message,
        "message_id": str(req.message_id),
        "conversation_id": req.conversation_id,
        "input_kind": req.input_kind,
        "observe_emotion": consent_granted,
        "student": {
            "id": str(profile.id),
            "real_name": user.real_name,
            "class_name": cls.name if cls else None,
            "advisor_name": advisor.real_name if advisor else None,
            "projects": [names.get(e.course_project_id, "") for e in enrollments],
        },
        "context": req.context.model_dump() if req.context else None,
    }


def _service_request_from_draft(draft: dict, request_key: str) -> ServiceCreateRequest:
    return ServiceCreateRequest(
        request_key=UUID(request_key),
        service_type=draft.get("service_type", "OTHER"),
        title=draft.get("title") or "申请",
        description=draft.get("description") or "",
        start_at=draft.get("start_at"),
        end_at=draft.get("end_at"),
        change_request=draft.get("change_request"),
        confirmed=True,
    )


def _feedback_request_from_draft(draft: dict, request_key: str) -> FeedbackCreateRequest:
    return FeedbackCreateRequest(
        request_key=UUID(request_key),
        category=draft.get("category", "CONSULTATION"),
        subject=draft.get("subject") or "咨询",
        teacher_name=draft.get("teacher_name") or "未知",
        project_category=draft.get("project_category") or "其他",
        course_project_id=draft.get("course_project_id"),
        content=draft.get("content") or "",
        confirmed=True,
    )


def _build_proposal(user: SysUser, wf: WfStudentOutput) -> Proposal | None:
    """写意图生成提议卡片 + 确认令牌。"""
    if not wf.draft or wf.intent not in _OPERATIONS:
        return None

    operation = _OPERATIONS[wf.intent]
    rk = new_request_key()
    expires = datetime.now(timezone.utc) + timedelta(minutes=CONFIRM_TTL_MINUTES)

    if operation == "SUBMIT_SERVICE":
        payload = canonical_service_payload(_service_request_from_draft(wf.draft, rk))
    elif operation == "SUBMIT_FEEDBACK":
        payload = canonical_feedback_payload(_feedback_request_from_draft(wf.draft, rk))
    else:  # UPGRADE_INTEREST
        payload = {"course_project_id": wf.draft.get("course_project_id")}

    token = sign_confirmation(user, operation, entity_id=None, payload=payload,
                              expected_version=None, request_key=rk)
    return Proposal(
        operation=operation, entityId=None, preview=wf.draft, expectedVersion=None,
        requestKey=rk, confirmationToken=token, expiresAt=expires,
    )


def handle_student_message(db: Session, user: SysUser, req: AssistantRequest) -> AssistantResult:
    profile = student_repo.get_profile_by_user(db, user.id)
    if profile is None:
        raise NotFoundError("学生档案不存在")

    consent_granted = profile.psych_consent_status == "GRANTED"
    received_at = datetime.now(timezone.utc)

    # 1) 直接风险词先行（不等待 Dify）
    if consent_granted:
        matched = psych_service.detect_direct_word(req.message)
        if matched:
            with with_business_transaction(db):
                psych_service.record_direct_risk(
                    db, profile, source_event_key=psych_service._sub_key(str(req.message_id), "direct"),
                    received_at=received_at, matched_word=matched)

    # 2) 调用 Dify（事务外）
    payload = _build_payload(db, profile, user, req, consent_granted)
    try:
        raw = call_student_workflow(payload, user.id)
        wf = WfStudentOutput(**raw)
    except (AIUnavailableError, AITimeoutError) as exc:
        logger.info("学生助手 AI 不可用：%s", exc.__class__.__name__)
        return AssistantResult(conversationId=req.conversation_id, messageId=str(req.message_id),
                               answer="AI 服务暂不可用，请稍后重试，或改用表单办理。",
                               aiStatus="UNAVAILABLE", warnings=["AI 服务暂不可用"])
    except (AIBadResponseError, ValidationError):
        return AssistantResult(conversationId=req.conversation_id, messageId=str(req.message_id),
                               answer="AI 返回异常，请稍后重试。", aiStatus="UNAVAILABLE",
                               warnings=["AI 返回异常"])

    # 3) 落 Dify 情绪观测（仅在授权且返回有效观测时）
    if (consent_granted and wf.observation is not None
            and wf.observation.emotion_state != "UNKNOWN"):
        with with_business_transaction(db):
            psych_service.record_dify_observation(
                db, profile, source_event_key=psych_service._sub_key(str(req.message_id), "emotion"),
                received_at=received_at, emotion_state=wf.observation.emotion_state,
                confidence=wf.observation.confidence)

    # 4) 提议卡片
    proposal = _build_proposal(user, wf)

    sources = [SourceItem(**s) for s in wf.sources if isinstance(s, dict)]
    return AssistantResult(
        conversationId=req.conversation_id, messageId=str(req.message_id),
        answer=wf.answer or "请描述您的问题。", sources=sources,
        missingFields=wf.missing_fields, proposal=proposal, aiStatus="LIVE",
        warnings=wf.warnings,
    )
