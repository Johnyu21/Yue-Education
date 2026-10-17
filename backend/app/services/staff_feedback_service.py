"""
M3 员工售后池 —— 列表/详情（员工视图）

⚠️ 投诉正文属敏感数据：必须 can_handle_feedback；部门范围外一律 404。
   认领/处理/转派由 M4 的 feedback_service.claim_feedback / handle_feedback 提供。
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.feedback_ticket import StudentFeedbackTicket
from app.models.student import StudentProfile
from app.models.user import SysUser
from app.repositories import employee as employee_repo
from app.repositories import feedback_repo
from app.services.m3_errors import CapabilityDeniedError

from app.core.errors import NotFoundError


def _require_after_sales(actor: SysUser) -> None:
    if not actor.can_handle_feedback:
        raise CapabilityDeniedError("需要售后处理权限")


def _require_ticket_visible(db: Session, actor: SysUser, ticket: StudentFeedbackTicket) -> None:
    _require_after_sales(actor)
    if actor.employee_role == "ADMIN":
        return
    if ticket.dept_id != actor.dept_id:
        raise NotFoundError("资源不存在")


def _to_staff_dict(db: Session, t: StudentFeedbackTicket) -> dict:
    profile = db.get(StudentProfile, t.student_profile_id)
    student_user = db.get(SysUser, profile.user_id) if profile else None
    return {
        "id": str(t.id),
        "category": t.category,
        "subject": t.subject,
        "teacherName": t.teacher_name,
        "projectCategory": t.project_category,
        "courseProjectId": str(t.course_project_id) if t.course_project_id else None,
        "content": t.content,
        "status": t.status,
        "resolution": t.resolution,
        "firstResponseAt": t.first_response_at,
        "resolvedAt": t.resolved_at,
        "closedAt": t.closed_at,
        "satisfactionRating": t.satisfaction_rating,
        "satisfactionComment": t.satisfaction_comment,
        "createTime": t.create_time,
        "version": t.version,
        # —— 员工侧附加（需售后授权才可见）——
        "priority": t.priority,
        "deptId": str(t.dept_id),
        "assigneeUserId": str(t.assignee_user_id) if t.assignee_user_id else None,
        "dueAt": t.due_at,
        "firstResolvedAt": t.first_resolved_at,
        "isNotified": t.is_notified,
        "reopenedCount": t.reopened_count,
        "handlingHistory": t.handling_history or [],
        "studentProfileId": str(t.student_profile_id),
        "studentDisplayName": student_user.real_name if student_user else "",
    }


def list_staff_tickets(db: Session, actor: SysUser, *, status: str | None = None,
                       assignee: str | None = None, category: str | None = None,
                       page: int = 1, page_size: int = 20):
    _require_after_sales(actor)
    dept_id = None if actor.employee_role == "ADMIN" else actor.dept_id
    pool_only = assignee == "pool"
    assignee_user_id = actor.id if assignee == "me" else None
    items, total = employee_repo.list_staff_tickets(
        db, dept_id=dept_id, assignee_user_id=assignee_user_id,
        pool_only=pool_only, status=status, category=category,
        page=page, page_size=page_size)
    return [_to_staff_dict(db, t) for t in items], total


def get_staff_ticket(db: Session, actor: SysUser, ticket_id: int) -> dict:
    t = feedback_repo.get_ticket(db, ticket_id)
    if t is None:
        raise NotFoundError("资源不存在")
    _require_ticket_visible(db, actor, t)
    return _to_staff_dict(db, t)
