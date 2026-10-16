"""
学生档案 / 课程关联 范围查询
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.course_project import CourseProject
from app.models.enrollment import StudentCourseEnrollment
from app.models.student import StudentProfile


def get_profile_by_user(db: Session, user_id: int) -> StudentProfile | None:
    return db.scalar(select(StudentProfile).where(StudentProfile.user_id == user_id))


def get_profile_by_id(db: Session, profile_id: int) -> StudentProfile | None:
    return db.get(StudentProfile, profile_id)


def list_enrollments(db: Session, profile_id: int) -> list[StudentCourseEnrollment]:
    return list(db.scalars(
        select(StudentCourseEnrollment)
        .where(StudentCourseEnrollment.student_profile_id == profile_id)
        .order_by(StudentCourseEnrollment.id)
    ).all())


def get_project_names(db: Session, project_ids: list[int]) -> dict[int, str]:
    """项目 id → 名称，用于课程关联展示。"""
    if not project_ids:
        return {}
    rows = db.execute(
        select(CourseProject.id, CourseProject.name)
        .where(CourseProject.id.in_(project_ids))
    ).all()
    return {pid: name for pid, name in rows}


def get_project(db: Session, project_id: int) -> CourseProject | None:
    return db.get(CourseProject, project_id)
