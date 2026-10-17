"""
M3 员工侧查询 —— 学生列表 / 售后池（员工视图）

⚠️ Repository 不自行 commit；范围条件由 service 传入（visible_student_ids 等）。
"""
from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.models.feedback_ticket import StudentFeedbackTicket
from app.models.student import StudentProfile
from app.models.user import SysUser
from app.repositories.common import paginate


def list_students(db: Session, visible_ids: list[int] | None, *, class_id: int | None = None,
                  keyword: str | None = None, page: int = 1, page_size: int = 20):
    """员工可见学生列表。visible_ids=None 表示管理员全域。"""
    stmt = select(StudentProfile)
    if visible_ids is not None:
        stmt = stmt.where(StudentProfile.id.in_(visible_ids))
    if class_id is not None:
        stmt = stmt.where(StudentProfile.class_id == class_id)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.join(SysUser, StudentProfile.user_id == SysUser.id).where(
            SysUser.real_name.ilike(like) | SysUser.username.ilike(like))
    stmt = stmt.order_by(StudentProfile.id)
    return paginate(db, stmt, page, page_size)


def list_staff_tickets(db: Session, *, dept_id: int | None = None,
                       assignee_user_id: int | None = None, pool_only: bool = False,
                       status: str | None = None, category: str | None = None,
                       page: int = 1, page_size: int = 20):
    """售后工单员工视图：部门范围 + 池/本人 + 状态/类型筛选。

    ⚠️ 只应由有 can_handle_feedback 的调用方使用（权限在 service 校验）。
    """
    stmt = select(StudentFeedbackTicket)
    if dept_id is not None:
        stmt = stmt.where(StudentFeedbackTicket.dept_id == dept_id)
    if pool_only:
        stmt = stmt.where(StudentFeedbackTicket.assignee_user_id.is_(None))
    elif assignee_user_id is not None:
        stmt = stmt.where(StudentFeedbackTicket.assignee_user_id == assignee_user_id)
    if status:
        stmt = stmt.where(StudentFeedbackTicket.status == status)
    if category:
        stmt = stmt.where(StudentFeedbackTicket.category == category)

    priority_rank = case(
        (StudentFeedbackTicket.priority == "HIGH", 0),
        else_=1,
    )
    stmt = stmt.order_by(priority_rank.asc(),
                         StudentFeedbackTicket.create_time.desc(),
                         StudentFeedbackTicket.id.desc())
    return paginate(db, stmt, page, page_size)
