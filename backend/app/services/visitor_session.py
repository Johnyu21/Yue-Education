"""Visitor drafts and short history use a high-entropy opaque conversation ID as a short-lived bearer handle."""
import uuid

from app.core import runtime_state
from app.core.config import settings

DRAFT_FIELDS = ('name', 'mobile', 'event_id')

# 送给工作流的最近对话条数（约 4 轮），以及单条内容上限
HISTORY_LIMIT = 8
MESSAGE_MAX_CHARS = 1000


def new_conversation_id(): return str(uuid.uuid4())


def _key(cid):
    try:
        return 'visitor:' + str(uuid.UUID(str(cid)))
    except (ValueError, TypeError, AttributeError):
        return None


def _history_key(cid):
    try:
        return 'visitor:history:' + str(uuid.UUID(str(cid)))
    except (ValueError, TypeError, AttributeError):
        return None


def _ttl_seconds():
    return max(1, settings.visitor_session_ttl_minutes) * 60


def get(conversation_id):
    key = _key(conversation_id)
    return (runtime_state.get(key) or {}) if key else {}


def merge(conversation_id, patch):
    key = _key(conversation_id)
    if not key:
        return {}
    clean = {k: v for k, v in (patch or {}).items() if k in DRAFT_FIELDS and v not in (None, '')}
    return runtime_state.put(key, clean, _ttl_seconds(), merge=True)


def drop(conversation_id):
    for key in (_key(conversation_id), _history_key(conversation_id)):
        if key:
            runtime_state.drop(key)


def get_history(conversation_id):
    """最近对话（与草稿分开存放）。

    ⚠️ 只存访客自己的消息与客服回答，均为公开内容，不含客户库或员工信息。
    """
    key = _history_key(conversation_id)
    if not key:
        return []
    items = runtime_state.get(key)
    if not isinstance(items, list):
        return []
    return [m for m in items if isinstance(m, dict) and m.get('content')][-HISTORY_LIMIT:]


def append_history(conversation_id, user_message, answer):
    """记录一轮问答；只保留最近 HISTORY_LIMIT 条，TTL 与会话草稿一致。"""
    key = _history_key(conversation_id)
    if not key:
        return []
    items = get_history(conversation_id)
    text = str(user_message or '').strip()
    if text:
        items.append({'role': 'user', 'content': text[:MESSAGE_MAX_CHARS]})
    reply = str(answer or '').strip()
    if reply:
        items.append({'role': 'assistant', 'content': reply[:MESSAGE_MAX_CHARS]})
    items = items[-HISTORY_LIMIT:]
    runtime_state.put(key, items, _ttl_seconds())
    return items
