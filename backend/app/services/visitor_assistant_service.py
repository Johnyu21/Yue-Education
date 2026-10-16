"""
访客客服助手（API027）—— M2

职责：
  1. 公开限流 + 会话草稿（进程内 TTL，见 visitor_session）
  2. 组装**只含公开信息**的 payload（已发布项目、开放活动），调用 WF_VISITOR
  3. AI 只输出"草稿 + 意图"，**绝不直接写库**；写操作由访客在页面确认后
     调用普通业务接口（POST /public/leads、POST /events/{id}/registrations）
  4. AI 不可用 → 降级回答（aiStatus=UNAVAILABLE），不影响表单与查询

⚠️ 关于"确认凭据"：M1 的 confirmation 令牌绑定登录 actor，访客无账号不适用；
   因此访客侧用**服务端签发的 requestKey + confirmed=true** 作为"用户已确认"的凭据，
   且公开留资/报名本身没有可越权的权限，不存在提权风险（已在文档中说明）。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AIBadResponseError, AITimeoutError, AIUnavailableError
from app.integrations.dify.visitor import run_visitor
from app.models.event import EventLecture
from app.schemas.assistant import AssistantRequest, AssistantResult, Proposal, SourceItem
from app.services import m2_config, rate_limit, visitor_session

logger = logging.getLogger(__name__)

# 意图 → 提议操作
_OPERATIONS = {"LEAD_DRAFT": "CAPTURE_LEAD", "ACTIVITY_DRAFT": "REGISTER_EVENT"}

# 提供给访客的公开信息条数上限
_MAX_PUBLIC_PROJECTS = 5
_MAX_PUBLIC_EVENTS = 5

# 提议有效期（分钟）——与 M1 确认令牌保持一致的 5 分钟口径
_PROPOSAL_TTL_MINUTES = 5

_DRAFT_INTENTS = tuple(_OPERATIONS.keys())


def _public_projects(db: Session) -> list[dict]:
    """只取已发布项目的公开字段（不含未审规则、路由部门、费用明细以外的内部信息）。"""
    from app.models.course_project import CourseProject

    rows = db.scalars(
        select(CourseProject)
        .where(CourseProject.is_published.is_(True))
        .order_by(CourseProject.id.asc())
        .limit(_MAX_PUBLIC_PROJECTS)
    ).all()
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "country": p.country,
            "education_level": p.education_level,
        }
        for p in rows
    ]


def _open_events(db: Session) -> list[dict]:
    """只取开放活动；名额以报名接口实时结果为准，不在此处承诺。"""
    rows = db.scalars(
        select(EventLecture)
        .where(EventLecture.status == "OPEN")
        .order_by(EventLecture.start_at.asc(), EventLecture.id.asc())
        .limit(_MAX_PUBLIC_EVENTS)
    ).all()
    return [
        {
            "id": str(e.id),
            "title": e.title,
            "start_at": e.start_at.isoformat() if e.start_at else None,
        }
        for e in rows
    ]


def _build_payload(db: Session, req: AssistantRequest, conversation_id: str) -> dict:
    """⚠️ 只放公开信息 + 访客自己的消息；不含任何客户库明细。"""
    return {
        "schema_version": "1.0",
        "message": req.message,
        "message_id": str(req.message_id),
        "conversation_id": conversation_id,
        "public_projects": _public_projects(db),
        "open_events": _open_events(db),
        "context": req.context.model_dump() if req.context else None,
    }


def _degraded(req: AssistantRequest, conversation_id: str, answer: str,
              warning: str) -> AssistantResult:
    return AssistantResult(
        conversationId=conversation_id,
        messageId=str(req.message_id),
        answer=answer,
        aiStatus="UNAVAILABLE",
        warnings=[warning],
    )


def _build_proposal(intent: str, merged: dict, missing: list[str]) -> Proposal | None:
    """生成"提议卡片"：只含预览与 requestKey，真正落库仍由访客调普通接口触发。

    ⚠️ 提议不是授权，也不是已提交；前端必须把它当"待确认草稿"渲染。
    """
    operation = _OPERATIONS.get(intent)
    if operation is None or not merged:
        return None

    expires = datetime.now(timezone.utc) + timedelta(minutes=_PROPOSAL_TTL_MINUTES)
    preview = dict(merged)
    preview["missing_fields"] = list(missing)
    return Proposal(
        operation=operation,
        entityId=None,
        preview=preview,
        expectedVersion=None,
        requestKey=visitor_session.new_conversation_id(),   # 服务端签发的幂等键
        confirmationToken=None,                             # 访客无 actor，见模块 docstring
        expiresAt=expires,
    )


def handle_visitor_message(db: Session, req: AssistantRequest, *,
                           client_key: str) -> AssistantResult:
    rate_limit.check(client_key)

    conversation_id = req.conversation_id or visitor_session.new_conversation_id()
    session_draft = visitor_session.get(conversation_id)

    payload = _build_payload(db, req, conversation_id)

    try:
        raw = run_visitor(payload, user=conversation_id,
                          timeout_s=m2_config.ai_timeout_visitor_seconds())
    except (AIUnavailableError, AITimeoutError) as exc:
        logger.info("访客客服 AI 不可用：%s", exc.__class__.__name__)
        return _degraded(req, conversation_id,
                         "AI 服务暂不可用，您可以稍后重试，或直接填写表单留下联系方式。",
                         "AI 服务暂不可用")
    except AIBadResponseError:
        logger.warning("访客客服 AI 返回异常")
        return _degraded(req, conversation_id,
                         "AI 返回异常，请稍后重试，或直接填写表单留下联系方式。",
                         "AI 返回异常")

    intent = raw["intent"]

    # 合并"会话里已有的草稿"与"本轮识别出的草稿"，避免多轮对话丢字段
    merged = dict(session_draft)
    if isinstance(raw.get("draft"), dict):
        merged = visitor_session.merge(
            conversation_id,
            {k: v for k, v in raw["draft"].items() if k != "event_id"},
        )
        if raw["draft"].get("event_id"):
            merged = visitor_session.merge(conversation_id,
                                           {"event_id": raw["draft"]["event_id"]})

    missing = [f for f in ("name", "mobile") if not merged.get(f)] \
        if intent in _DRAFT_INTENTS else list(raw.get("missing_fields") or [])

    sources = [
        SourceItem(documentId=s.get("document_id"), title=s.get("title"),
                   section=s.get("section"))
        for s in raw.get("sources", [])
        if isinstance(s, dict)
    ]

    proposal = _build_proposal(intent, merged, missing) if intent in _DRAFT_INTENTS else None

    # 提示词要求导出客户库等越界请求：明确拒绝，且不带任何草稿
    if intent == "OUT_OF_SCOPE":
        proposal = None
        missing = []

    logger.info("M2 访客客服 intent=%s 会话=%s", intent, conversation_id)
    return AssistantResult(
        conversationId=conversation_id,
        messageId=str(req.message_id),
        answer=raw["answer"],
        sources=sources,
        missingFields=missing,
        proposal=proposal,
        aiStatus="LIVE",
        warnings=list(raw.get("warnings") or []),
    )
