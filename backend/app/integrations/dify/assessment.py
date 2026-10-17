"""
WF_ASSESSMENT 适配器 —— 客户研判字段提取（API041 / API096）

职责：按 dify_mode 选择"离线样本"或"真实调用"，并对输出做一次契约校验。
⚠️ 只做字段提取 + 证据定位 + 缺项；**录取判定与打分由 Python** 按已审核规则执行。
⚠️ 调用必须在事务之外，且不把整张客户表/员工 token 发给 Dify。
"""
from __future__ import annotations

import logging

from app.core.config import settings
from app.core.errors import AIBadResponseError
from app.integrations.dify import mock_samples, run_workflow

logger = logging.getLogger(__name__)


def _validate(data: object) -> dict:
    """按 mode=ASSESSMENT_EXTRACT 校验并归一化；不符合契约抛 502。"""
    if not isinstance(data, dict):
        raise AIBadResponseError("研判工作流输出不是 JSON 对象")

    facts = data.get("facts")
    if not isinstance(facts, dict):
        raise AIBadResponseError("研判工作流未返回 facts 对象")

    evidence = data.get("evidence")
    missing_fields = data.get("missing_fields")

    return {
        "schema_version": str(data.get("schema_version") or "1.0"),
        "mode": "ASSESSMENT_EXTRACT",
        "facts": facts,
        "evidence": [e for e in (evidence or []) if isinstance(e, dict)],
        "missing_fields": [str(x) for x in (missing_fields or [])],
        "warnings": [str(w) for w in (data.get("warnings") or [])],
    }


def run_assessment(payload: dict, *, user: str = "assessment",
                   timeout_s: int | None = None) -> dict:
    """调用研判提取工作流，返回已校验的 ASSESSMENT_EXTRACT 结构。

    payload 只含：lead_id / request_id / confirmed_facts / 可选 resume_text / project_rules。
    """
    if settings.dify_mode == "mock":
        return _validate(mock_samples.assessment_extract(payload))

    timeout = timeout_s or settings.ai_timeout_assessment_seconds
    raw = run_workflow("assessment", payload, user, timeout=float(timeout))
    return _validate(raw)
