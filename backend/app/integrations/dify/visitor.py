"""
WF_VISITOR 适配器 —— 访客客服（API027）

职责：按 dify_mode 选择"离线样本"或"真实调用"，并对输出做一次契约校验。
⚠️ 本模块只负责"拿到结构化输出"；限流、会话草稿、提议卡片拼装在 service 层。
⚠️ 调用必须在事务之外。
"""
from __future__ import annotations

import logging

from app.core.config import settings
from app.core.errors import AIBadResponseError
from app.integrations.dify import mock_samples, run_workflow

logger = logging.getLogger(__name__)

ALLOWED_INTENTS = {"FAQ", "LEAD_DRAFT", "ACTIVITY_DRAFT", "OUT_OF_SCOPE"}


def _validate(data: object) -> dict:
    """按 mode=VISITOR_ANSWER 校验并归一化；不符合契约抛 502。"""
    if not isinstance(data, dict):
        raise AIBadResponseError("访客工作流输出不是 JSON 对象")

    answer = data.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        raise AIBadResponseError("访客工作流未返回有效 answer")

    intent = data.get("intent")
    if intent not in ALLOWED_INTENTS:
        # 未知意图一律降级为公开问答，绝不执行任何写操作
        if intent is not None:
            logger.warning("未知访客意图 %s，按 FAQ 处理", intent)
        intent = "FAQ"

    draft = data.get("draft")
    sources = data.get("sources")

    return {
        "schema_version": str(data.get("schema_version") or "1.0"),
        "mode": "VISITOR_ANSWER",
        "intent": intent,
        "answer": answer.strip(),
        "draft": draft if isinstance(draft, dict) else None,
        "missing_fields": [str(x) for x in (data.get("missing_fields") or [])],
        "sources": [s for s in (sources or []) if isinstance(s, dict)],
        "warnings": [str(w) for w in (data.get("warnings") or [])],
    }


def run_visitor(payload: dict, *, user: str = "visitor",
                timeout_s: int | None = None) -> dict:
    """调用访客问答工作流，返回已校验的 VISITOR_ANSWER 结构。

    失败语义：Dify 不可用抛 AIUnavailableError、超时抛 AITimeoutError、
    输出不合契约抛 AIBadResponseError —— 由 service 层统一降级。
    """
    if settings.dify_mode == "mock":
        return _validate(mock_samples.visitor_answer(payload))

    timeout = timeout_s or settings.ai_timeout_visitor_seconds
    raw = run_workflow("visitor", payload, user, timeout=float(timeout))
    return _validate(raw)
