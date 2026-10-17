"""
M3 统一待办 —— 实时聚合，无 todo 表

六类待办中 M3 负责五类（日报退回由 M5 的日报模块提供，暂不实现，留扩展点）：
  1. LEAD_POOL      本部门公共池未认领客户
  2. LEAD_FOLLOW_UP 本人名下到期跟进（已确认：不做状态过滤，设过计划且到期即算）
  3. SERVICE_PENDING 待我审批 / 主管部门待办 / 管理员全量
  4. FEEDBACK_POOL  售后池未认领（需 can_handle_feedback；标题不含投诉正文）
  5. PSYCH_ALERT    待复核关怀事项（需 psych_access_enabled；不含心理原文）

待办不落库：完成业务操作后刷新自然消失。所有条目只含权限内对象。
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.admin_service import StudentAdminService
from app.models.feedback_ticket import StudentFeedbackTicket
from app.models.lead import CrmLead
from app.models.organization import SysDepartment
from app.models.psych import StudentPsychAlert
from app.models.student import StudentProfile
from app.models.user import SysUser
from app.repositories.common import visible_student_ids
from app.schemas.workbench import TodoOut

logger = logging.getLogger(__name__)

_ADVISOR_ROLES = ("ADVISOR", "SENIOR_ADVISOR")
_OPEN_ALERT_STATUS = ("PENDING_REVIEW", "CONFIRMED", "HANDLING")
_SOURCE_CAP = 200


def _is_head_of_any(db: Session, actor: SysUser) -> bool:
    return db.scalar(select(SysDepartment.id).where(
        SysDepartment.head_user_id == actor.id).limit(1)) is not None


def _lead_todos(db: Session, actor: SysUser) -> list[TodoOut]:
    todos: list[TodoOut] = []
    is_admin = actor.employee_role == "ADMIN"
    if actor.employee_role not in (*_ADVISOR_ROLES, "ADMIN"):
        return todos

    # 1) 本部门公共池
    pool_stmt = select(CrmLead).where(CrmLead.owner_user_id.is_(None))
    if not is_admin:
        pool_stmt = pool_stmt.where(CrmLead.dept_id == actor.dept_id)
    pool_stmt = pool_stmt.order_by(CrmLead.id.desc()).limit(_SOURCE_CAP)
    for lead in db.scalars(pool_stmt).all():
        todos.append(TodoOut(
            key=f"LEAD_POOL:{lead.id}", type="LEAD_POOL",
            title=f"待认领客户：{lead.name or '未命名客户'}",
            entityId=str(lead.id), relatedType="lead",
            actionRoute=f"/employees/leads/{lead.id}"))

    # 2) 本人到期跟进（不做状态过滤）
    now = datetime.now(timezone.utc)
    fu_stmt = (select(CrmLead)
               .where(CrmLead.owner_user_id == actor.id,
                      CrmLead.next_follow_up_at.isnot(None),
                      CrmLead.next_follow_up_at <= now)
               .order_by(CrmLead.next_follow_up_at.asc())
               .limit(_SOURCE_CAP))
    for lead in db.scalars(fu_stmt).all():
        todos.append(TodoOut(
            key=f"LEAD_FOLLOW_UP:{lead.id}", type="LEAD_FOLLOW_UP",
            title=f"待跟进客户：{lead.name or '未命名客户'}",
            entityId=str(lead.id), relatedType="lead",
            dueAt=lead.next_follow_up_at,
            actionRoute=f"/employees/leads/{lead.id}"))
    return todos


def _service_todos(db: Session, actor: SysUser) -> list[TodoOut]:
    is_admin = actor.employee_role == "ADMIN"
    head_of = _is_head_of_any(db, actor)

    stmt = select(StudentAdminService).where(StudentAdminService.status == "PENDING")
    if is_admin:
        pass
    elif head_of:
        stmt = stmt.where(
            (StudentAdminService.dept_id == actor.dept_id)
            | (StudentAdminService.assignee_user_id == actor.id))
    else:
        stmt = stmt.where(StudentAdminService.assignee_user_id == actor.id)
    stmt = stmt.order_by(StudentAdminService.create_time.asc()).limit(_SOURCE_CAP)

    return [TodoOut(
        key=f"SERVICE_PENDING:{s.id}", type="SERVICE_PENDING",
        title=f"待处理申请：{s.title}",
        entityId=str(s.id), relatedType="admin_service",
        actionRoute=f"/services/{s.id}") for s in db.scalars(stmt).all()]


def _feedback_todos(db: Session, actor: SysUser) -> list[TodoOut]:
    if not actor.can_handle_feedback:
        return []
    stmt = select(StudentFeedbackTicket).where(
        StudentFeedbackTicket.assignee_user_id.is_(None),
        StudentFeedbackTicket.status.in_(("PENDING", "PROCESSING")))
    if actor.employee_role != "ADMIN":
        stmt = stmt.where(StudentFeedbackTicket.dept_id == actor.dept_id)
    stmt = stmt.order_by(StudentFeedbackTicket.create_time.asc()).limit(_SOURCE_CAP)
    # 标题不含投诉正文/主题，避免通知与待办泄露
    return [TodoOut(
        key=f"FEEDBACK_POOL:{t.id}", type="FEEDBACK_POOL",
        title="待受理售后工单",
        entityId=str(t.id), relatedType="feedback_ticket",
        dueAt=t.due_at,
        actionRoute=f"/employees/feedback-tickets/{t.id}")
        for t in db.scalars(stmt).all()]


def _psych_todos(db: Session, actor: SysUser) -> list[TodoOut]:
    if not actor.psych_access_enabled:
        return []
    ids = visible_student_ids(db, actor)
    stmt = select(StudentPsychAlert).join(StudentProfile,StudentProfile.id==StudentPsychAlert.student_profile_id).where(
        StudentPsychAlert.status.in_(_OPEN_ALERT_STATUS),StudentProfile.psych_consent_status=="GRANTED")
    if ids is not None:
        stmt = stmt.where(StudentPsychAlert.student_profile_id.in_(ids))
    stmt = stmt.order_by(StudentPsychAlert.last_triggered_at.desc()).limit(_SOURCE_CAP)

    todos: list[TodoOut] = []
    for alert in db.scalars(stmt).all():
        profile = db.get(StudentProfile, alert.student_profile_id)
        user = db.get(SysUser, profile.user_id) if profile else None
        todos.append(TodoOut(
            key=f"PSYCH_ALERT:{alert.id}", type="PSYCH_ALERT",
            title=f"待复核关怀事项：{user.real_name if user else '学生'}",
            entityId=str(alert.id), relatedType="psych_alert",
            dueAt=alert.last_triggered_at,
            actionRoute=f"/employees/psych-alerts/{alert.id}"))
    return todos


def list_todos(db: Session, actor: SysUser, *, type: str | None = None,
               due_before: datetime | None = None,
               page: int = 1, page_size: int = 20):
    todos: list[TodoOut] = []
    todos.extend(_lead_todos(db, actor))
    todos.extend(_service_todos(db, actor))
    todos.extend(_feedback_todos(db, actor))
    todos.extend(_psych_todos(db, actor))
    from app.models.m5_report_models import Daily
    from app.repositories.m5_report_repository import context
    from app.services.m5_report_service import scoped_daily_query,restricted_daily
    user=context(db,actor)
    for d in db.scalars(scoped_daily_query(user).where(Daily.status.in_(["SUBMITTED","RETURNED"])).order_by(Daily.report_date,Daily.id).limit(_SOURCE_CAP)):
        if restricted_daily(user,d):continue
        if d.status=="RETURNED" and d.user_id==actor.id:
            todos.append(TodoOut(key="DAILY_REPORT_RETURN:"+d.id,type="DAILY_REPORT_RETURN",title="日报已退回，请修改",entityId=d.id,relatedType="daily_report",actionRoute="/employees/daily-reports/"+d.id))
        elif d.status=="SUBMITTED" and user["is_dept_head"] and d.user_id!=actor.id:
            todos.append(TodoOut(key="DAILY_REPORT_REVIEW:"+d.id,type="DAILY_REPORT_REVIEW",title="日报待审核",entityId=d.id,relatedType="daily_report",actionRoute="/employees/daily-reports/"+d.id))

    if type:
        todos = [t for t in todos if t.type == type]
    if due_before is not None:
        todos = [t for t in todos if t.dueAt is None or t.dueAt <= due_before]

    todos.sort(key=lambda t: (t.dueAt is None, t.dueAt or datetime.max.replace(
        tzinfo=timezone.utc), t.type, t.entityId))

    total = len(todos)
    start = (max(page, 1) - 1) * min(max(page_size, 1), 100)
    end = start + min(max(page_size, 1), 100)
    return todos[start:end], total
