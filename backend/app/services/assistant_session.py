"""Actor-scoped assistant drafts, bounded history and proposal revisions (15 min).

Business query results, confirmation tokens and psychological notes are not kept
in chat history. runtime_state is shared by workers and is not a business write.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt

from app.core import runtime_state
from app.core.config import settings
from app.core.errors import InvalidRequestError

TTL = 900
CANCEL = {"取消", "取消操作", "取消本次", "取消草稿", "清空草稿", "重新开始"}


def begin(audience, actor_id, req):
    if not req.conversation_id:
        req.conversation_id = str(uuid4())
    key = f"assistant:{audience}:{actor_id}:{req.conversation_id}"
    state = runtime_state.get(key) or {}
    if req.message.strip() in CANCEL:
        state = {}
    state["revision"] = str(uuid4())
    runtime_state.put(key, state, TTL)
    return key, state


def context(state):
    return {"pending": state.get("pending"), "history": state.get("history", []),
            "candidates": [{"kind": "lead", "id": str(state["selected_lead_id"])}] if state.get("selected_lead_id") else [],
            "business_now": datetime.now(timezone(timedelta(hours=8))).isoformat(),
            "business_timezone": "Asia/Shanghai"}


def finish(key, state, req, wf, result):
    current = runtime_state.get(key)
    if not current or current.get("revision") != state["revision"]:
        raise InvalidRequestError("会话已更新，请以最新消息为准")
    # All model output is revalidated before it reaches this function.
    intent = wf.get("intent") if wf else None
    writes = {"LEAD_CREATE", "FOLLOWUP_ADD", "LEAD_CHANGE_STATUS", "DAILY_DRAFT", "LEAVE_DECIDE",
              "FEEDBACK_HANDLE", "PSYCH_NOTE", "APPLICATION_UPDATE", "SERVICE_DRAFT", "FEEDBACK_DRAFT", "UPGRADE_INTEREST"}
    retain = wf and (result.missingFields or result.proposal or intent in writes)
    if retain:
        state["pending"] = {k: wf[k] for k in ("schema_version", "intent", "params", "draft") if k in wf}
    elif result.aiStatus != "UNAVAILABLE":
        state.pop("pending", None)
    if intent not in {"PSYCH_NOTE", "PSYCH_LIST"} and retain:
        history = state.get("history", [])
        history += [{"role": "user", "content": req.message[:8000]},
                    {"role": "assistant", "content": "请补充：" + "、".join(result.missingFields) if result.missingFields else "请核对待确认草稿。"}]
        state["history"] = history[-8:]
    else:
        state["history"] = []
    if not runtime_state.compare_put(key, state, state["revision"], TTL):
        raise InvalidRequestError("会话已更新，请以最新消息为准")
    if result.proposal and result.proposal.confirmationToken:
        claims = jwt.decode(result.proposal.confirmationToken, settings.jwt_secret,
                            algorithms=[settings.jwt_algorithm], issuer="confirm")
        claims.update(draft_key=key, draft_revision=state["revision"])
        result.proposal.confirmationToken = jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return result
