"""
WF_ENTERPRISE 适配器 —— 企业智能助手（API029）

职责：按 dify_mode 选择离线样本或真实调用，并对输出做一次契约校验。
⚠️ 只负责“拿到结构化意图”；权限、查询、提议、确认都在 service 层。
⚠️ 调用必须在事务之外。
"""
import logging

from app.core.config import settings
from app.core.errors import AIBadResponseError
from app.integrations.dify import mock_samples, run_workflow
from app.schemas.assistant_enterprise import ALLOWED_INTENTS

logger = logging.getLogger(__name__)

_ACTIONS = {"query", "create", "update", "delete", "decide", "note", "execute"}


def _validate(data: object) -> dict:
    if not isinstance(data, dict):
        raise AIBadResponseError("企业工作流输出不是 JSON 对象")

    intent = str(data.get("intent") or "OTHER").strip().upper()
    if intent not in ALLOWED_INTENTS:
        logger.warning("未知企业意图 %s，按 OTHER 处理", intent)
        intent = "OTHER"

    action = data.get("action")
    if action is not None and str(action).lower() not in _ACTIONS:
        action = None

    params = data.get("params")
    draft = data.get("draft")
    return {
        "schema_version": str(data.get("schema_version") or "1.0"),
        "intent": intent,
        "action": str(action).lower() if action else None,
        "params": params if isinstance(params, dict) else {},
        "draft": draft if isinstance(draft, dict) else None,
        "missing_fields": [str(x) for x in (data.get("missing_fields") or [])],
        "answer": str(data.get("answer") or ""),
        "sources": [s for s in (data.get("sources") or []) if isinstance(s, dict)],
        "warnings": [str(w) for w in (data.get("warnings") or [])],
    }


def run_enterprise(payload: dict, *, user: str = "employee",
                   timeout_s: int | None = None) -> dict:
    """调用企业助手工作流，返回已校验的意图结构。"""
    if settings.dify_mode == "mock":
        return _validate(mock_samples.enterprise_output(payload))

    timeout = timeout_s or 30
    raw = run_workflow("enterprise", payload, str(user), timeout=float(timeout))
    return _validate(raw)
