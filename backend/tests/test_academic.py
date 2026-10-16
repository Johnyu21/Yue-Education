"""
成绩 / 日程 / 进度 / 升学意向 业务测试（M4-07）
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core.errors import InvalidRequestError, NotFoundError, StateConflictError
from app.core.transaction import with_business_transaction
from app.schemas.student import ReminderRequest
from app.services import academic_service


def test_my_scores_read_only(student, m4_db):
    items, total = academic_service.list_scores(m4_db, student)
    assert total == 0  # 无成绩数据时返回空，不报错


def test_set_reminder_requires_own_schedule(student, m4_db, m4_env):
    from sqlalchemy import text
    now = datetime.now(timezone.utc)
    m4_db.execute(text("""
        INSERT INTO student_academic_schedule(student_profile_id,schedule_type,title,start_at,data_source,created_by_user_id)
        VALUES (:p,'EXAM','测试考试',:s,'TEST',:a)
    """), {"p": m4_env["profile"], "s": now + timedelta(days=5), "a": m4_env["advisor"]})
    m4_db.commit()
    sid = m4_db.scalar(text("SELECT id FROM student_academic_schedule WHERE title='测试考试'"))

    req = ReminderRequest(remind_at=now + timedelta(days=4), expected_version=1,
                          request_key=uuid.uuid4())
    with with_business_transaction(m4_db):
        r = academic_service.set_reminder(m4_db, student, sid, req)
    assert r["reminderRevision"] == 2


def test_set_reminder_past_rejected(student, m4_db, m4_env):
    from sqlalchemy import text
    now = datetime.now(timezone.utc)
    m4_db.execute(text("""
        INSERT INTO student_academic_schedule(student_profile_id,schedule_type,title,start_at,data_source,created_by_user_id)
        VALUES (:p,'EXAM','测试考试2',:s,'TEST',:a)
    """), {"p": m4_env["profile"], "s": now + timedelta(days=5), "a": m4_env["advisor"]})
    m4_db.commit()
    sid = m4_db.scalar(text("SELECT id FROM student_academic_schedule WHERE title='测试考试2'"))

    req = ReminderRequest(remind_at=now - timedelta(days=1), expected_version=1,
                          request_key=uuid.uuid4())
    with pytest.raises(InvalidRequestError):
        with with_business_transaction(m4_db):
            academic_service.set_reminder(m4_db, student, sid, req)


def test_application_cases_empty(student, m4_db):
    items, total = academic_service.list_application_cases(m4_db, student)
    assert total == 0


def test_initial_assessment_no_lead(student, m4_db):
    result = academic_service.get_initial_assessment(m4_db, student)
    assert result["available"] is False


def test_upgrade_interest_requires_source_lead(student, m4_db):
    from app.schemas.student import UpgradeInterestRequest
    req = UpgradeInterestRequest(course_project_id=1, request_key=uuid.uuid4(), confirmed=True)
    with pytest.raises(StateConflictError):
        with with_business_transaction(m4_db):
            academic_service.create_upgrade_interest(m4_db, student, req)
