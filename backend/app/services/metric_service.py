"""
企业助手白名单聚合指标（方案 A+）

⚠️ 只接受枚举的 metric / group_by / time_range，不接受任意字段名或表达式；
   所有查询先按当前员工 Scope 过滤，再聚合；敏感指标要求对应能力。
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ForbiddenError, InvalidRequestError
from app.core.permissions import build_scope
from app.models.admin_service import StudentAdminService
from app.models.application_progress import StudentApplicationProgress
from app.models.feedback_ticket import StudentFeedbackTicket
from app.models.follow_up import CrmFollowUp
from app.models.lead import CrmLead
from app.models.organization import SysDepartment
from app.models.psych import StudentPsychAlert
from app.models.student import StudentProfile
from app.models.user import SysUser
from app.repositories.common import visible_student_ids

METRICS = {
    "LEAD_COUNT": "客户数",
    "SIGNED_COUNT": "签约数",
    "FOLLOWUP_COUNT": "跟进次数",
    "FOLLOWUP_DUE_COUNT": "到期跟进数",
    "SERVICE_PENDING_COUNT": "待审单数",
    "FEEDBACK_OPEN_COUNT": "未结工单数",
    "APPLICATION_STAGE_COUNT": "进度阶段分布",
    "PSYCH_ALERT_COUNT": "待复核预警数",
}

GROUP_BY = {
    "LEAD_COUNT": {"STATUS", "OWNER", "DEPT"},
    "SIGNED_COUNT": {"OWNER", "DEPT"},
    "FOLLOWUP_COUNT": {"OWNER"},
    "SERVICE_PENDING_COUNT": {"TYPE", "DEPT"},
    "FEEDBACK_OPEN_COUNT": {"STATUS", "PRIORITY", "DEPT"},
    "APPLICATION_STAGE_COUNT": {"STAGE", "ITEM_TYPE"},
    "PSYCH_ALERT_COUNT": {"SEVERITY"},
}

TIME_RANGES = {"TODAY", "THIS_WEEK", "THIS_MONTH", "LAST_MONTH", "THIS_YEAR", "ALL"}

_ADVISOR_ROLES = ("ADVISOR", "SENIOR_ADVISOR", "ADMIN")
_UTC = ZoneInfo("UTC")


# =============================================================
# 时间窗口
# =============================================================
def _bounds(time_range: str) -> tuple[datetime | None, datetime | None, str]:
    tz = ZoneInfo(settings.business_timezone)
    now = datetime.now(tz)
    if time_range == "ALL":
        return None, None, "全部时间"
    if time_range == "TODAY":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        label = "今天"
    elif time_range == "THIS_WEEK":
        start = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0)
        label = "本周"
    elif time_range == "LAST_MONTH":
        first_this = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        start = (first_this - timedelta(days=1)).replace(day=1)
        return start.astimezone(_UTC), first_this.astimezone(_UTC), "上月"
    elif time_range == "THIS_YEAR":
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        label = "今年"
    else:
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        label = "本月"
    return start.astimezone(_UTC), None, label


def _finish(metric: str, *, value=None, items=None, start, end, label,
            warnings: list[str] | None = None) -> dict:
    return {
        "metric": metric,
        "label": METRICS[metric],
        "value": value,
        "items": [{"key": k, "label": lbl, "value": int(v)} for k, lbl, v in (items or [])],
        "range": {
            "label": label,
            "start": start.isoformat() if start else None,
            "end": end.isoformat() if end else None,
        },
        "warnings": warnings or [],
    }


def _count(db: Session, stmt) -> int:
    return int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)


def _grouped(db: Session, stmt, column_name: str) -> list[tuple]:
    sub = stmt.subquery()
    col = sub.c[column_name]
    return list(db.execute(select(col, func.count()).group_by(col)).all())


def _dept_name(db: Session, dept_id) -> str:
    if dept_id is None:
        return "未分配"
    dept = db.get(SysDepartment, int(dept_id))
    return dept.name if dept else "未知部门"


def _user_name(db: Session, user_id) -> str:
    if user_id is None:
        return "未分配"
    user = db.get(SysUser, int(user_id))
    return user.real_name if user else "未知"


def _lead_scope_stmt(db: Session, actor: SysUser):
    scope = build_scope(db, actor, "lead")
    stmt = select(CrmLead)
    if scope.is_admin:
        return stmt
    if scope.dept_ids:
        return stmt.where(or_(CrmLead.dept_id.in_(list(scope.dept_ids)),
                              CrmLead.owner_user_id == actor.id))
    return stmt.where(CrmLead.owner_user_id == actor.id)


# =============================================================
# 指标实现
# =============================================================
def _metric_lead_count(db, actor, *, filters, group_by, start, end, label):
    stmt = _lead_scope_stmt(db, actor)
    if filters.get("status"):
        stmt = stmt.where(CrmLead.status == filters["status"])
    warnings = ["客户数暂不支持按创建时间筛选"] if start is not None else []

    if group_by == "STATUS":
        rows = _grouped(db, stmt, "status")
        return _finish(metric="LEAD_COUNT", items=[(k, k, v) for k, v in rows],
                       start=start, end=end, label=label, warnings=warnings)
    if group_by == "OWNER":
        rows = _grouped(db, stmt, "owner_user_id")
        return _finish(metric="LEAD_COUNT",
                       items=[(str(k) if k else None, _user_name(db, k), v) for k, v in rows],
                       start=start, end=end, label=label, warnings=warnings)
    if group_by == "DEPT":
        rows = _grouped(db, stmt, "dept_id")
        return _finish(metric="LEAD_COUNT",
                       items=[(str(k) if k else None, _dept_name(db, k), v) for k, v in rows],
                       start=start, end=end, label=label, warnings=warnings)
    return _finish(metric="LEAD_COUNT", value=_count(db, stmt),
                   start=start, end=end, label=label, warnings=warnings)


def _metric_signed_count(db, actor, *, filters, group_by, start, end, label):
    stmt = _lead_scope_stmt(db, actor).where(CrmLead.status == "SIGNED")
    if start is not None:
        stmt = stmt.where(CrmLead.signed_at >= start)
    if end is not None:
        stmt = stmt.where(CrmLead.signed_at < end)

    if group_by == "OWNER":
        rows = _grouped(db, stmt, "owner_user_id")
        return _finish(metric="SIGNED_COUNT",
                       items=[(str(k) if k else None, _user_name(db, k), v) for k, v in rows],
                       start=start, end=end, label=label)
    if group_by == "DEPT":
        rows = _grouped(db, stmt, "dept_id")
        return _finish(metric="SIGNED_COUNT",
                       items=[(str(k) if k else None, _dept_name(db, k), v) for k, v in rows],
                       start=start, end=end, label=label)
    return _finish(metric="SIGNED_COUNT", value=_count(db, stmt),
                   start=start, end=end, label=label)


def _metric_followup_count(db, actor, *, filters, group_by, start, end, label):
    lead_stmt = _lead_scope_stmt(db, actor)
    lead_ids = select(lead_stmt.subquery().c.id)
    stmt = select(CrmFollowUp).where(CrmFollowUp.lead_id.in_(lead_ids))
    if start is not None:
        stmt = stmt.where(CrmFollowUp.create_time >= start)
    if end is not None:
        stmt = stmt.where(CrmFollowUp.create_time < end)
    if group_by == "OWNER":
        rows = _grouped(db, stmt, "actor_user_id")
        return _finish(metric="FOLLOWUP_COUNT",
                       items=[(str(k) if k else None, _user_name(db, k), v) for k, v in rows],
                       start=start, end=end, label=label)
    return _finish(metric="FOLLOWUP_COUNT", value=_count(db, stmt),
                   start=start, end=end, label=label)


def _metric_followup_due_count(db, actor, *, filters, group_by, start, end, label):
    now = datetime.now(_UTC)
    stmt = select(CrmLead).where(
        CrmLead.owner_user_id == actor.id,
        CrmLead.next_follow_up_at.isnot(None),
        CrmLead.next_follow_up_at <= now)
    return _finish(metric="FOLLOWUP_DUE_COUNT", value=_count(db, stmt),
                   start=None, end=None, label="当前")


def _metric_service_pending_count(db, actor, *, filters, group_by, start, end, label):
    stmt = select(StudentAdminService).where(StudentAdminService.status == "PENDING")
    if actor.employee_role != "ADMIN":
        head = db.scalar(select(SysDepartment.id).where(
            SysDepartment.head_user_id == actor.id, SysDepartment.id == actor.dept_id))
        if head:
            stmt = stmt.where(or_(StudentAdminService.dept_id == actor.dept_id,
                                  StudentAdminService.assignee_user_id == actor.id))
        else:
            stmt = stmt.where(StudentAdminService.assignee_user_id == actor.id)
    if filters.get("service_type"):
        stmt = stmt.where(StudentAdminService.service_type == filters["service_type"])
    if group_by == "TYPE":
        rows = _grouped(db, stmt, "service_type")
        return _finish(metric="SERVICE_PENDING_COUNT",
                       items=[(k, k, v) for k, v in rows], start=None, end=None, label="当前")
    if group_by == "DEPT":
        rows = _grouped(db, stmt, "dept_id")
        return _finish(metric="SERVICE_PENDING_COUNT",
                       items=[(str(k), _dept_name(db, k), v) for k, v in rows],
                       start=None, end=None, label="当前")
    return _finish(metric="SERVICE_PENDING_COUNT", value=_count(db, stmt),
                   start=None, end=None, label="当前")


def _metric_feedback_open_count(db, actor, *, filters, group_by, start, end, label):
    if not actor.can_handle_feedback:
        raise ForbiddenError("需要售后授权")
    stmt = select(StudentFeedbackTicket).where(
        StudentFeedbackTicket.status.in_(("PENDING", "PROCESSING", "RESOLVED")))
    if actor.employee_role != "ADMIN":
        stmt = stmt.where(StudentFeedbackTicket.dept_id == actor.dept_id)
    if filters.get("category"):
        stmt = stmt.where(StudentFeedbackTicket.category == filters["category"])
    if group_by == "STATUS":
        rows = _grouped(db, stmt, "status")
        return _finish(metric="FEEDBACK_OPEN_COUNT",
                       items=[(k, k, v) for k, v in rows], start=None, end=None, label="当前")
    if group_by == "PRIORITY":
        rows = _grouped(db, stmt, "priority")
        return _finish(metric="FEEDBACK_OPEN_COUNT",
                       items=[(k, k, v) for k, v in rows], start=None, end=None, label="当前")
    if group_by == "DEPT":
        rows = _grouped(db, stmt, "dept_id")
        return _finish(metric="FEEDBACK_OPEN_COUNT",
                       items=[(str(k), _dept_name(db, k), v) for k, v in rows],
                       start=None, end=None, label="当前")
    return _finish(metric="FEEDBACK_OPEN_COUNT", value=_count(db, stmt),
                   start=None, end=None, label="当前")


def _metric_application_stage_count(db, actor, *, filters, group_by, start, end, label):
    ids = visible_student_ids(db, actor)
    stmt = select(StudentApplicationProgress)
    if ids is not None:
        stmt = stmt.where(StudentApplicationProgress.student_profile_id.in_(ids))
    if filters.get("item_type"):
        stmt = stmt.where(StudentApplicationProgress.item_type == filters["item_type"])

    events = list(db.scalars(stmt).all())
    latest: dict = {}
    for e in events:
        if e.case_no not in latest or e.sequence_no > latest[e.case_no].sequence_no:
            latest[e.case_no] = e
    current = list(latest.values())

    if group_by in ("STAGE", "ITEM_TYPE"):
        counts: dict[str, int] = {}
        for e in current:
            key = e.stage if group_by == "STAGE" else e.item_type
            counts[key] = counts.get(key, 0) + 1
        return _finish(metric="APPLICATION_STAGE_COUNT",
                       items=[(k, k, v) for k, v in counts.items()],
                       start=None, end=None, label="当前")
    return _finish(metric="APPLICATION_STAGE_COUNT", value=len(current),
                   start=None, end=None, label="当前")


def _metric_psych_alert_count(db, actor, *, filters, group_by, start, end, label):
    if not actor.psych_access_enabled:
        raise ForbiddenError("需要心理数据授权")
    ids = visible_student_ids(db, actor)
    stmt = select(StudentPsychAlert).where(
        StudentPsychAlert.status.in_(("PENDING_REVIEW", "CONFIRMED", "HANDLING")))
    if ids is not None:
        stmt = stmt.where(StudentPsychAlert.student_profile_id.in_(ids))
    if filters.get("severity"):
        stmt = stmt.where(StudentPsychAlert.severity == filters["severity"])
    if group_by == "SEVERITY":
        rows = _grouped(db, stmt, "severity")
        return _finish(metric="PSYCH_ALERT_COUNT",
                       items=[(k, k, v) for k, v in rows], start=None, end=None, label="当前")
    return _finish(metric="PSYCH_ALERT_COUNT", value=_count(db, stmt),
                   start=None, end=None, label="当前")


# =============================================================
# 入口
# =============================================================
def run_metric(db: Session, actor: SysUser, *, metric: str,
               time_range: str = "THIS_MONTH", filters: dict | None = None,
               group_by: str | None = None) -> dict:
    if metric not in METRICS:
        raise InvalidRequestError("不支持的统计指标")
    if time_range not in TIME_RANGES:
        raise InvalidRequestError("不支持的时间范围")
    if group_by is not None and group_by not in GROUP_BY.get(metric, set()):
        raise InvalidRequestError("不支持的统计维度")
    if actor.employee_role not in _ADVISOR_ROLES:
        raise ForbiddenError("暂无统计权限")

    start, end, label = _bounds(time_range)
    handler = globals().get(f"_metric_{metric.lower()}")
    if handler is None:
        raise InvalidRequestError("指标暂不可用")
    return handler(db, actor, filters=filters or {}, group_by=group_by,
                   start=start, end=end, label=label)
