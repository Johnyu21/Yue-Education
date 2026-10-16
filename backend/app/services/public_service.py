"""
项目与活动业务（API015~API022）—— M2

职责边界：
- 公开查询只返回**已发布项目**与**非草稿活动**；公开 DTO 不含未审内部规则、路由部门与员工信息
- 员工维护项目：创建草稿 → 修改业务字段 → 主管/管理员审核并发布准入规则
- 员工维护活动：创建 → 开放/结束/取消；取消不得把名额降到已报名数之下，并通知已登录报名人

⚠️ 多表/多步写在 with_business_transaction 内；AI 与外部调用不在此层。
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ForbiddenError, NotFoundError, ValidationError, VersionConflictError
from app.core.notification import notify
from app.core.permissions import build_scope
from app.core.transaction import with_business_transaction
from app.models.course_project import CourseProject
from app.models.event import EventLecture, EventRegistration
from app.models.organization import SysDepartment
from app.models.user import SysUser
from app.repositories import event as event_repo
from app.repositories import project as project_repo
from app.schemas.event import EventCreateIn, EventUpdateIn
from app.schemas.project import ProjectCreateIn, ProjectUpdateIn
from app.services.m2_errors import (
    CapacityBelowRegisteredError,
    DuplicateCodeError,
    PeriodInvalidError,
    RuleNotApprovedError,
)

logger = logging.getLogger(__name__)

# 可公开的活动状态（DRAFT 不对外）
PUBLIC_EVENT_STATUS = ("OPEN", "ENDED", "CANCELLED")


# ============================================================
# DTO 归一化（model → camelCase 响应）
# ============================================================
def project_public_out(p: CourseProject) -> dict:
    return {
        "id": str(p.id),
        "code": p.code,
        "name": p.name,
        "country": p.country,
        "educationLevel": p.education_level,
        "description": p.description,
        "admissionRequirements": p.admission_requirements,
        "facultySummary": p.faculty_summary,
        "durationMonths": p.duration_months,
        "feeAmount": str(p.fee_amount) if p.fee_amount is not None else None,
        "feeCurrency": p.fee_currency,
    }


def project_staff_out(p: CourseProject) -> dict:
    data = project_public_out(p)
    data.update({
        "defaultDeptId": str(p.default_dept_id) if p.default_dept_id else None,
        "isPublished": bool(p.is_published),
        "admissionRules": p.admission_rules,
        "ruleVersion": p.rule_version,
        "ruleApprovedAt": p.rule_approved_at,
        "version": p.version,
    })
    return data


def event_out(ev: EventLecture, remaining: int) -> dict:
    return {
        "id": str(ev.id),
        "title": ev.title,
        "description": ev.description,
        "courseProjectId": str(ev.course_project_id) if ev.course_project_id else None,
        "startAt": ev.start_at,
        "endAt": ev.end_at,
        "signupDeadline": ev.signup_deadline,
        "capacity": ev.capacity,
        "remainingCapacity": max(remaining, 0),
        "location": ev.location,
        "status": ev.status,
        "version": ev.version,
    }


# ============================================================
# 权限与校验
# ============================================================
def _scope(db: Session, user: SysUser):
    # purpose 只影响 own_field，这里用不到；需要的是 is_head_of / is_admin
    return build_scope(db, user, "project")


def _require_any_management(scope, what: str) -> None:
    """没有"项目/活动管理"岗位能力 → 403（能力判断可返回 403）。"""
    if not (scope.is_admin or scope.is_head_of):
        raise ForbiddenError(f"没有{what}管理权限")


def _project_visible(scope, project: CourseProject) -> bool:
    if scope.is_admin:
        return True
    return project.default_dept_id is not None and project.default_dept_id in scope.is_head_of


def _event_visible(scope, ev: EventLecture) -> bool:
    if scope.is_admin:
        return True
    return ev.host_department_id is not None and ev.host_department_id in scope.is_head_of


def _validate_fee_pair(amount, currency) -> None:
    """DDL 约束：参考费用与币种必须同时有或同时无。"""
    if (amount is None) != (currency is None):
        field = "fee_currency" if currency is None else "fee_amount"
        raise ValidationError(
            "参考费用与币种必须同时提供或同时留空",
            errors=[{"field": field, "reason": "需与另一项同时提供或同时留空"}],
        )


def _validate_event_period(start_at: datetime, end_at: datetime,
                           signup_deadline: datetime) -> None:
    """DDL 约束：end_at > start_at 且 signup_deadline <= start_at。"""
    if end_at <= start_at:
        raise PeriodInvalidError("结束时间必须晚于开始时间",
                                 errors=[{"field": "end_at", "reason": "必须晚于 start_at"}])
    if signup_deadline > start_at:
        raise PeriodInvalidError("报名截止时间不得晚于活动开始时间",
                                 errors=[{"field": "signup_deadline",
                                          "reason": "必须不晚于 start_at"}])


def _require_dept_exists(db: Session, dept_id: int | None, field: str) -> None:
    if dept_id is None:
        return
    if db.get(SysDepartment, dept_id) is None:
        raise ValidationError("部门不存在", errors=[{"field": field, "reason": "部门不存在"}])


# ============================================================
# API015 / API016 —— 公开项目
# ============================================================
def list_public_projects(db: Session, *, page: int, page_size: int,
                         country: str | None = None, keyword: str | None = None):
    items, total = project_repo.list_public(
        db, page=page, page_size=page_size, country=country, keyword=keyword)
    return [project_public_out(p) for p in items], total


def get_public_project(db: Session, project_id: int) -> dict:
    p = project_repo.get_by_id(db, project_id)
    if p is None or not p.is_published:
        # 未发布项目对外一律 404，不暴露草稿存在性
        raise NotFoundError("资源不存在")
    return project_public_out(p)


# ============================================================
# API017 / API018 —— 员工维护项目
# ============================================================
def create_project(db: Session, user: SysUser, data: ProjectCreateIn) -> dict:
    scope = _scope(db, user)
    _require_any_management(scope, "项目")
    _validate_fee_pair(data.fee_amount, data.fee_currency)

    with with_business_transaction(db):
        if project_repo.get_by_code(db, data.code) is not None:
            raise DuplicateCodeError("项目编码已存在")
        _require_dept_exists(db, data.default_dept_id, "default_dept_id")

        project = CourseProject(
            code=data.code,
            name=data.name,
            description=data.description,
            country=data.country,
            education_level=data.education_level,
            admission_requirements=data.admission_requirements,
            faculty_summary=data.faculty_summary,
            duration_months=data.duration_months,
            fee_amount=data.fee_amount,
            fee_currency=data.fee_currency,
            default_dept_id=data.default_dept_id,
            is_published=False,        # 新建一律草稿
            version=1,
        )
        db.add(project)
        db.flush()
        out = project_staff_out(project)

    logger.info("M2 创建项目草稿 actor=%s project=%s", user.id, out["id"])
    return out


def update_project(db: Session, user: SysUser, project_id: int,
                   data: ProjectUpdateIn) -> dict:
    scope = _scope(db, user)
    _require_any_management(scope, "项目")
    provided = data.model_fields_set

    with with_business_transaction(db):
        project = project_repo.get_by_id(db, project_id)
        if project is None or not _project_visible(scope, project):
            raise NotFoundError("资源不存在")
        if project.version != data.expected_version:
            raise VersionConflictError(project.version)

        # ---- 业务字段（只写白名单；用 model_fields_set 判断是否显式提供）----
        for field, attr in (
            ("name", "name"),
            ("description", "description"),
            ("country", "country"),
            ("education_level", "education_level"),
            ("admission_requirements", "admission_requirements"),
            ("faculty_summary", "faculty_summary"),
            ("duration_months", "duration_months"),
            ("default_dept_id", "default_dept_id"),
            ("rule_version", "rule_version"),
        ):
            if field in provided:
                setattr(project, attr, getattr(data, field))
        if "default_dept_id" in provided:
            _require_dept_exists(db, data.default_dept_id, "default_dept_id")

        # 费用与币种：要按"改完之后"的状态整体校验
        new_amount = data.fee_amount if "fee_amount" in provided else project.fee_amount
        new_currency = data.fee_currency if "fee_currency" in provided else project.fee_currency
        _validate_fee_pair(new_amount, new_currency)
        project.fee_amount = new_amount
        project.fee_currency = new_currency

        # ---- 准入规则与审核 ----
        if "admission_rules" in provided:
            project.admission_rules = data.admission_rules
            if not data.approve_rules:
                # 规则变更未经复审 → 撤回原审核（未审规则不作自动判定）
                project.rule_approved_at = None
                project.rule_approved_by = None

        if data.approve_rules:
            if not project.admission_rules:
                raise RuleNotApprovedError("缺少结构化准入条件，无法审核通过")
            project.rule_approved_at = datetime.now(timezone.utc)
            project.rule_approved_by = user.id

        if "is_published" in provided and data.is_published is not None:
            project.is_published = data.is_published

        project.version += 1
        db.flush()
        out = project_staff_out(project)

    logger.info("M2 更新项目 actor=%s project=%s version=%s",
                user.id, project_id, out["version"])
    return out


# ============================================================
# API019 / API020 —— 公开活动
# ============================================================
def list_public_events(db: Session, *, page: int, page_size: int,
                       status: str = "OPEN"):
    items, total = event_repo.list_by_status(db, status=status,
                                             page=page, page_size=page_size)
    counts = event_repo.count_active_map(db, [e.id for e in items])
    return [event_out(e, e.capacity - counts.get(e.id, 0)) for e in items], total


def get_public_event(db: Session, event_id: int) -> dict:
    ev = event_repo.get_by_id(db, event_id)
    if ev is None or ev.status not in PUBLIC_EVENT_STATUS:
        raise NotFoundError("资源不存在")
    used = event_repo.count_active_registrations(db, ev.id)
    return event_out(ev, ev.capacity - used)


# ============================================================
# API021 / API022 —— 员工维护活动
# ============================================================
def create_event(db: Session, user: SysUser, data: EventCreateIn) -> dict:
    scope = _scope(db, user)
    _require_any_management(scope, "活动")
    if not (scope.is_admin or data.host_department_id in scope.is_head_of):
        raise ForbiddenError("只能为本人主管的部门创建活动")
    _validate_event_period(data.start_at, data.end_at, data.signup_deadline)
    _require_dept_exists(db, data.host_department_id, "host_department_id")

    with with_business_transaction(db):
        ev = EventLecture(
            title=data.title,
            description=data.description,
            organizer_user_id=data.organizer_user_id,
            host_department_id=data.host_department_id,
            course_project_id=data.course_project_id,
            start_at=data.start_at,
            end_at=data.end_at,
            signup_deadline=data.signup_deadline,
            capacity=data.capacity,
            location=data.location,
            status="DRAFT",           # 新建一律草稿，须显式开放
            version=1,
        )
        db.add(ev)
        db.flush()
        out = event_out(ev, ev.capacity)

    logger.info("M2 创建活动草稿 actor=%s event=%s", user.id, out["id"])
    return out


def update_event(db: Session, user: SysUser, event_id: int, data: EventUpdateIn) -> dict:
    scope = _scope(db, user)
    _require_any_management(scope, "活动")
    provided = data.model_fields_set

    with with_business_transaction(db):
        # 锁活动行：与报名/取消共用同一锁序，避免并发改名额
        ev = event_repo.lock_by_id(db, event_id)
        if ev is None or not _event_visible(scope, ev):
            raise NotFoundError("资源不存在")
        if ev.version != data.expected_version:
            raise VersionConflictError(ev.version)

        for field in ("title", "description", "course_project_id",
                      "host_department_id", "organizer_user_id", "location"):
            if field in provided:
                setattr(ev, field, getattr(data, field))

        # 时间区间：按"改完之后"整体校验
        start_at = data.start_at if "start_at" in provided else ev.start_at
        end_at = data.end_at if "end_at" in provided else ev.end_at
        deadline = data.signup_deadline if "signup_deadline" in provided else ev.signup_deadline
        _validate_event_period(start_at, end_at, deadline)
        ev.start_at, ev.end_at, ev.signup_deadline = start_at, end_at, deadline

        # 名额不得降到已报名数之下
        if "capacity" in provided and data.capacity is not None:
            used = event_repo.count_active_registrations(db, ev.id)
            if data.capacity < used:
                raise CapacityBelowRegisteredError(
                    f"名额不能小于已报名人数（当前占用 {used}）",
                    data={"registered": used},
                )
            ev.capacity = data.capacity

        status_before = ev.status
        if data.status is not None:
            ev.status = data.status

        ev.version += 1

        # ---- 取消活动：通知已登录报名人（同事务）----
        if data.status == "CANCELLED" and status_before != "CANCELLED":
            _notify_registrants_cancelled(db, ev)

        db.flush()
        used = event_repo.count_active_registrations(db, ev.id)
        out = event_out(ev, ev.capacity - used)

    logger.info("M2 更新活动 actor=%s event=%s status=%s",
                user.id, event_id, out["status"])
    return out


def _notify_registrants_cancelled(db: Session, ev: EventLecture) -> None:
    """只通知有站内账号的学生报名人；访客无消息账号，不宣称推送到达。"""
    student_ids = db.scalars(
        select(EventRegistration.student_profile_id).where(
            EventRegistration.event_id == ev.id,
            EventRegistration.status.in_(("REGISTERED", "CHECKED_IN")),
            EventRegistration.student_profile_id.isnot(None),
        )
    ).all()
    if not student_ids:
        return

    from app.models.student import StudentProfile      # 局部导入避免循环

    user_ids = db.scalars(
        select(StudentProfile.user_id).where(StudentProfile.id.in_(list(student_ids)))
    ).all()
    if not user_ids:
        return

    notify(
        db,
        f"event:{ev.id}:cancelled:v{ev.version}",
        list(user_ids),
        category="SYSTEM",                              # 白名单内；取消无独立类别
        title="活动已取消",
        content=f"「{ev.title}」已取消，如有疑问请联系顾问。",
        related_type="event",
        related_id=ev.id,
    )
