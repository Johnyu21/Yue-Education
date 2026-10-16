"""
行政服务 范围查询（学生本人 / 班主任当前班或指派 / 主管本部门 / 管理员全域）
"""
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.admin_service import StudentAdminService
from app.models.user import SysUser
from app.repositories.common import my_profile_id, paginate, visible_student_ids


def list_services(db: Session, user: SysUser, *, status: str | None = None,
                  service_type: str | None = None, page: int = 1, page_size: int = 20):
    stmt = select(StudentAdminService)

    if user.is_student:
        stmt = stmt.where(StudentAdminService.student_profile_id == my_profile_id(db, user))
    elif user.employee_role == "ADMIN":
        pass  # 全域
    else:
        ids = visible_student_ids(db, user)
        conds = [StudentAdminService.assignee_user_id == user.id]
        if ids:
            conds.append(StudentAdminService.student_profile_id.in_(ids))
        stmt = stmt.where(or_(*conds))

    if status:
        stmt = stmt.where(StudentAdminService.status == status)
    if service_type:
        stmt = stmt.where(StudentAdminService.service_type == service_type)
    stmt = stmt.order_by(StudentAdminService.create_time.desc(), StudentAdminService.id.desc())
    return paginate(db, stmt, page, page_size)


def get_service(db: Session, service_id: int) -> StudentAdminService | None:
    return db.get(StudentAdminService, service_id)


def get_service_by_request_key(db: Session, request_key) -> StudentAdminService | None:
    return db.scalar(select(StudentAdminService).where(
        StudentAdminService.request_key == request_key))
