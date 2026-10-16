"""
Repository 公共工具 —— 分页 + 学生范围判定

⚠️ 数据范围过滤在 Repository 层自行拼装（基于 build_scope 暴露的关系字段），
   不改 core/permissions.py（M1 地基）。
   班主任本班 / 顾问本人 / 主管本部门 / 管理员全域 / 学生本人。
"""
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.core.permissions import build_scope
from app.models.student import StudentProfile
from app.models.user import SysUser


def paginate(db: Session, stmt: Select, page: int, page_size: int) -> tuple[list, int]:
    """稳定分页：返回 (items, total)。page 从 1 开始，page_size 最大 100。"""
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all())
    return items, total


def my_profile_id(db: Session, user: SysUser) -> int:
    """当前学生对应的 student_profile.id；非学生返回 -1。"""
    pid = db.scalar(select(StudentProfile.id).where(StudentProfile.user_id == user.id))
    return pid or -1


def visible_student_ids(db: Session, user: SysUser) -> list[int] | None:
    """员工可见的学生档案 id 集合；None 表示管理员全域不限制。

    范围：班主任本班 ∪ 主管本部门 ∪ 顾问本人学生。
    """
    if user.employee_role == "ADMIN":
        return None
    scope = build_scope(db, user, "student")
    conds = []
    if scope.class_teacher_of:
        conds.append(StudentProfile.class_id.in_(scope.class_teacher_of))
    if scope.dept_ids:
        conds.append(StudentProfile.dept_id.in_(scope.dept_ids))
    conds.append(StudentProfile.advisor_user_id == user.id)
    return list(db.scalars(select(StudentProfile.id).where(or_(*conds))).all())


def require_student_visible(db: Session, user: SysUser, profile_id: int) -> StudentProfile:
    """员工访问某学生前校验可见性；越权抛 404（防信息泄露）。"""
    from app.core.errors import NotFoundError

    profile = db.get(StudentProfile, profile_id)
    if profile is None:
        raise NotFoundError("资源不存在")

    ids = visible_student_ids(db, user)
    if ids is not None and profile.id not in ids:
        raise NotFoundError("资源不存在")
    return profile
