"""
event_lecture / event_registration 查询（M2）

⚠️ Repository 不自行 commit；锁行只返回对象，事务提交由 service 层负责。
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.event import EventLecture, EventRegistration
from app.repositories.common import paginate

# 占名额的报名状态（已取消不占名额）
ACTIVE_STATUSES = ("REGISTERED", "CHECKED_IN")


def get_by_id(db: Session, event_id: int) -> EventLecture | None:
    return db.get(EventLecture, event_id)


def lock_by_id(db: Session, event_id: int) -> EventLecture | None:
    """在事务内锁定活动行，用于名额复查（报名与取消共用同一锁序）。"""
    return db.scalar(
        select(EventLecture).where(EventLecture.id == event_id).with_for_update().execution_options(populate_existing=True)
    )


def list_by_status(db: Session, *, status: str = "OPEN",
                   page: int = 1, page_size: int = 20):
    stmt = (
        select(EventLecture)
        .where(EventLecture.status == status)
        .order_by(EventLecture.start_at.asc(), EventLecture.id.asc())
    )
    return paginate(db, stmt, page, page_size)


def count_active_registrations(db: Session, event_id: int) -> int:
    """该活动当前占用名额的报名数。"""
    return db.scalar(
        select(func.count())
        .select_from(EventRegistration)
        .where(
            EventRegistration.event_id == event_id,
            EventRegistration.status.in_(ACTIVE_STATUSES),
        )
    ) or 0


def count_active_map(db: Session, event_ids: list[int]) -> dict[int, int]:
    """批量统计占用名额的报名数（消除列表 N+1）。"""
    if not event_ids:
        return {}
    rows = db.execute(
        select(EventRegistration.event_id, func.count())
        .where(
            EventRegistration.event_id.in_(event_ids),
            EventRegistration.status.in_(ACTIVE_STATUSES),
        )
        .group_by(EventRegistration.event_id)
    ).all()
    return {event_id: count for event_id, count in rows}


def get_registration(db: Session, registration_id: int) -> EventRegistration | None:
    return db.get(EventRegistration, registration_id)


def get_registration_by_request_key(db: Session, request_key) -> EventRegistration | None:
    """幂等重试：同一 request_key 直接返回既有报名。"""
    return db.scalar(
        select(EventRegistration).where(EventRegistration.request_key == request_key)
    )


def get_registration_by_event_mobile(db: Session, event_id: int,
                                     mobile: str) -> EventRegistration | None:
    """同一活动同手机号唯一（数据库唯一约束的业务侧预检）。"""
    return db.scalar(
        select(EventRegistration).where(
            EventRegistration.event_id == event_id,
            EventRegistration.mobile == mobile,
        )
    )


def list_student_registrations(db: Session, student_profile_id: int, *,
                               page: int = 1, page_size: int = 20):
    stmt = (
        select(EventRegistration)
        .where(EventRegistration.student_profile_id == student_profile_id)
        .order_by(EventRegistration.registered_at.desc(), EventRegistration.id.desc())
    )
    return paginate(db, stmt, page, page_size)
