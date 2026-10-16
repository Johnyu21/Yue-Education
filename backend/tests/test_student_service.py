"""
行政服务业务测试（M4-02 / M4-03）
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core.errors import InvalidRequestError, StateConflictError, VersionConflictError
from app.core.transaction import with_business_transaction
from app.schemas.service import ServiceCreateRequest
from app.services import student_service


def _leave(start, end, **kw):
    base = dict(service_type="LEAVE", title="请假申请", description="身体不适",
                start_at=start, end_at=end, confirmed=True)
    base.update(kw)
    return ServiceCreateRequest(request_key=uuid.uuid4(), **base)


def test_get_self_overview(student, m4_db):
    dto = student_service.get_self_overview(m4_db, student)
    assert dto.user.realName == "学生甲"
    assert dto.status == "ENROLLED"


def test_submit_leave_success(student, m4_db):
    now = datetime.now(timezone.utc)
    req = _leave(now + timedelta(days=3), now + timedelta(days=3, hours=8))
    with with_business_transaction(m4_db):
        result = student_service.submit_service(m4_db, student, req)
    assert result["status"] == "PENDING"
    assert result["assignee_display_name"] == "顾问甲"  # 班主任 = advisor01（本测试班）


def test_submit_leave_missing_times_rejected(student, m4_db):
    req = ServiceCreateRequest(request_key=uuid.uuid4(), service_type="LEAVE",
                               title="请假", description="身体不适", confirmed=True)
    with pytest.raises(InvalidRequestError):
        with with_business_transaction(m4_db):
            student_service.submit_service(m4_db, student, req)


def test_submit_leave_overlap_rejected(student, m4_db):
    now = datetime.now(timezone.utc)
    r1 = _leave(now + timedelta(days=5), now + timedelta(days=5, hours=8))
    with with_business_transaction(m4_db):
        student_service.submit_service(m4_db, student, r1)
    r2 = _leave(now + timedelta(days=5, hours=4), now + timedelta(days=6))
    with pytest.raises(StateConflictError):
        with with_business_transaction(m4_db):
            student_service.submit_service(m4_db, student, r2)


def test_submit_idempotent_same_request_key(student, m4_db):
    now = datetime.now(timezone.utc)
    req = _leave(now + timedelta(days=7), now + timedelta(days=7, hours=8))
    with with_business_transaction(m4_db):
        r1 = student_service.submit_service(m4_db, student, req)
    with with_business_transaction(m4_db):
        r2 = student_service.submit_service(m4_db, student, req)
    assert r1["id"] == r2["id"]  # 同 request_key 幂等返回既有


def test_cancel_service(student, m4_db):
    now = datetime.now(timezone.utc)
    req = _leave(now + timedelta(days=9), now + timedelta(days=9, hours=8))
    with with_business_transaction(m4_db):
        r = student_service.submit_service(m4_db, student, req)
    with with_business_transaction(m4_db):
        r2 = student_service.cancel_service(m4_db, student, int(r["id"]),
                                            expected_version=r["version"],
                                            request_key=uuid.uuid4(), reason="不请了")
    assert r2["status"] == "CANCELLED"


def test_cancel_wrong_version_conflict(student, m4_db):
    now = datetime.now(timezone.utc)
    req = _leave(now + timedelta(days=11), now + timedelta(days=11, hours=8))
    with with_business_transaction(m4_db):
        r = student_service.submit_service(m4_db, student, req)
    with pytest.raises(VersionConflictError):
        with with_business_transaction(m4_db):
            student_service.cancel_service(m4_db, student, int(r["id"]),
                                           expected_version=r["version"] + 5,
                                           request_key=uuid.uuid4(), reason="x")


def test_list_services_only_self(student, m4_env, m4_db):
    now = datetime.now(timezone.utc)
    with with_business_transaction(m4_db):
        student_service.submit_service(m4_db, student,
                                       _leave(now + timedelta(days=13), now + timedelta(days=13, hours=8)))
    items, total = student_service.list_services(m4_db, student)
    assert total >= 1
    assert all(i.studentProfileId == str(m4_env["profile"]) for i in items)  # 只看到自己
