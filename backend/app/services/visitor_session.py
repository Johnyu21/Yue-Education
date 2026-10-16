"""
访客会话草稿（进程内 TTL 缓存）—— M2

⚠️ 设计取舍（对齐 02 文档"聊天保存在短期会话缓存、不增加聊天表"）：
  - 本项目固定 19 表，没有聊天/草稿表，因此草稿只放在**进程内存**里；
  - **仅适用于单实例开发/演示**，多实例或重启会丢草稿（属预期，不是 bug）；
  - 草稿里**只允许**放"待提交的最少字段"（姓名/手机号/活动 id），
    绝不缓存客户库明细、他人数据或员工信息。
  - 缺姓名/手机号的对话**不落正式客户**（落库只发生在访客确认调用普通接口时）。
"""
from __future__ import annotations

import threading
import time
import uuid

from app.services import m2_config

# conversation_id -> (draft dict, expire_ts)
_sessions: dict[str, tuple[dict, float]] = {}
_lock = threading.Lock()
_PRUNE_AT = 512

# 草稿允许保留的字段白名单
DRAFT_FIELDS = ("name", "mobile", "event_id")


def new_conversation_id() -> str:
    return str(uuid.uuid4())


def _ttl_seconds() -> float:
    return max(m2_config.visitor_session_ttl_minutes(), 1) * 60.0


def _prune(now: float) -> None:
    for key, (_, exp) in list(_sessions.items()):
        if exp < now:
            _sessions.pop(key, None)


def get(conversation_id: str | None) -> dict:
    """取会话草稿（只返回白名单字段）。"""
    if not conversation_id:
        return {}
    now = time.monotonic()
    with _lock:
        item = _sessions.get(conversation_id)
        if item is None:
            return {}
        draft, exp = item
        if exp < now:
            _sessions.pop(conversation_id, None)
            return {}
        return dict(draft)


def merge(conversation_id: str, patch: dict) -> dict:
    """把新拿到的草稿字段并入会话（只收白名单字段；空值不覆盖已有值）。"""
    clean = {k: v for k, v in (patch or {}).items()
             if k in DRAFT_FIELDS and v not in (None, "")}

    now = time.monotonic()
    with _lock:
        if len(_sessions) > _PRUNE_AT:
            _prune(now)

        current, _ = _sessions.get(conversation_id, ({}, 0.0))
        merged = dict(current)
        merged.update(clean)
        _sessions[conversation_id] = (merged, now + _ttl_seconds())
        return dict(merged)


def drop(conversation_id: str) -> None:
    """确认提交成功后清掉草稿（避免重复提交同一份草稿）。"""
    with _lock:
        _sessions.pop(conversation_id, None)
