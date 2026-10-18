"""Pure stdlib contracts shared by the backend and generated Dify Code nodes.

This module deliberately has no database, HTTP, credential or project imports.
Missing business fields are a clarification, malformed output is an error.
"""
import json
import re
from datetime import datetime


def object_json(raw):
    if not isinstance(raw, str) or not raw.strip() or len(raw) > 180000:
        raise ValueError("Invalid JSON text")
    raw = re.sub(r"^<think>[\s\S]*?</think>\s*", "", raw.strip(), count=1)
    raw = re.sub(r"^(```|~~~)(?:json)?\s*([\s\S]*?)\s*\1$", r"\2", raw).strip()
    value = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite JSON")))
    if not isinstance(value, dict):
        raise ValueError("Expected JSON object")
    return value


def dump(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def string(value, limit=8000):
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError("Invalid string")
    return value.strip()


def strings(value):
    if not isinstance(value, list) or len(value) > 100:
        raise ValueError("Expected string array")
    return list(dict.fromkeys(string(v, 2000) for v in value))


def pick(value, fields):
    if value is None:
        return {}
    if not isinstance(value, dict) or set(value) - set(fields):
        raise ValueError("Unsupported business fields")
    result = {}
    for key, item in value.items():
        if item is not None and key in {"filters", "change_request", "old_values", "new_values"}:
            if not isinstance(item, dict):
                raise ValueError("Expected object field: " + key)
        elif item is not None and key not in {"confidence", "direct_signal"} and not key.endswith("_id") and not isinstance(item, str):
            raise ValueError("Expected text field: " + key)
        if key.endswith("_id") and item is not None:
            if isinstance(item, bool) or not re.fullmatch(r"[1-9]\d{0,18}", str(item)):
                raise ValueError("Invalid object ID")
        if isinstance(item, str):
            item = string(item)
        elif item is not None and type(item) not in (int, float, bool, dict, list):
            raise ValueError("Invalid field type")
        result[key] = item
    return result


def absent(value):
    return value is None or value == "" or value == {} or value == []


def merge_pending(value, payload):
    value = dict(value)
    old = (payload or {}).get("pending") or {}
    if not isinstance(old, dict) or old.get("intent") != value.get("intent"):
        return value
    fresh = value.get("params") or {}
    previous = old.get("params") or {}
    # A new target starts a new operation, rather than borrowing another person's draft.
    targets = {"lead_id", "keyword", "ticket_id", "service_id", "alert_id", "case_no", "student_name"}
    if any(not absent(fresh.get(k)) and str(fresh[k]) != str(previous.get(k, "")) for k in targets):
        return value
    fresh_draft, old_draft = value.get("draft") or {}, old.get("draft") or {}
    if any(not absent(fresh_draft.get(k)) and not absent(old_draft.get(k)) and str(fresh_draft[k]) != str(old_draft[k])
           for k in ("service_type", "course_project_id")):
        return value
    for field in ("params", "draft"):
        if field not in value and field not in old:
            continue
        current = value.get(field) or {}
        prior = old.get(field) or {}
        if not isinstance(current, dict) or not isinstance(prior, dict):
            raise ValueError("Invalid pending fields")
        value[field] = {**prior, **{k: v for k, v in current.items() if not absent(v) or k == "next_follow_up_at"}}
        if field == "draft" and isinstance(prior.get("change_request"), dict) and isinstance(current.get("change_request"), dict):
            change = {**prior["change_request"], **current["change_request"]}
            for side in ("old_values", "new_values"):
                a, b = prior["change_request"].get(side), current["change_request"].get(side)
                if isinstance(a, dict) and isinstance(b, dict):
                    change[side] = {**a, **b}
            value[field]["change_request"] = change
    return value


def require(fields, data):
    return [key for key in fields if absent(data.get(key))]


def enum(data, key, values):
    if not absent(data.get(key)) and data[key] not in values:
        raise ValueError("Invalid " + key)


def envelope(value, intents, enterprise=False):
    fields = {"schema_version", "intent", "answer", "draft", "missing_fields", "warnings", "sources"}
    fields |= {"params", "action"} if enterprise else {"observation"}
    if not isinstance(value, dict) or set(value) - fields or value.get("schema_version") != "1.0":
        raise ValueError("Invalid output schema")
    if value.get("intent") not in intents:
        raise ValueError("Unsupported intent")
    out = {"schema_version": "1.0", "intent": value["intent"],
           "answer": string(value.get("answer", "")), "draft": None,
           "missing_fields": [], "sources": [], "warnings": strings(value.get("warnings", []))}
    # Missing fields and citations are recomputed, never trusted from the model.
    return out


READ_FIELDS = {
    "LEAD_SEARCH": "keyword status view", "LEAD_DETAIL": "lead_id keyword status view",
    "FOLLOWUP_LIST": "lead_id keyword", "TODO_LIST": "", "SERVICE_LIST": "status",
    "FEEDBACK_LIST": "status assignee", "PSYCH_LIST": "status severity",
    "APPLICATION_SEARCH": "student_name", "ORG_SEARCH": "keyword", "DAILY_SEARCH": "",
    "METRIC_QUERY": "metric time_range filters group_by",
}
WRITE_FIELDS = {
    "LEAD_CREATE": ("", "name mobile gender city education intended_project_id study_purpose interest_level content"),
    "FOLLOWUP_ADD": ("lead_id keyword next_follow_up_at", "content"),
    "LEAD_CHANGE_STATUS": ("lead_id keyword target_status reason", ""),
    "DAILY_DRAFT": ("", "original_text"),
    "LEAVE_DECIDE": ("service_id decision note", ""),
    "FEEDBACK_HANDLE": ("ticket_id action note resolution assignee_user_id", ""),
    "PSYCH_NOTE": ("alert_id note", ""),
    "APPLICATION_UPDATE": ("case_no event_kind stage detail assignee_user_id", ""),
}
METRIC_GROUPS = {
    "LEAD_COUNT": {"STATUS", "OWNER", "DEPT"}, "SIGNED_COUNT": {"OWNER", "DEPT"},
    "FOLLOWUP_COUNT": {"OWNER"}, "FOLLOWUP_DUE_COUNT": set(),
    "SERVICE_PENDING_COUNT": {"TYPE", "DEPT"}, "FEEDBACK_OPEN_COUNT": {"STATUS", "PRIORITY", "DEPT"},
    "APPLICATION_STAGE_COUNT": {"STAGE", "ITEM_TYPE"}, "PSYCH_ALERT_COUNT": {"SEVERITY"},
}
METRIC_FILTERS = {"LEAD_COUNT": {"status"}, "SERVICE_PENDING_COUNT": {"service_type"},
                  "FEEDBACK_OPEN_COUNT": {"category"}, "APPLICATION_STAGE_COUNT": {"item_type"},
                  "PSYCH_ALERT_COUNT": {"severity"}}


def validate_enterprise(value, payload=None):
    value = merge_pending(value, payload)
    out = envelope(value, set(READ_FIELDS) | set(WRITE_FIELDS) | {"KNOWLEDGE", "OTHER"}, True)
    intent = out["intent"]
    pfields, dfields = WRITE_FIELDS.get(intent, (READ_FIELDS.get(intent, ""), ""))
    params = pick(value.get("params", {}), pfields.split())
    draft = pick(value.get("draft"), dfields.split())
    missing = []
    if intent == "LEAD_CREATE":
        missing = require(["name", "mobile"], draft)
        if draft.get("mobile") and not re.fullmatch(r"1[3-9]\d{9}", str(draft["mobile"])):
            missing.append("mobile")
    if intent in {"FOLLOWUP_ADD", "FOLLOWUP_LIST", "LEAD_CHANGE_STATUS", "LEAD_DETAIL"}:
        if not params.get("lead_id") and not params.get("keyword"):
            missing.append("lead_id")
    if intent == "FOLLOWUP_ADD":
        missing += require(["content"], draft)
        if params.get("next_follow_up_at"):
            aware_datetime(params["next_follow_up_at"])
    if intent == "LEAD_CHANGE_STATUS":
        enum(params, "target_status", {"FOLLOWING", "LOST"})
        missing += require(["target_status", "reason"], params)
    if intent == "LEAVE_DECIDE":
        enum(params, "decision", {"APPROVE", "REJECT"})
        missing += require(["service_id", "decision", "note"], params)
    if intent == "FEEDBACK_HANDLE":
        enum(params, "action", {"NOTE", "RESOLVE", "ASSIGN"})
        missing += require(["ticket_id", "action", "note"], params)
        if params.get("action") == "RESOLVE":
            missing += require(["resolution"], params)
        if params.get("action") == "ASSIGN":
            missing += require(["assignee_user_id"], params)
    if intent == "PSYCH_NOTE":
        missing += require(["alert_id", "note"], params)
    if intent == "APPLICATION_UPDATE":
        enum(params, "event_kind", {"STAGE", "DETAIL", "ASSIGNMENT"})
        enum(params, "stage", {"PROCESSING", "COMPLETED"})
        missing += require(["case_no", "event_kind", "detail"], params)
        if params.get("event_kind") == "STAGE":
            missing += require(["stage"], params)
        if params.get("event_kind") == "ASSIGNMENT":
            missing += require(["assignee_user_id"], params)
    if intent == "APPLICATION_SEARCH":
        missing += require(["student_name"], params)
    if intent == "DAILY_DRAFT":
        missing += require(["original_text"], draft)
    if intent == "METRIC_QUERY":
        enum(params, "metric", set(METRIC_GROUPS))
        enum(params, "time_range", {"TODAY", "THIS_WEEK", "THIS_MONTH", "LAST_MONTH", "THIS_YEAR", "ALL"})
        missing += require(["metric", "time_range"], params)
        if params.get("group_by") and params["group_by"] not in METRIC_GROUPS.get(params.get("metric"), set()):
            raise ValueError("Unsupported metric grouping")
        if "filters" in params and not isinstance(params["filters"], dict):
            raise ValueError("Invalid metric filters")
        filters = params.get("filters", {})
        if set(filters) - METRIC_FILTERS.get(params.get("metric"), set()):
            raise ValueError("Unsupported metric filters")
        if any(not isinstance(v, str) or not v.strip() for v in filters.values()):
            raise ValueError("Invalid metric filter values")
    if "view" in params:
        enum(params, "view", {"mine", "pool"})
    out.update(params=params, draft=draft or None, action=("query" if intent in READ_FIELDS else
               "execute" if intent in WRITE_FIELDS else None), missing_fields=list(dict.fromkeys(missing)))
    if intent in READ_FIELDS or intent in WRITE_FIELDS:
        out["answer"] = "请补充：" + "、".join(out["missing_fields"]) if missing else "已整理业务请求，待后端核验。"
    else:
        out["answer"] = "请说明需要咨询的制度或办理的业务。" if intent == "OTHER" else "资料不足，暂无法核实该问题。"
    return out


STUDENT_INTENTS = {"PROFILE_QUERY", "SCORE_QUERY", "SCHEDULE_QUERY", "CASE_QUERY", "ASSESSMENT_QUERY",
                   "FAQ", "SERVICE_DRAFT", "FEEDBACK_DRAFT", "UPGRADE_INTEREST", "OTHER"}


def aware_datetime(value):
    dt = datetime.fromisoformat(string(value, 60).replace("Z", "+00:00"))
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("Timezone required")
    return dt


def validate_student(value, payload=None):
    payload = payload or {}
    value = merge_pending(value, payload)
    out = envelope(value, STUDENT_INTENTS)
    intent = out["intent"]
    fields = {"SERVICE_DRAFT": "service_type title description start_at end_at change_request",
              "FEEDBACK_DRAFT": "category subject teacher_name project_category course_project_id content",
              "UPGRADE_INTEREST": "course_project_id note"}.get(intent, "")
    draft = pick(value.get("draft"), fields.split())
    missing = []
    if intent == "SERVICE_DRAFT":
        enum(draft, "service_type", {"LEAVE", "EXAM", "INFO_CHANGE", "OTHER"})
        missing = require(["service_type", "title", "description"], draft)
        if draft.get("service_type") == "LEAVE":
            missing += require(["start_at", "end_at"], draft)
            for key in ("start_at", "end_at"):
                if draft.get(key):
                    aware_datetime(draft[key])
            if draft.get("start_at") and draft.get("end_at") and aware_datetime(draft["end_at"]) <= aware_datetime(draft["start_at"]):
                missing += ["start_at", "end_at"]
        if draft.get("service_type") == "INFO_CHANGE":
            change = pick(draft.get("change_request"), ["old_values", "new_values"])
            if (not isinstance(change.get("new_values"), dict) or not change["new_values"]
                    or not isinstance(change.get("old_values"), dict)
                    or set(change["new_values"]) != set(change["old_values"])):
                missing.append("change_request")
    if intent == "FEEDBACK_DRAFT":
        enum(draft, "category", {"COMPLAINT", "SUGGESTION", "CONSULTATION"})
        missing = require(["category", "subject", "teacher_name", "project_category", "content"], draft)
    if intent == "UPGRADE_INTEREST":
        missing = require(["course_project_id"], draft)
    out.update(draft=draft or None, missing_fields=list(dict.fromkeys(missing)))
    if fields:
        out["answer"] = "请补充：" + "、".join(out["missing_fields"]) if missing else "已整理草稿，请等待后端核验并核对确认卡。"
    else:
        out["answer"] = "资料不足，暂无法核实该问题。" if intent == "FAQ" else "请说明需要查询或办理的业务。"
        if intent == "OTHER" and "OUT_OF_SCOPE" in out["warnings"]:
            out["answer"] = "学生助手不提供员工内部资料，请咨询学生服务或办理本人业务。"
        elif intent == "OTHER" and "ADMIN_SERVICE_PAGE" in out["warnings"]:
            out["answer"] = "请到行政服务页面查看本人请假、考务或资料更正申请的处理结果。"
    if payload.get("observe_emotion") is True and value.get("observation") is not None:
        observation = pick(value["observation"], ["emotion_state", "confidence", "direct_signal"])
        enum(observation, "emotion_state", {"HEALTHY", "NEGATIVE", "VERY_NEGATIVE", "UNKNOWN"})
        confidence = observation.get("confidence", 0.0)
        if type(confidence) not in (int, float) or not 0 <= confidence <= 1:
            raise ValueError("Invalid confidence")
        out["observation"] = {"emotion_state": observation.get("emotion_state", "UNKNOWN"),
                              "confidence": confidence, "direct_signal": False}
    return out


def validate_visitor(value, payload=None):
    payload = payload or {}
    value = dict(value)
    if value.pop("mode", "VISITOR_ANSWER") != "VISITOR_ANSWER":
        raise ValueError("Invalid visitor mode")
    out = envelope(value, {"FAQ", "LEAD_DRAFT", "ACTIVITY_DRAFT", "OUT_OF_SCOPE"})
    out["mode"] = "VISITOR_ANSWER"
    intent = out["intent"]
    fields = {"LEAD_DRAFT": ["name", "mobile"], "ACTIVITY_DRAFT": ["name", "mobile", "event_id"]}.get(intent, [])
    draft = pick(value.get("draft"), fields)
    previous = payload.get("draft") or {}
    if not isinstance(previous, dict):
        raise ValueError("Invalid visitor draft")
    draft = {**{k: v for k, v in previous.items() if k in fields},
             **{k: v for k, v in draft.items() if not absent(v)}}
    missing = require(fields, draft)
    if draft.get("mobile") and not re.fullmatch(r"1[3-9]\d{9}", str(draft["mobile"])):
        missing.append("mobile")
    if intent == "ACTIVITY_DRAFT" and draft.get("event_id"):
        event_ids = {str(e.get("id")) for e in payload.get("open_events", []) if isinstance(e, dict)}
        if str(draft["event_id"]) not in event_ids:
            draft.pop("event_id")
            missing.append("event_id")
    out.update(draft=draft or None, missing_fields=list(dict.fromkeys(missing)))
    if fields:
        out["answer"] = "请补充：" + "、".join(out["missing_fields"]) if missing else "请核对咨询或活动意向，确认后由系统办理。活动资格及余位以系统核验为准。"
    else:
        out["answer"] = "仅支持公开咨询、留资和活动意向登记，无法访问内部业务资料。" if intent == "OUT_OF_SCOPE" else "公开知识库尚未提供可核实的资料，可先说明咨询意向或登记联系信息。"
    return out


def validate_assessment(value, payload):
    if value.get("schema_version") != "1.0" or value.get("mode") != "ASSESSMENT_EXTRACT":
        raise ValueError("Invalid assessment schema")
    if not isinstance(value.get("facts"), dict) or not isinstance(value.get("evidence", []), list):
        raise ValueError("Invalid assessment extraction")
    confirmed = payload.get("confirmed_facts") or {}
    resume = payload.get("resume_text", "")
    string(resume, 100000)  # Validate without changing evidence line numbers.
    required = strings(payload.get("required_fields", ["education"]))
    allowed = {"education", "language_level", "date_of_birth", "city", "gender", "study_purpose"} | set(required)
    forbidden = {"score", "decision", "match", "match_level", "match_result"}
    facts = {key: val for key, val in confirmed.items() if key not in forbidden and not absent(val)}
    evidence = []
    warnings = []
    lines = resume.splitlines()
    for item in value.get("evidence", []):
        if not isinstance(item, dict):
            continue
        field, ref, snippet = (item.get(k) for k in ("field", "source_ref", "snippet"))
        match = re.fullmatch(r"resume:p([1-9]\d*)", ref or "")
        if (field not in allowed or field in forbidden or not match or not isinstance(snippet, str)
                or not snippet or len(snippet) > 160 or re.search(r"\d{15,19}", snippet)
                or int(match[1]) > len(lines) or snippet not in lines[int(match[1])-1]):
            warnings.append("UNVERIFIED_EVIDENCE_DROPPED")
            continue
        fact = value["facts"].get(field)
        if absent(fact) or isinstance(fact, (dict, list, bool)):
            continue
        if field in facts:
            if str(facts[field]) != str(fact):
                warnings.append("CONFIRMED_FACT_CONFLICT:" + field)
            continue
        facts[field] = string(str(fact), 200)
        evidence.append({"field": field, "source_ref": ref, "snippet": snippet})
    missing = [field for field in required if absent(facts.get(field))]
    if not resume:
        warnings.append("NO_RESUME_TEXT")
    if missing:
        warnings.append("NEEDS_MANUAL_CONFIRMATION")
    return {"schema_version": "1.0", "mode": "ASSESSMENT_EXTRACT", "facts": facts,
            "evidence": evidence, "missing_fields": missing, "warnings": list(dict.fromkeys(warnings))}


def prepare_payload(payload, kind):
    if payload.get("schema_version", "1.0") != "1.0":
        raise ValueError("Unsupported input schema")
    # Never forward unknown top-level fields (in particular tokens or credentials).
    fields = {"message", "message_id", "conversation_id", "context", "history", "draft", "pending",
              "business_now", "business_timezone", "candidates"}
    fields |= {"visitor": {"public_projects", "open_events"}, "enterprise": {"actor"},
               "student": {"input_kind", "observe_emotion"},
               "assessment": {"confirmed_facts", "resume_text", "project_rules", "required_fields"}}[kind]
    out = {key: value for key, value in payload.items() if key in fields}
    out["schema_version"] = "1.0"
    if kind != "assessment":
        out["message"] = string(payload.get("message"), 8000)
        if not out["message"]:
            raise ValueError("Empty message")
        history = payload.get("history", [])
        if not isinstance(history, list):
            raise ValueError("Invalid history")
        out["history"] = [{"role": h["role"], "content": string(h.get("content"), 8000)}
                          for h in history[-8:] if isinstance(h, dict) and h.get("role") in {"user", "assistant"}]
    return out
