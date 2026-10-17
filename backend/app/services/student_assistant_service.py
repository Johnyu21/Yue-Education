"""
学生智能助手（API030）消息编排

意图分类 / 查询 / 写操作由 WF_STUDENT（Dify 工作流）完成：
  - Dify 工作流内用 HTTP 节点直接调用后端业务接口（查询 GET / 写操作 POST）
  - 学生 JWT 通过 payload 传给 Dify，供 HTTP 节点鉴权
后端负责：
  - 情绪观测（直接词先行 + Dify 情绪落库，事务外调用）
  - 返回前删除内部 observation（不向学生回显情绪/风险）
"""
import logging
from datetime import datetime, timezone

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.errors import AIBadResponseError, AITimeoutError, AIUnavailableError, NotFoundError
from app.core.transaction import with_business_transaction
from app.integrations.dify import call_student_workflow
from app.models.user import SysUser
from app.repositories import student_repo
from app.schemas.assistant import AssistantRequest, AssistantResult, SourceItem, WfStudentOutput
from app.services import psych_service

logger = logging.getLogger(__name__)


def _build_payload(req: AssistantRequest, auth_token: str, consent_granted: bool) -> dict:
    """组装 Dify 输入：携带学生 JWT，供工作流内 HTTP 节点鉴权调后端接口。"""
    return {
        "schema_version": "1.0",
        "auth_token": auth_token,
        "student_user_id": "",            # JWT 已识别学生，此字段仅占位，Dify 不依赖
        "message": req.message,
        "message_id": str(req.message_id),
        "conversation_id": req.conversation_id,
        "input_kind": req.input_kind,
        "observe_emotion": consent_granted,
        "context": req.context.model_dump() if req.context else None,
    }


def handle_student_message(db: Session, user: SysUser, req: AssistantRequest,
                           auth_token: str) -> AssistantResult:
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
    payload = _build_payload(req, auth_token, consent_granted)
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

    sources = [SourceItem(**s) for s in wf.sources if isinstance(s, dict)]
    return AssistantResult(
        conversationId=req.conversation_id, messageId=str(req.message_id),
        answer=wf.answer or "请描述您的问题。", sources=sources,
        missingFields=wf.missing_fields, proposal=None, aiStatus="LIVE",
        warnings=wf.warnings,
    )
