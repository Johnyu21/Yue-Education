"""Visitor drafts use a high-entropy opaque conversation ID as a short-lived bearer handle."""
import uuid
from app.services import m2_config
from app.core import runtime_state
DRAFT_FIELDS=('name','mobile','event_id')

def new_conversation_id():return str(uuid.uuid4())
def _key(cid):
    try:return 'visitor:'+str(uuid.UUID(str(cid)))
    except (ValueError,TypeError,AttributeError):return None
def get(conversation_id):
    key=_key(conversation_id)
    return runtime_state.get(key) or {} if key else {}
def merge(conversation_id,patch):
    key=_key(conversation_id)
    if not key:return {}
    clean={k:v for k,v in (patch or {}).items() if k in DRAFT_FIELDS and v not in (None,'')}
    return runtime_state.put(key,clean,max(1,m2_config.visitor_session_ttl_minutes())*60,merge=True)
def drop(conversation_id):
    key=_key(conversation_id)
    if key:runtime_state.drop(key)
