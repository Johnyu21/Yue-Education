"""
心理关怀 范围查询（⚠️ 敏感，调用方需先校验 psych_access_enabled）
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.psych import StudentPsychAlert, StudentPsychProfile
from app.repositories.common import paginate


# ---- 观测 ----
def get_latest_version_no(db: Session, profile_id: int) -> int:
    return db.scalar(
        select(func.max(StudentPsychProfile.version_no))
        .where(StudentPsychProfile.student_profile_id == profile_id)
    ) or 0


def get_observation(db: Session, obs_id: int) -> StudentPsychProfile | None:
    return db.get(StudentPsychProfile, obs_id)


def list_observations(db: Session, profile_id: int, *, start_date, end_date,
                      page: int = 1, page_size: int = 20):
    stmt = select(StudentPsychProfile).where(
        StudentPsychProfile.student_profile_id == profile_id)
    if start_date is not None:
        stmt = stmt.where(StudentPsychProfile.assessment_date >= start_date)
    if end_date is not None:
        stmt = stmt.where(StudentPsychProfile.assessment_date <= end_date)
    stmt = stmt.order_by(StudentPsychProfile.observed_at.desc(),
                         StudentPsychProfile.version_no.desc())
    return paginate(db, stmt, page, page_size)


def get_daily_final_states(db: Session, profile_id: int, days: int) -> list[dict]:
    """最近 N 个相邻自然日（业务时区）的最后有效观测；缺失日为 None。

    返回 [{"assessment_date": date, "emotion_state": str|None}, ...]（旧→新）。
    """
    tz = ZoneInfo(settings.business_timezone)
    today = datetime.now(tz).date()
    start = today - timedelta(days=days - 1)

    rows = db.scalars(
        select(StudentPsychProfile)
        .where(
            StudentPsychProfile.student_profile_id == profile_id,
            StudentPsychProfile.is_valid.is_(True),
            StudentPsychProfile.assessment_date >= start,
            StudentPsychProfile.assessment_date <= today,
        )
        .order_by(
            StudentPsychProfile.assessment_date.asc(),
            StudentPsychProfile.observed_at.asc(),
            StudentPsychProfile.version_no.asc(),
        )
    ).all()

    final: dict = {}
    for r in rows:
        final[r.assessment_date] = r.emotion_state

    result = []
    for i in range(days):
        d = start + timedelta(days=i)
        result.append({"assessment_date": d, "emotion_state": final.get(d)})
    return result


# ---- 预警 ----
def get_open_alert(db: Session, profile_id: int) -> StudentPsychAlert | None:
    return db.scalar(
        select(StudentPsychAlert).where(
            StudentPsychAlert.student_profile_id == profile_id,
            StudentPsychAlert.status.in_(("PENDING_REVIEW", "CONFIRMED", "HANDLING")),
        )
    )


def list_alerts(db: Session, *, profile_ids: list[int] | None = None,
                status: str | None = None, severity: str | None = None,
                page: int = 1, page_size: int = 20):
    stmt = select(StudentPsychAlert)
    if profile_ids is not None:                     # None 表示管理员全域
        if not profile_ids:
            return [], 0
        stmt = stmt.where(StudentPsychAlert.student_profile_id.in_(profile_ids))
    if status:
        stmt = stmt.where(StudentPsychAlert.status == status)
    if severity:
        stmt = stmt.where(StudentPsychAlert.severity == severity)
    stmt = stmt.order_by(StudentPsychAlert.last_triggered_at.desc(),
                         StudentPsychAlert.id.desc())
    return paginate(db, stmt, page, page_size)


def get_alert(db: Session, alert_id: int) -> StudentPsychAlert | None:
    return db.get(StudentPsychAlert, alert_id)
