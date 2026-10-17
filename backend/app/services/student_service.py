"""
学生档案概览 + 行政服务（请假/考务/信息修改）业务

含导出的 M3 Interface：decide_service / assign_service。
写操作在同一事务内完成校验、状态、通知（事务边界在 controller）。
"""
from app.core.idempotency import idempotent
from app.services import m3_canonical
import logging
from datetime import date, datetime, timezone
from app.core.mobile import normalize_mobile
from uuid import UUID

from sqlalchemy import select, text
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
from app.models.admin_service import StudentAdminService
from app.models.organization import SysClass, SysDepartment
from app.models.student import StudentProfile
from app.models.user import SysUser
from app.repositories import student_repo
from app.repositories import service_repo
from app.repositories.common import my_profile_id
from app.schemas.service import ServiceCreateRequest, ServiceDecisionRequest, ServiceDTO
from app.schemas.student import (
    StudentAdvisorBrief,
    StudentClassBrief,
    StudentEnrollmentItem,
    StudentSelfDTO,
    StudentUserBrief,
)

logger = logging.getLogger(__name__)

# INFO_CHANGE 白名单字段 → 所在实体
_INFO_CHANGE_STUDENT_FIELDS = {"gender", "city", "education", "date_of_birth"}
_IDENTITY_FIELDS = {"real_name", "mobile"}   # 需 identity_verification 才可批准


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def canonical_service_payload(req: ServiceCreateRequest) -> dict:
    """确认令牌的内容指纹来源：与提交时完全一致（时间为 ISO 字符串）。"""
    return {
        "service_type": req.service_type,
        "title": req.title,
        "description": req.description,
        "start_at": _iso(req.start_at),
        "end_at": _iso(req.end_at),
        "change_request": req.change_request.model_dump() if req.change_request else None,
    }


# =============================================================
# 学生概览（API046）
# =============================================================
def get_self_overview(db: Session, user: SysUser) -> StudentSelfDTO:
    profile = student_repo.get_profile_by_user(db, user.id)
    if profile is None:
        raise NotFoundError("学生档案不存在")

    cls: SysClass | None = db.get(SysClass, profile.class_id) if profile.class_id else None
    head: SysUser | None = db.get(SysUser, cls.head_teacher_id) if cls and cls.head_teacher_id else None
    advisor: SysUser | None = db.get(SysUser, profile.advisor_user_id) if profile.advisor_user_id else None

    # M1 的 SysClass 模型未映射 is_active/version，这里补查（不改 M1 模型）
    cls_is_active, cls_version = True, 1
    if cls is not None:
        row = db.execute(text("SELECT is_active, version FROM sys_class WHERE id=:id"),
                         {"id": cls.id}).mappings().first()
        if row:
            cls_is_active, cls_version = row["is_active"], row["version"]

    enrollments = student_repo.list_enrollments(db, profile.id)
    names = student_repo.get_project_names(db, [e.course_project_id for e in enrollments])

    return StudentSelfDTO(
        id=str(profile.id),
        user=StudentUserBrief(id=str(user.id), realName=user.real_name, mobile=user.username),
        gender=profile.gender,
        city=profile.city,
        education=profile.education,
        dateOfBirth=profile.date_of_birth,
        enrollmentDate=profile.enrollment_date,
        status=profile.status,
        classInfo=StudentClassBrief(
            id=str(cls.id), code=cls.code, name=cls.name, courseType=cls.course_type,
            deptId=str(cls.dept_id),
            headTeacher={"id": str(head.id), "realName": head.real_name} if head else None,
            isActive=cls_is_active, version=cls_version,
        ) if cls else None,
        advisor=StudentAdvisorBrief(
            id=str(advisor.id), realName=advisor.real_name,
            contactInfo=advisor.contact_info,
        ) if advisor else None,
        enrollments=[
            StudentEnrollmentItem(
                id=str(e.id), courseProjectId=str(e.course_project_id),
                projectName=names.get(e.course_project_id, ""), status=e.status,
            ) for e in enrollments
        ],
        version=profile.version,
    )


# =============================================================
# 行政服务（API050-053 + M3 Interface API054/055）
# =============================================================
def _service_to_dto(db: Session, svc: StudentAdminService) -> ServiceDTO:
    stu = db.get(SysUser, svc.submitted_by_user_id)
    assignee = db.get(SysUser, svc.assignee_user_id) if svc.assignee_user_id else None
    return ServiceDTO(
        id=str(svc.id),
        studentProfileId=str(svc.student_profile_id),
        studentDisplayName=stu.real_name if stu else "",
        serviceType=svc.service_type,
        title=svc.title,
        description=svc.description,
        startAt=svc.start_at,
        endAt=svc.end_at,
        changeRequest=svc.change_request,
        assigneeDisplayName=assignee.real_name if assignee else None,
        status=svc.status,
        decisionNote=svc.decision_note,
        decidedAt=svc.decided_at,
        createTime=svc.create_time,
        version=svc.version,
    )


def _resolve_assignee(db: Session, profile: StudentProfile, service_type: str) -> SysUser:
    """按类型确定审批人：LEAVE/EXAM→班主任，INFO_CHANGE→个人顾问，OTHER→部门主管。"""
    if service_type in ("LEAVE", "EXAM"):
        cls = db.get(SysClass, profile.class_id) if profile.class_id else None
        assignee_id = cls.head_teacher_id if cls else None
    elif service_type == "INFO_CHANGE":
        assignee_id = profile.advisor_user_id
    else:
        dept = db.get(SysDepartment, profile.dept_id)
        assignee_id = dept.head_user_id if dept else None

    if not assignee_id:
        raise InvalidRequestError("暂无可用处理人，请联系管理员")
    assignee = db.get(SysUser, assignee_id)
    if assignee is None or assignee.status != "NORMAL":
        raise InvalidRequestError("暂无可用处理人，请联系管理员")
    return assignee


def _check_leave_overlap(db: Session, profile_id: int, start_at: datetime, end_at: datetime,
                         exclude_id: int | None = None) -> None:
    """请假重叠检测（在 student_profile 行锁内）：与 PENDING/APPROVED 的 LEAVE 不重叠。"""
    stmt = select(StudentAdminService).where(
        StudentAdminService.student_profile_id == profile_id,
        StudentAdminService.service_type == "LEAVE",
        StudentAdminService.status.in_(("PENDING", "APPROVED")),
        StudentAdminService.start_at < end_at,
        StudentAdminService.end_at > start_at,
    )
    if exclude_id is not None:
        stmt = stmt.where(StudentAdminService.id != exclude_id)
    if db.scalar(select(stmt.exists())):
        raise StateConflictError("请假时间与已有申请重叠")


@idempotent("student_service.submit_service")
def submit_service(db: Session, user: SysUser, req: ServiceCreateRequest) -> dict:
    """API052 学生确认提交行政服务。"""
    profile = student_repo.get_profile_by_user(db, user.id)
    if profile is None:
        raise NotFoundError("学生档案不存在")

    if not req.confirmed:
        raise InvalidRequestError("请确认后再提交")

    # 幂等：同一 request_key 直接返回既有结果
    existing = service_repo.get_service_by_request_key(db, req.request_key)
    if existing is not None:
        if existing.submitted_by_user_id != user.id:
            raise NotFoundError("资源不存在")
        if any(getattr(existing,k) != v for k,v in canonical_service_payload(req).items() if k not in {"start_at","end_at"}) or _iso(existing.start_at) != _iso(req.start_at) or _iso(existing.end_at) != _iso(req.end_at):
            raise StateConflictError("请求键已被其他内容使用")
        return {"id": str(existing.id), "status": existing.status,
                "assignee_display_name": _service_to_dto(db, existing).assigneeDisplayName,
                "version": existing.version}

    # AI 提议确认凭据
    if req.confirmation_token:
        verify_confirmation(
            user, req.confirmation_token, operation="SUBMIT_SERVICE",
            entity_id=None, payload=canonical_service_payload(req),
         request_key=req.request_key)

    profile = db.get(StudentProfile, profile.id, with_for_update=True, populate_existing=True)
    # 校验
    if req.service_type == "LEAVE":
        if not req.start_at or not req.end_at or req.end_at <= req.start_at:
            raise InvalidRequestError("请假必须填写开始与结束时间，且结束晚于开始")
        _check_leave_overlap(db, profile.id, req.start_at, req.end_at)
    if req.service_type == "INFO_CHANGE" and not req.change_request:
        raise InvalidRequestError("信息修改必须提供新旧值")

    if req.service_type=="INFO_CHANGE":
        change=req.change_request
        allowed=_INFO_CHANGE_STUDENT_FIELDS | _IDENTITY_FIELDS
        if not change.new_values or not set(change.new_values)<=allowed or set(change.old_values)!=set(change.new_values):raise InvalidRequestError("新旧字段必须一致，且仅能修改允许的资料字段")
        for field,value in change.new_values.items():
            if field=="date_of_birth":
                try:
                    if value is not None and date.fromisoformat(value)>date.today():raise ValueError()
                except (ValueError,TypeError):raise InvalidRequestError("出生日期必须为有效的YYYY-MM-DD且不晚于今天")
            elif value is not None and (not isinstance(value,str) or not value.strip() or len(value)>160):raise InvalidRequestError("资料字段必须为有效文本")
            if field in _IDENTITY_FIELDS and (not isinstance(value,str) or not value.strip()):raise InvalidRequestError("身份字段不能为空")
            if field=="mobile" and normalize_mobile(value)!=value:raise InvalidRequestError("手机号须为规范格式")
    # 锁定学生主行（重叠检测 + 并发）

    assignee = _resolve_assignee(db, profile, req.service_type)

    svc = StudentAdminService(
        student_profile_id=profile.id,
        dept_id=profile.dept_id,
        service_type=req.service_type,
        title=req.title,
        description=req.description,
        start_at=req.start_at,
        end_at=req.end_at,
        change_request=req.change_request.model_dump() if req.change_request else None,
        submitted_by_user_id=user.id,
        assignee_user_id=assignee.id,
        status="PENDING",
        handling_history=[],
        request_key=req.request_key,
        version=1,
    )
    db.add(svc)
    db.flush()

    notify(db, f"service:{svc.id}:submitted:1", [assignee.id],
           category="SERVICE_SUBMITTED",
           title=f"新申请：{req.title}",
           content=f"学生提交了「{req.title}」，请处理",
           related_type="admin_service", related_id=svc.id)

    return {"id": str(svc.id), "status": svc.status,
            "assignee_display_name": assignee.real_name, "version": svc.version}


@idempotent("student_service.cancel_service")
def cancel_service(db: Session, user: SysUser, service_id: int, *,
                   expected_version: int, request_key: UUID, reason: str) -> dict:
    """API053 学生取消待审单（仅本人 PENDING）。"""
    profile_id = my_profile_id(db, user)
    svc = service_repo.get_service(db, service_id)
    if svc is None or svc.student_profile_id != profile_id:
        raise NotFoundError("资源不存在")
    if svc.version != expected_version:
        raise VersionConflictError(svc.version)
    if svc.status != "PENDING":
        raise StateConflictError("仅待审批的申请可撤销")

    history = list(svc.handling_history or [])
    history.append({"action": "CANCELLED", "actor": str(user.id), "at": _iso(datetime.now(timezone.utc)),
                    "note": reason, "request_key": str(request_key)})
    svc.status = "CANCELLED"
    svc.handling_history = history
    svc.version += 1
    db.flush()
    return {"id": str(svc.id), "status": svc.status, "version": svc.version}


def list_services(db: Session, user: SysUser, *, status: str | None = None,
                  service_type: str | None = None, page: int = 1, page_size: int = 20):
    items, total = service_repo.list_services(
        db, user, status=status, service_type=service_type, page=page, page_size=page_size)
    return [_service_to_dto(db, s) for s in items], total


def get_service(db: Session, user: SysUser, service_id: int) -> ServiceDTO:
    svc = service_repo.get_service(db, service_id)
    if svc is None:
        raise NotFoundError("资源不存在")

    if user.is_student:
        if svc.student_profile_id != my_profile_id(db, user):
            raise NotFoundError("资源不存在")
    elif user.employee_role == "ADMIN":
        pass
    else:
        from app.repositories.common import visible_student_ids
        ids = visible_student_ids(db, user)
        if svc.assignee_user_id != user.id and (ids is None or svc.student_profile_id not in ids):
            raise NotFoundError("资源不存在")
    return _service_to_dto(db, svc)


def _check_decider_permission(db: Session, actor: SysUser, svc: StudentAdminService) -> None:
    if actor.id == svc.assignee_user_id:
        return
    if actor.employee_role == "ADMIN":
        return
    # 主管部门可代办
    head_of = db.scalar(select(SysDepartment.id).where(
        SysDepartment.head_user_id == actor.id, SysDepartment.id == svc.dept_id))
    if head_of is not None:
        return
    raise ForbiddenError("无权处理该申请")


@idempotent("student_service.decide_service")
def decide_service(db: Session, actor: SysUser, service_id: int,
                   req: ServiceDecisionRequest) -> ServiceDTO:
    """API054 员工审批（M3 控制器复用此业务函数）。

    ⚠️ INFO_CHANGE 批准时同时校验旧值并应用白名单字段，结果通知同事务。
    """
    svc = service_repo.get_service(db, service_id)
    if svc is None:
        raise NotFoundError("资源不存在")
    if svc.status != "PENDING":
        raise StateConflictError("该申请已处理")
    if svc.version != req.expected_version:
        raise VersionConflictError(svc.version)
    _check_decider_permission(db, actor, svc)

    if req.confirmation_token:
        verify_confirmation(actor, req.confirmation_token, operation="DECIDE_SERVICE",
                            entity_id=service_id,
                            payload=m3_canonical.decide_service_payload(req.decision,req.note,req.identity_verification),
                            expected_version=req.expected_version, request_key=req.request_key)

    now = datetime.now(timezone.utc)
    if req.decision == "APPROVE" and svc.service_type == "INFO_CHANGE":
        _apply_info_change(db, svc, req)

    history = list(svc.handling_history or [])
    history.append({"action": req.decision, "actor": str(actor.id), "at": _iso(now),
                    "note": req.note, "request_key": str(req.request_key)})
    svc.status = "APPROVED" if req.decision == "APPROVE" else "REJECTED"
    svc.decision_note = req.note
    svc.decided_at = now
    svc.handling_history = history
    svc.version += 1
    db.flush()

    notify(db, f"service:{svc.id}:decision:{svc.version}", [svc.submitted_by_user_id],
           category="SERVICE_DECISION",
           title="申请已通过" if req.decision == "APPROVE" else "申请被驳回",
           content=f"您的「{svc.title}」{'已通过' if req.decision == 'APPROVE' else '被驳回'}：{req.note}",
           related_type="admin_service", related_id=svc.id)

    return _service_to_dto(db, svc)


def _apply_info_change(db: Session, svc: StudentAdminService, req: ServiceDecisionRequest) -> None:
    """INFO_CHANGE 批准：比对旧值仍一致后更新白名单字段；身份字段需核验。"""
    cr = svc.change_request or {}
    old = cr.get("old_values") or {}
    new = cr.get("new_values") or {}

    profile = db.get(StudentProfile, svc.student_profile_id)
    user = db.get(SysUser, svc.submitted_by_user_id)

    for field, new_val in new.items():
        if field in _IDENTITY_FIELDS and (not req.identity_verification or field not in req.identity_verification.verified_fields):
            raise InvalidRequestError(f"字段 {field} 属于身份信息，需人工核验后才能批准")

        if field in _INFO_CHANGE_STUDENT_FIELDS:
            current = getattr(profile, field)
            if old.get(field) != (current.isoformat() if isinstance(current,date) else current):
                raise StateConflictError(f"字段 {field} 原值已变更，请刷新后处理")
            setattr(profile, field, date.fromisoformat(new_val) if field=="date_of_birth" and new_val is not None else new_val)
        elif field == "real_name":
            if old.get(field) != user.real_name:
                raise StateConflictError("姓名原值已变更，请刷新后处理")
            user.real_name = new_val
        elif field == "mobile":
            if old.get(field) != user.username:
                raise StateConflictError("手机号原值已变更，请刷新后处理")
            if db.scalar(select(SysUser.id).where(SysUser.username == new_val,
                                                  SysUser.id != user.id)):
                raise StateConflictError("该手机号已被占用")
            user.username = new_val
            user.token_version += 1          # 变更登录身份，撤销旧会话


@idempotent("student_service.assign_service")
def assign_service(db: Session, actor: SysUser, service_id: int, *,
                   assignee_user_id: int, expected_version: int,
                   reason: str, request_key: UUID) -> ServiceDTO:
    """API055 主管转派待审单（M3 控制器复用）。"""
    svc = service_repo.get_service(db, service_id)
    if svc is None:
        raise NotFoundError("资源不存在")
    if svc.status != "PENDING":
        raise StateConflictError("仅待审批可转派")
    if svc.version != expected_version:
        raise VersionConflictError(svc.version)

    if actor.employee_role != "ADMIN":
        head_of = db.scalar(select(SysDepartment.id).where(
            SysDepartment.head_user_id == actor.id, SysDepartment.id == svc.dept_id))
        if head_of is None:
            raise ForbiddenError("无权转派")

    new_assignee = db.get(SysUser, assignee_user_id)
    if new_assignee is None or not new_assignee.is_employee or new_assignee.status != "NORMAL" or new_assignee.dept_id != svc.dept_id:
        raise InvalidRequestError("转派目标无效")

    history = list(svc.handling_history or [])
    history.append({"action": "ASSIGN", "actor": str(actor.id), "at": _iso(datetime.now(timezone.utc)),
                    "note": reason, "request_key": str(request_key),
                    "assignee_from": svc.assignee_user_id, "assignee_to": assignee_user_id})
    svc.assignee_user_id = assignee_user_id
    svc.handling_history = history
    svc.version += 1
    db.flush()

    notify(db, f"service:{svc.id}:assign:{svc.version}", [assignee_user_id],
           category="SERVICE_SUBMITTED", title=f"转派申请：{svc.title}",
           content=f"一条申请转派给您处理", related_type="admin_service", related_id=svc.id)

    return _service_to_dto(db, svc)
