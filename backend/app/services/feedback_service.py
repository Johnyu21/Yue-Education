"""
售后工单（投诉/建议/咨询）业务

学生侧 + 导出的 M3 Interface（claim_feedback / handle_feedback）。
priority 只由后端决定，学生 DTO 不返回 priority 与内部历史。
"""
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.confirmation import verify_confirmation
from app.core.errors import (
    ForbiddenError,
    InvalidRequestError,
    NotFoundError,
    StateConflictError,
    VersionConflictError,
)
from app.core.notification import notify
from app.models.feedback_ticket import StudentFeedbackTicket
from app.models.student import StudentProfile
from app.models.user import SysUser
from app.repositories import feedback_repo
from app.repositories.common import my_profile_id
from app.schemas.feedback import (
    FeedbackCreateRequest,
    FeedbackHandlingRequest,
    FeedbackStaffDTO,
    FeedbackStudentDTO,
    RatingRequest,
)

logger = logging.getLogger(__name__)


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def _student_user_id(db: Session, t: StudentFeedbackTicket) -> int:
    return db.scalar(select(StudentProfile.user_id).where(
        StudentProfile.id == t.student_profile_id))


def _to_student_dto(t: StudentFeedbackTicket) -> FeedbackStudentDTO:
    return FeedbackStudentDTO(
        id=str(t.id), category=t.category, subject=t.subject, teacherName=t.teacher_name,
        projectCategory=t.project_category,
        courseProjectId=str(t.course_project_id) if t.course_project_id else None,
        content=t.content, status=t.status, resolution=t.resolution,
        firstResponseAt=t.first_response_at, resolvedAt=t.resolved_at, closedAt=t.closed_at,
        satisfactionRating=t.satisfaction_rating, satisfactionComment=t.satisfaction_comment,
        createTime=t.create_time, version=t.version,
    )


def _to_staff_dto(t: StudentFeedbackTicket) -> FeedbackStaffDTO:
    return FeedbackStaffDTO(
        **_to_student_dto(t).model_dump(),
        priority=t.priority, deptId=str(t.dept_id),
        assigneeUserId=str(t.assignee_user_id) if t.assignee_user_id else None,
        dueAt=t.due_at, firstResolvedAt=t.first_resolved_at,
        isNotified=t.is_notified, reopenedCount=t.reopened_count,
        handlingHistory=t.handling_history or [],
    )


def canonical_feedback_payload(req: FeedbackCreateRequest) -> dict:
    """确认令牌内容指纹来源：与提交时完全一致。"""
    return {
        "category": req.category, "subject": req.subject, "teacher_name": req.teacher_name,
        "project_category": req.project_category, "course_project_id": req.course_project_id,
        "content": req.content,
    }


# =============================================================
# 学生侧
# =============================================================
def submit_feedback(db: Session, user: SysUser, req: FeedbackCreateRequest) -> FeedbackStudentDTO:
    profile_id = my_profile_id(db, user)
    if profile_id <= 0:
        raise NotFoundError("学生档案不存在")

    existing = feedback_repo.get_ticket_by_request_key(db, req.request_key)
    if existing is not None:
        return _to_student_dto(existing)

    if req.confirmation_token:
        verify_confirmation(user, req.confirmation_token, operation="SUBMIT_FEEDBACK",
                            entity_id=None, payload=canonical_feedback_payload(req))

    profile = db.get(StudentProfile, profile_id)
    priority = "HIGH" if req.category == "COMPLAINT" else "NORMAL"

    t = StudentFeedbackTicket(
        student_profile_id=profile_id,
        dept_id=profile.dept_id,
        assignee_user_id=None,
        category=req.category,
        subject=req.subject,
        teacher_name=req.teacher_name,
        project_category=req.project_category,
        course_project_id=req.course_project_id,
        content=req.content,
        priority=priority,
        status="PENDING",
        handling_history=[],
        request_key=req.request_key,
        version=1,
    )
    db.add(t)
    db.flush()

    # 通知受理部门配置管理者（不含投诉正文）
    from app.models.organization import SysDepartment
    dept_head = db.scalar(select(SysDepartment.head_user_id).where(
        SysDepartment.id == profile.dept_id))
    if dept_head:
        notify(db, f"ticket:{t.id}:submitted:1", [dept_head],
               category="SYSTEM", title="新售后工单",
               content=f"收到一条「{req.category}」工单，请安排售后处理",
               related_type="feedback_ticket", related_id=t.id)

    return _to_student_dto(t)


def list_my_tickets(db: Session, user: SysUser, *, status: str | None = None,
                    page: int = 1, page_size: int = 20):
    profile_id = my_profile_id(db, user)
    items, total = feedback_repo.list_tickets_by_student(
        db, profile_id, status=status, page=page, page_size=page_size)
    return [_to_student_dto(t) for t in items], total


def get_my_ticket(db: Session, user: SysUser, ticket_id: int) -> FeedbackStudentDTO:
    profile_id = my_profile_id(db, user)
    t = feedback_repo.get_ticket(db, ticket_id)
    if t is None or t.student_profile_id != profile_id:
        raise NotFoundError("资源不存在")
    return _to_student_dto(t)


def confirm_feedback(db: Session, user: SysUser, ticket_id: int, *,
                     expected_version: int, request_key: UUID) -> FeedbackStudentDTO:
    """API063 学生确认解决并关闭。"""
    profile_id = my_profile_id(db, user)
    t = feedback_repo.get_ticket(db, ticket_id)
    if t is None or t.student_profile_id != profile_id:
        raise NotFoundError("资源不存在")
    if t.version != expected_version:
        raise VersionConflictError(t.version)
    if t.status != "RESOLVED":
        raise StateConflictError("当前状态不允许关闭")

    t.status = "CLOSED"
    t.closed_at = datetime.now(timezone.utc)
    t.handling_history = list(t.handling_history or []) + [
        {"action": "CLOSED", "actor": str(user.id), "at": _iso(datetime.now(timezone.utc)),
         "request_key": str(request_key)}]
    t.version += 1
    db.flush()
    return _to_student_dto(t)


def reopen_feedback(db: Session, user: SysUser, ticket_id: int, *,
                    expected_version: int, request_key: UUID, reason: str) -> FeedbackStudentDTO:
    """API064 学生不认可解决结果：RESOLVED → PROCESSING，保留前次解决历史。"""
    profile_id = my_profile_id(db, user)
    t = feedback_repo.get_ticket(db, ticket_id)
    if t is None or t.student_profile_id != profile_id:
        raise NotFoundError("资源不存在")
    if t.version != expected_version:
        raise VersionConflictError(t.version)
    if t.status != "RESOLVED":
        raise StateConflictError("当前状态不允许此操作")

    t.status = "PROCESSING"
    t.reopened_count += 1
    t.is_notified = False
    t.handling_history = list(t.handling_history or []) + [
        {"action": "REOPEN", "actor": str(user.id), "at": _iso(datetime.now(timezone.utc)),
         "note": reason, "request_key": str(request_key)}]
    t.version += 1
    db.flush()
    return _to_student_dto(t)


def rate_feedback(db: Session, user: SysUser, ticket_id: int, req: RatingRequest) -> dict:
    """API065 学生评价 1~5 分（仅 CLOSED 且未评价）。"""
    profile_id = my_profile_id(db, user)
    t = feedback_repo.get_ticket(db, ticket_id)
    if t is None or t.student_profile_id != profile_id:
        raise NotFoundError("资源不存在")
    if t.version != req.expected_version:
        raise VersionConflictError(t.version)
    if t.status != "CLOSED":
        raise StateConflictError("仅关闭的工单可评价")
    if t.satisfaction_rating is not None:
        raise StateConflictError("该工单已评价")

    t.satisfaction_rating = req.rating
    t.satisfaction_comment = req.comment
    t.rated_at = datetime.now(timezone.utc)
    t.version += 1
    db.flush()
    return {"id": str(t.id), "rating": t.satisfaction_rating, "ratedAt": t.rated_at,
            "version": t.version}


# =============================================================
# 员工侧（M3 控制器复用）
# =============================================================
def _require_after_sales(db: Session, actor: SysUser, t: StudentFeedbackTicket) -> None:
    if not actor.can_handle_feedback:
        raise ForbiddenError("需要售后处理权限")
    if actor.employee_role == "ADMIN":
        return
    if t.dept_id != actor.dept_id:
        raise NotFoundError("资源不存在")


def claim_feedback(db: Session, actor: SysUser, ticket_id: int, *,
                   expected_version: int, request_key: UUID) -> FeedbackStaffDTO:
    """API061 售后认领（M3 控制器复用）。"""
    t = feedback_repo.get_ticket(db, ticket_id)
    if t is None:
        raise NotFoundError("资源不存在")
    _require_after_sales(db, actor, t)
    if t.version != expected_version:
        raise VersionConflictError(t.version)
    if t.assignee_user_id is not None:
        raise StateConflictError("该工单已被认领")

    now = datetime.now(timezone.utc)
    t.assignee_user_id = actor.id
    t.status = "PROCESSING"
    if t.first_response_at is None:
        t.first_response_at = now
    t.handling_history = list(t.handling_history or []) + [
        {"action": "CLAIM", "actor": str(actor.id), "at": _iso(now), "request_key": str(request_key)}]
    t.version += 1
    db.flush()
    return _to_staff_dto(t)


def handle_feedback(db: Session, actor: SysUser, ticket_id: int,
                    req: FeedbackHandlingRequest) -> FeedbackStaffDTO:
    """API062 售后跟进/解决/转派（M3 控制器复用）。"""
    t = feedback_repo.get_ticket(db, ticket_id)
    if t is None:
        raise NotFoundError("资源不存在")
    _require_after_sales(db, actor, t)
    if t.version != req.expected_version:
        raise VersionConflictError(t.version)

    now = datetime.now(timezone.utc)
    history = list(t.handling_history or [])

    if req.action == "ASSIGN":
        if actor.employee_role != "ADMIN" and actor.dept_id != t.dept_id:
            raise ForbiddenError("无权转派")
        new_assignee = db.get(SysUser, req.assignee_user_id) if req.assignee_user_id else None
        if new_assignee is None or not new_assignee.can_handle_feedback:
            raise InvalidRequestError("目标处理人需有售后权限")
        t.assignee_user_id = new_assignee.id
        if t.status == "PENDING":
            t.status = "PROCESSING"
            if t.first_response_at is None:
                t.first_response_at = now
        history.append({"action": "ASSIGN", "actor": str(actor.id), "at": _iso(now),
                        "note": req.note, "assignee_to": new_assignee.id,
                        "request_key": str(req.request_key)})
    elif req.action == "NOTE":
        if t.assignee_user_id != actor.id:
            raise ForbiddenError("仅受理人可跟进")
        history.append({"action": "NOTE", "actor": str(actor.id), "at": _iso(now),
                        "note": req.note, "request_key": str(req.request_key)})
    elif req.action == "RESOLVE":
        if t.assignee_user_id != actor.id:
            raise ForbiddenError("仅受理人可解决")
        if not req.resolution:
            raise InvalidRequestError("解决必须提供结果说明")
        if t.first_resolved_at is None:
            t.first_resolved_at = now
        t.resolved_at = now
        t.resolution = req.resolution
        t.is_notified = True
        t.status = "RESOLVED"
        history.append({"action": "RESOLVE", "actor": str(actor.id), "at": _iso(now),
                        "resolution": req.resolution, "request_key": str(req.request_key)})

    t.handling_history = history
    t.version += 1
    db.flush()

    if req.action == "RESOLVE":
        sid = _student_user_id(db, t)
        if sid:
            notify(db, f"ticket:{t.id}:resolved:{t.version}", [sid],
                   category="FEEDBACK_RESOLVED", title="售后工单已解决",
                   content=f"您的工单「{t.subject}」已有处理结果，请查看并确认",
                   related_type="feedback_ticket", related_id=t.id)

    return _to_staff_dto(t)
