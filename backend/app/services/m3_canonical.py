"""
M3 确认令牌的“规范化载荷”函数

⚠️ 提议签发（企业助手）与业务接口校验必须使用同一个函数、同一份字段，
   否则 payload_hash 不一致，确认会被拒绝。
"""
from app.schemas.application import ApplicationAdvanceIn
from app.schemas.feedback import FeedbackHandlingRequest
from app.schemas.lead import FollowUpIn, LeadManualIn, LeadTransitionIn
from app.schemas.psych import PsychActionRequest


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def lead_create_payload(data: LeadManualIn) -> dict:
    return {
        "name": data.name,
        "mobile": data.mobile,
        "gender": data.gender,
        "city": data.city,
        "education": data.education,
        "date_of_birth": data.date_of_birth.isoformat() if data.date_of_birth else None,
        "intended_project_id": data.intended_project_id,
        "study_purpose": data.study_purpose,
        "interest_level": data.interest_level,
        "dept_id": data.dept_id,
        "content": data.content,
    }


def follow_up_payload(data: FollowUpIn) -> dict:
    return {
        "content": data.content,
        "follow_up_type": data.follow_up_type,
        "next_follow_up_at": _iso(data.next_follow_up_at),
        "next_follow_up_at_provided":"next_follow_up_at" in data.model_fields_set,
    }


def transition_payload(data: LeadTransitionIn) -> dict:
    return {"target_status": data.target_status, "reason": data.reason}


def decide_service_payload(decision: str, note: str) -> dict:
    return {"decision": decision, "note": note}


def feedback_handling_payload(data: FeedbackHandlingRequest) -> dict:
    return {
        "action": data.action,
        "note": data.note,
        "resolution": data.resolution,
        "assignee_user_id": data.assignee_user_id,
    }


def psych_note_payload(data: PsychActionRequest) -> dict:
    return {"action": data.action, "note": data.note}


def application_advance_payload(case_no: str, data: ApplicationAdvanceIn) -> dict:
    return {
        "case_no": case_no,
        "event_kind": data.event_kind,
        "stage": data.stage,
        "detail": data.detail,
        "assignee_user_id": data.assignee_user_id,
        "occurred_at": _iso(data.occurred_at),
        "expected_sequence": data.expected_sequence,
    }
