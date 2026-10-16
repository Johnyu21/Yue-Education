"""
售后工单业务测试（M4-04）
"""
import uuid

import pytest

from app.core.errors import ForbiddenError, StateConflictError
from app.core.transaction import with_business_transaction
from app.schemas.feedback import FeedbackCreateRequest, FeedbackHandlingRequest, RatingRequest
from app.services import feedback_service


def _ticket(category="COMPLAINT", **kw):
    base = dict(category=category, subject="投诉主题", teacher_name="张老师",
                project_category="教学", content="对课程不满意", confirmed=True)
    base.update(kw)
    return FeedbackCreateRequest(request_key=uuid.uuid4(), **base)


def test_submit_complaint_priority_high_not_leaked(student, m4_db):
    with with_business_transaction(m4_db):
        dto = feedback_service.submit_feedback(m4_db, student, _ticket("COMPLAINT"))
    assert dto.status == "PENDING"
    assert not hasattr(dto, "priority")  # 学生 DTO 不含 priority


def test_submit_suggestion_priority_normal(student, m4_db):
    with with_business_transaction(m4_db):
        dto = feedback_service.submit_feedback(m4_db, student, _ticket("SUGGESTION"))
    assert dto.status == "PENDING"


def test_claim_requires_after_sales(student, m4_db):
    with with_business_transaction(m4_db):
        dto = feedback_service.submit_feedback(m4_db, student, _ticket())
    tid = int(dto.id)
    # 学生无售后能力，无法认领
    with pytest.raises(ForbiddenError):
        with with_business_transaction(m4_db):
            feedback_service.claim_feedback(m4_db, student, tid,
                                            expected_version=dto.version,
                                            request_key=uuid.uuid4())


def test_confirm_reopen_rate_flow(student, m4_db, advisor):
    from app.models.user import SysUser
    from sqlalchemy import text
    # 给 advisor 授售后能力
    m4_db.execute(text("UPDATE sys_user SET can_handle_feedback=true WHERE id=:u"),
                  {"u": advisor.id})
    m4_db.commit()
    actor = m4_db.get(SysUser, advisor.id)

    with with_business_transaction(m4_db):
        dto = feedback_service.submit_feedback(m4_db, student, _ticket())
    tid = int(dto.id)

    with with_business_transaction(m4_db):
        claimed = feedback_service.claim_feedback(m4_db, actor, tid,
                                                  expected_version=dto.version,
                                                  request_key=uuid.uuid4())
    assert claimed.status == "PROCESSING"

    with with_business_transaction(m4_db):
        resolved = feedback_service.handle_feedback(
            m4_db, actor, tid,
            FeedbackHandlingRequest(action="RESOLVE", note="已处理", resolution="已道歉并整改",
                                    expected_version=claimed.version, request_key=uuid.uuid4()))
    assert resolved.status == "RESOLVED"

    with with_business_transaction(m4_db):
        confirmed = feedback_service.confirm_feedback(m4_db, student, tid,
                                                      expected_version=resolved.version,
                                                      request_key=uuid.uuid4())
    assert confirmed.status == "CLOSED"

    with with_business_transaction(m4_db):
        rated = feedback_service.rate_feedback(m4_db, student, tid,
                                               RatingRequest(rating=5, comment="满意",
                                                             expected_version=confirmed.version,
                                                             request_key=uuid.uuid4()))
    assert rated["rating"] == 5


def test_reopen_preserves_history(student, m4_db, advisor):
    from app.models.user import SysUser
    from sqlalchemy import text
    m4_db.execute(text("UPDATE sys_user SET can_handle_feedback=true WHERE id=:u"),
                  {"u": advisor.id})
    m4_db.commit()
    actor = m4_db.get(SysUser, advisor.id)

    with with_business_transaction(m4_db):
        dto = feedback_service.submit_feedback(m4_db, student, _ticket())
    tid = int(dto.id)
    with with_business_transaction(m4_db):
        claimed = feedback_service.claim_feedback(m4_db, actor, tid,
                                                  expected_version=dto.version, request_key=uuid.uuid4())
    with with_business_transaction(m4_db):
        resolved = feedback_service.handle_feedback(
            m4_db, actor, tid,
            FeedbackHandlingRequest(action="RESOLVE", note="处理", resolution="已解决",
                                    expected_version=claimed.version, request_key=uuid.uuid4()))
    with with_business_transaction(m4_db):
        reopened = feedback_service.reopen_feedback(m4_db, student, tid,
                                                    expected_version=resolved.version,
                                                    request_key=uuid.uuid4(), reason="不满意")
    assert reopened.status == "PROCESSING"
    # reopened_count 是内部字段（不进学生 DTO），通过 DB 验证
    from sqlalchemy import text
    count = m4_db.scalar(text("SELECT reopened_count FROM student_feedback_ticket WHERE id=:i"),
                         {"i": tid})
    assert count == 1
