"""
course_project 查询（M2）

⚠️ Repository 不自行 commit；公开查询只返回已发布项目。
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.course_project import CourseProject
from app.repositories.common import paginate


def get_by_id(db: Session, project_id: int) -> CourseProject | None:
    return db.get(CourseProject, project_id)


def get_by_code(db: Session, code: str) -> CourseProject | None:
    return db.scalar(select(CourseProject).where(CourseProject.code == code))


def list_public(db: Session, *, page: int = 1, page_size: int = 20,
                country: str | None = None, keyword: str | None = None):
    """公开列表：只含已发布项目，稳定排序防分页漏项。"""
    stmt = select(CourseProject).where(CourseProject.is_published.is_(True))
    if country:
        stmt = stmt.where(CourseProject.country == country)
    if keyword:
        stmt = stmt.where(CourseProject.name.ilike(f"%{keyword}%"))
    stmt = stmt.order_by(CourseProject.create_time.desc(), CourseProject.id.desc())
    return paginate(db, stmt, page, page_size)


def list_staff(db: Session, *, page: int = 1, page_size: int = 20,
               keyword: str | None = None, dept_id: int | None = None):
    """员工列表：含未发布草稿。"""
    stmt = select(CourseProject)
    if keyword:
        stmt = stmt.where(CourseProject.name.ilike(f"%{keyword}%"))
    if dept_id is not None:
        stmt = stmt.where(CourseProject.default_dept_id == dept_id)
    stmt = stmt.order_by(CourseProject.create_time.desc(), CourseProject.id.desc())
    return paginate(db, stmt, page, page_size)
