"""
成绩 / 日程 / 申请进度 查询（学生本人或员工授权范围）
"""
from sqlalchemy import func, select
from app.core.config import settings
from sqlalchemy.orm import Session

from app.models.academic_schedule import StudentAcademicSchedule
from app.models.application_progress import StudentApplicationProgress
from app.models.score import StudentScore
from app.repositories.common import paginate


# ---- 成绩（只读，无业务写接口）----
def list_scores(db: Session, profile_id: int, *, enrollment_id: int | None = None,
                subject: str | None = None, page: int = 1, page_size: int = 20):
    stmt = select(StudentScore).where(StudentScore.student_profile_id == profile_id)
    if settings.environment=="prod":stmt=stmt.where(StudentScore.data_source!="TEST")
    if enrollment_id is not None:
        stmt = stmt.where(StudentScore.enrollment_id == enrollment_id)
    if subject:
        stmt = stmt.where(StudentScore.subject == subject)
    stmt = stmt.order_by(StudentScore.graded_at.desc(), StudentScore.id.desc())
    return paginate(db, stmt, page, page_size)


# ---- 日程 ----
def list_schedules(db: Session, profile_id: int, *, start_at=None, end_at=None,
                   schedule_type: str | None = None, page: int = 1, page_size: int = 20):
    stmt = select(StudentAcademicSchedule).where(
        StudentAcademicSchedule.student_profile_id == profile_id)
    if settings.environment=="prod":stmt=stmt.where(StudentAcademicSchedule.data_source!="TEST")
    if start_at is not None:
        stmt = stmt.where(StudentAcademicSchedule.start_at >= start_at)
    if end_at is not None:
        stmt = stmt.where(StudentAcademicSchedule.start_at <= end_at)
    if schedule_type:
        stmt = stmt.where(StudentAcademicSchedule.schedule_type == schedule_type)
    stmt = stmt.order_by(StudentAcademicSchedule.start_at.asc(), StudentAcademicSchedule.id.asc())
    return paginate(db, stmt, page, page_size)


def get_schedule(db: Session, schedule_id: int) -> StudentAcademicSchedule | None:
    return db.get(StudentAcademicSchedule, schedule_id)


# ---- 申请进度 ----
def list_application_cases(db: Session, profile_id: int, *, item_type: str | None = None,
                           stage: str | None = None, page: int = 1, page_size: int = 20):
    """每个 case_no 取最新一条（sequence_no 最大）作为当前事项。"""
    max_seq = (
        select(StudentApplicationProgress.case_no,
               func.max(StudentApplicationProgress.sequence_no).label("max_seq"))
        .where(StudentApplicationProgress.student_profile_id == profile_id)
        .group_by(StudentApplicationProgress.case_no)
        .subquery()
    )
    stmt = (
        select(StudentApplicationProgress)
        .join(
            max_seq,
            (StudentApplicationProgress.case_no == max_seq.c.case_no)
            & (StudentApplicationProgress.sequence_no == max_seq.c.max_seq),
        )
        .where(StudentApplicationProgress.student_profile_id == profile_id)
    )
    if item_type:
        stmt = stmt.where(StudentApplicationProgress.item_type == item_type)
    if stage:
        stmt = stmt.where(StudentApplicationProgress.stage == stage)
    stmt = stmt.order_by(StudentApplicationProgress.occurred_at.desc())
    return paginate(db, stmt, page, page_size)


def get_case_timeline(db: Session, profile_id: int, case_no, *, page: int = 1,
                      page_size: int = 20):
    """按 sequence_no 升序返回某事项全部事件。"""
    stmt = select(StudentApplicationProgress).where(
        StudentApplicationProgress.student_profile_id == profile_id,
        StudentApplicationProgress.case_no == case_no,
    ).order_by(StudentApplicationProgress.sequence_no.asc())
    return paginate(db, stmt, page, page_size)
