"""
M3 CRM 闭环 —— 线索列表/详情/建客户/补充资料/认领/转派/跟进/状态流转/转学生

设计要点（对齐 04 API 契约与 M3 模块文档）：
  1. 复用 M2 的 lead_service.acquire_lead：手机号规范化、一人一档、完整度、部门路由、ACQUIRED 跟进幂等。
  2. 范围：build_scope(db, user, "lead")；顾问仅本人，主管本部门，管理员全域；
     未路由（dept_id 为空）客户只有管理员可见（待分配池）。
  3. 认领用条件更新（owner IS NULL + version）保证并发只有一人成功。
  4. SIGNED 只能由转化入口设置；流失必须写原因。
  5. 转学生在一个事务内完成：账号 + 档案 + 课程关联 + SIGNED + 跟进 + 通知；
     临时密码只在首次成功响应出现一次，不写日志。
  6. 本模块函数只 flush，不 commit（事务边界在 controller 的 with_business_transaction）。
"""
from app.core.idempotency import idempotent
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.confirmation import verify_confirmation
from app.core.errors import (
    ForbiddenError,
    InvalidRequestError,
    NotFoundError,
    VersionConflictError,
)
from app.core.mobile import mask_mobile, normalize_mobile
from app.core.notification import notify
from app.core.permissions import build_scope
from app.core.security import generate_temp_password, hash_password
from app.models.course_project import CourseProject
from app.models.enrollment import StudentCourseEnrollment
from app.models.follow_up import CrmFollowUp
from app.models.lead import CrmLead
from app.models.organization import SysClass, SysDepartment
from app.models.student import StudentProfile
from app.models.user import SysUser
from app.repositories import lead as lead_repo
from app.schemas.lead import (
    ConversionIn,
    FollowUpIn,
    FollowUpOut,
    LeadManualIn,
    LeadStaffOut,
    LeadSummaryOut,
    LeadTransitionIn,
    LeadUpdateIn,
)
from app.services import lead_service, m3_canonical
from app.services.m3_errors import (
    AlreadyConvertedError,
    ClassTeacherRequiredError,
    DepartmentMismatchError,
    LeadAlreadyClaimedError,
    LeadExistsOutOfScopeError,
    MobileConflictError,
    StateTransitionDeniedError,
    UsernameConflictError,
)

logger = logging.getLogger(__name__)

_ADVISOR_ROLES = ("ADVISOR", "SENIOR_ADVISOR")
_TEMP_PASSWORD_DAYS = 7


# =============================================================
# 权限与范围辅助
# =============================================================
def _require_lead_read(actor: SysUser) -> None:
    """客户读取：新人无客户权限；顾问/高级顾问/主管/管理员可读。"""
    if actor.employee_role not in (*_ADVISOR_ROLES, "ADMIN"):
        raise ForbiddenError("暂无客户数据权限")


def _require_lead_write(actor: SysUser) -> None:
    """客户写：与读取同一岗位基线（新人默认无客户写权限）。"""
    _require_lead_read(actor)


def _head_dept_ids(db: Session, actor: SysUser) -> list[int]:
    """我是主管的部门（唯一事实源 sys_department.head_user_id）。"""
    return list(db.scalars(select(SysDepartment.id).where(
        SysDepartment.head_user_id == actor.id)))


def _is_head_of(db: Session, actor: SysUser, dept_id: int | None) -> bool:
    if dept_id is None:
        return False
    return db.scalar(select(SysDepartment.id).where(
        SysDepartment.id == dept_id,
        SysDepartment.head_user_id == actor.id)) is not None


def _can_view_lead(db: Session, actor: SysUser, lead: CrmLead) -> bool:
    """客户详情可见性：本人 / 主管部门 / 管理员 / 待分配客户（未路由或本部门）。"""
    if actor.employee_role == "ADMIN":
        return True
    if lead.owner_user_id is not None and lead.owner_user_id == actor.id:
        return True
    if _is_head_of(db, actor, lead.dept_id):
        return True
    # 待分配客户（未路由 ∪ 本部门）对顾问可见，便于抢单认领
    if lead.owner_user_id is None:
        return lead.dept_id is None or lead.dept_id == actor.dept_id
    return False


def _get_lead_in_scope(db: Session, actor: SysUser, lead_id: int) -> CrmLead:
    """按 id 取客户；范围外一律 404（防探测）。"""
    lead = db.get(CrmLead, lead_id)
    if lead is None or not _can_view_lead(db, actor, lead):
        raise NotFoundError("资源不存在")
    return lead


def _can_claim_lead(db: Session, actor: SysUser, lead: CrmLead) -> bool:
    """可认领：本部门公共池 + 未路由池；管理员可认领任意池。"""
    if lead.owner_user_id is not None:
        return False
    if actor.employee_role == "ADMIN":
        return True
    if lead.dept_id is None:
        return True
    return lead.dept_id == actor.dept_id


# =============================================================
# DTO 组装
# =============================================================
def _display_name(db: Session, user_id: int | None) -> str | None:
    if user_id is None:
        return None
    user = db.get(SysUser, user_id)
    return user.real_name if user else None


def _to_summary(db: Session, lead: CrmLead) -> LeadSummaryOut:
    return LeadSummaryOut(
        id=str(lead.id),
        name=lead.name or "",
        mobileMasked=mask_mobile(lead.mobile),
        education=lead.education,
        intendedProjectId=str(lead.intended_project_id) if lead.intended_project_id else None,
        status=lead.status,
        ownerDisplayName=_display_name(db, lead.owner_user_id),
        latestScore=lead.latest_score,
        profileCompleteness=lead.profile_completeness or "MINIMAL",
        nextFollowUpAt=lead.next_follow_up_at,
        version=lead.version,
    )


def _to_staff(db: Session, lead: CrmLead) -> LeadStaffOut:
    summary = _to_summary(db, lead).model_dump()
    return LeadStaffOut(
        **summary,
        mobile=lead.mobile,
        gender=lead.gender,
        city=lead.city,
        dateOfBirth=lead.date_of_birth,
        studyPurpose=lead.study_purpose,
        interestLevel=lead.interest_level,
        deptId=str(lead.dept_id) if lead.dept_id else None,
        profileSummary=lead.profile_summary,
        assessmentStatus=lead.assessment_status or "NONE",
        assessmentStartedAt=lead.assessment_started_at,
        assessmentErrorCode=lead.assessment_error_code,
        assessedAt=lead.assessed_at,
        contractRef=lead.contract_ref,
        contractAmount=str(lead.contract_amount) if lead.contract_amount is not None else None,
        contractCurrency=lead.contract_currency,
    )


def _to_follow_up(db: Session, fu: CrmFollowUp) -> FollowUpOut:
    return FollowUpOut(
        id=str(fu.id),
        actorDisplayName=_display_name(db, fu.actor_user_id),
        followUpType=fu.follow_up_type,
        content=fu.content,
        statusBefore=fu.status_before,
        statusAfter=fu.status_after,
        nextFollowUpAt=fu.next_follow_up_at,
        createTime=fu.create_time,
        details=fu.details,
    )


def _recompute_completeness(lead: CrmLead) -> None:
    complete = bool(lead.name) and bool(lead.mobile) and all(
        getattr(lead, f, None) for f in ("gender", "city", "education"))
    lead.profile_completeness = "COMPLETE" if complete else "MINIMAL"


def _add_follow_up(db: Session, lead: CrmLead, actor_id: int | None, *,
                   follow_up_type: str, content: str, request_key,
                   status_before: str | None = None, status_after: str | None = None,
                   next_follow_up_at=None, details: dict | None = None) -> CrmFollowUp:
    fu = CrmFollowUp(
        lead_id=lead.id,
        actor_user_id=actor_id,
        follow_up_type=follow_up_type,
        content=content,
        status_before=status_before if status_before is not None else lead.status,
        status_after=status_after if status_after is not None else lead.status,
        next_follow_up_at=next_follow_up_at,
        details=details,
        request_key=request_key,
    )
    db.add(fu)
    db.flush()
    return fu


# =============================================================
# API032 列表
# =============================================================
def list_leads(db: Session, actor: SysUser, *, view: str = "mine",
               keyword: str | None = None, status: str | None = None,
               project_id: int | None = None, dept_id: int | None = None,
               sort: str = "created_desc", page: int = 1, page_size: int = 20):
    _require_lead_read(actor)
    is_admin = actor.employee_role == "ADMIN"
    is_head = bool(_head_dept_ids(db, actor))

    if view == "pool":
        if is_admin:
            items, total = lead_repo.list_leads(
                db, pool_only=True, dept_id=None, keyword=keyword,
                status=status, project_id=project_id, sort=sort,
                page=page, page_size=page_size)
        else:
            # 顾问/主管：待分配池 = 未路由客户 ∪ 本部门客户（支持抢单认领）
            items, total = lead_repo.list_leads(
                db, pool_only=True, dept_id=actor.dept_id, or_unrouted=True,
                keyword=keyword, status=status, project_id=project_id,
                sort=sort, page=page, page_size=page_size)
        return [_to_summary(db, lead) for lead in items], total

    if is_admin:
        items, total = lead_repo.list_leads(
            db, all_scope=True, dept_id=dept_id, keyword=keyword, status=status,
            project_id=project_id, sort=sort, page=page, page_size=page_size)
    elif is_head:
        items, total = lead_repo.list_leads(
            db, dept_id=actor.dept_id, keyword=keyword, status=status,
            project_id=project_id, sort=sort, page=page, page_size=page_size)
    else:
        items, total = lead_repo.list_leads(
            db, owner_user_id=actor.id, keyword=keyword, status=status,
            project_id=project_id, sort=sort, page=page, page_size=page_size)
    return [_to_summary(db, lead) for lead in items], total


# =============================================================
# API033 详情
# =============================================================
def get_lead(db: Session, actor: SysUser, lead_id: int) -> LeadStaffOut:
    _require_lead_read(actor)
    lead = _get_lead_in_scope(db, actor, lead_id)
    return _to_staff(db, lead)


# =============================================================
# API034 员工手工/转写确认建客户
# =============================================================
@idempotent("crm_service.create_lead")
def create_lead(db: Session, actor: SysUser, data: LeadManualIn) -> dict:
    _require_lead_write(actor)
    if data.confirmation_token:
        verify_confirmation(actor, data.confirmation_token, operation="CREATE_LEAD",
                            entity_id=None, payload=m3_canonical.lead_create_payload(data), request_key=data.request_key)
    if data.dept_id is not None:
        if actor.employee_role != "ADMIN":
            raise ForbiddenError("仅管理员可指定归属部门")
        if db.get(SysDepartment, data.dept_id) is None:
            raise InvalidRequestError("指定部门不存在")

    mobile = normalize_mobile(data.mobile)

    # ⚠️ 先判归属再调用 acquire_lead：跨部门撞号绝不能先写入对方的跟进记录
    existing = lead_repo.get_by_mobile(db, mobile)
    if existing is not None:
        visible = _can_view_lead(db, actor, existing) or (
            existing.owner_user_id is None and existing.dept_id is not None
            and existing.dept_id == actor.dept_id)
        if not visible:
            raise LeadExistsOutOfScopeError()

    facts = {
        "gender": data.gender,
        "city": data.city,
        "education": data.education,
        "date_of_birth": data.date_of_birth,
        "study_purpose": data.study_purpose,
        "interest_level": data.interest_level,
    }

    lead, created = lead_service.acquire_lead(
        db,
        name=data.name.strip(),
        mobile=mobile,
        source="MANUAL",
        request_key=data.request_key,
        intended_project_id=data.intended_project_id,
        facts=facts,
        content=data.content or "员工手工录入",
        details={"channel": "MANUAL"},
        actor_user_id=actor.id,
    )

    if not created:
        # 复用了既有客户：必须在可见范围内，否则不泄露详情直接 409
        visible = _can_view_lead(db, actor, lead) or (
            lead.owner_user_id is None and lead.dept_id is not None
            and lead.dept_id == actor.dept_id)
        if not visible:
            raise LeadExistsOutOfScopeError()
        return {"lead_id": str(lead.id), "created": False, "version": lead.version}

    # 新建：owner=本人；管理员可覆盖部门，否则落本人部门
    lead.owner_user_id = actor.id
    if data.dept_id is not None:
        lead.dept_id = data.dept_id
    elif lead.dept_id is None and actor.dept_id is not None:
        lead.dept_id = actor.dept_id
    db.flush()
    return {"lead_id": str(lead.id), "created": True, "version": lead.version}


# =============================================================
# API035 补充核对后的客户资料
# =============================================================
@idempotent("crm_service.update_lead")
def update_lead(db: Session, actor: SysUser, lead_id: int, data: LeadUpdateIn) -> LeadStaffOut:
    _require_lead_write(actor)
    lead = _get_lead_in_scope(db, actor, lead_id)
    if lead.version != data.expected_version:
        raise VersionConflictError(lead.version)

    fields = data.model_dump(exclude_unset=True,
                             exclude={"expected_version", "request_key"})

    if "name" in fields and not fields["name"]:
        raise InvalidRequestError("姓名不能为空")
    if "mobile" in fields:
        if not fields["mobile"]:
            raise InvalidRequestError("手机号不能为空")
        mobile = normalize_mobile(fields["mobile"])
        other = lead_repo.get_by_mobile(db, mobile)
        if other is not None and other.id != lead.id:
            raise MobileConflictError()
        fields["mobile"] = mobile
    if fields.get("intended_project_id") is not None:
        if db.get(CourseProject, fields["intended_project_id"]) is None:
            raise InvalidRequestError("意向项目不存在")

    for key, value in fields.items():
        setattr(lead, key, value)

    _recompute_completeness(lead)
    lead.version += 1
    db.flush()
    return _to_staff(db, lead)


# =============================================================
# 采纳研判提取事实：AI 提取 → 顾问核对确认 → 进主档参与判定
# =============================================================
def accept_extracted_facts(db: Session, actor: SysUser, lead_id: int) -> LeadStaffOut:
    """把最近一次研判的 AI 提取事实写入客户主档。

    - 表字段（name/gender/city/education/study_purpose）直接落到 crm_lead 对应列；
    - 其余画像字段（age/education_status/grade/intent_country/family_economy/
      english_level/policy_awareness/handson_ability/logic_thinking/german_potential/
      criminal_record 等）合并进 profile_summary；
    - 写入动作留一条 ASSESSMENT 跟进事件。
    """
    _require_lead_write(actor)
    lead = _get_lead_in_scope(db, actor, lead_id)
    report = lead.assessment_report if isinstance(lead.assessment_report, dict) else {}
    extraction = report.get("extraction") if isinstance(report.get("extraction"), dict) else {}
    facts = extraction.get("facts") if isinstance(extraction.get("facts"), dict) else {}
    if not facts:
        raise InvalidRequestError("当前没有可采纳的研判提取事实，请先发起研判")

    table_fields = ("name", "gender", "city", "education", "study_purpose")
    for field in table_fields:
        value = facts.get(field)
        if value not in (None, ""):
            setattr(lead, field, value)

    summary = dict(lead.profile_summary) if isinstance(lead.profile_summary, dict) else {}
    for key, value in facts.items():
        if key in table_fields or key == "mobile":
            continue
        if value not in (None, ""):
            summary[key] = value
    lead.profile_summary = summary or None

    _recompute_completeness(lead)
    lead.version += 1
    from uuid import uuid4
    _add_follow_up(db, lead, actor.id, follow_up_type="ASSESSMENT",
                   content="采纳研判提取的画像事实", request_key=uuid4())
    db.flush()
    return _to_staff(db, lead)


# =============================================================
# API036 认领（条件更新，并发只有一人成功）
# =============================================================
@idempotent("crm_service.claim_lead")
def claim_lead(db: Session, actor: SysUser, lead_id: int, *,
               expected_version: int, request_key) -> dict:
    _require_lead_write(actor)
    lead = db.get(CrmLead, lead_id)
    if lead is None:
        raise NotFoundError("资源不存在")
    if (actor.employee_role != "ADMIN" and lead.dept_id is not None
            and lead.dept_id != actor.dept_id):
        raise NotFoundError("资源不存在")

    # 未路由客户认领时补上归属部门，保持与本人部门口径一致
    assign_dept = lead.dept_id
    if assign_dept is None and actor.dept_id is not None:
        assign_dept = actor.dept_id

    # 幂等：同一 request_key 的认领重试返回既有结果
    existing = lead_repo.get_follow_up_by_request_key(db, request_key)
    if (existing is not None and existing.lead_id == lead.id
            and existing.follow_up_type == "CLAIMED"):
        return {"id": str(lead.id), "owner_user_id": str(lead.owner_user_id),
                "status": lead.status, "version": lead.version}

    if lead.owner_user_id is not None:
        raise LeadAlreadyClaimedError()
    if lead.version != expected_version:
        raise VersionConflictError(lead.version)

    before_status = lead.status
    result = db.execute(
        update(CrmLead)
        .where(CrmLead.id == lead.id,
               CrmLead.owner_user_id.is_(None),
               CrmLead.version == expected_version)
        .values(owner_user_id=actor.id, status="FOLLOWING",
                dept_id=assign_dept,
                version=CrmLead.version + 1)
    )
    if result.rowcount == 0:
        db.expire_all()
        fresh = db.get(CrmLead, lead.id)
        if fresh is not None and fresh.owner_user_id is not None:
            raise LeadAlreadyClaimedError()
        raise VersionConflictError(fresh.version if fresh else None)

    db.expire_all()
    lead = db.get(CrmLead, lead.id)
    _add_follow_up(db, lead, actor.id, follow_up_type="CLAIMED",
                   content="认领客户", request_key=request_key,
                   status_before=before_status, status_after="FOLLOWING")
    db.flush()
    return {"id": str(lead.id), "owner_user_id": str(lead.owner_user_id),
            "status": lead.status, "version": lead.version}


# =============================================================
# API037 分配/转派（主管/管理员）
# =============================================================
@idempotent("crm_service.assign_lead")
def assign_lead(db: Session, actor: SysUser, lead_id: int, *, owner_user_id: int,
                expected_version: int, reason: str, request_key) -> dict:
    _require_lead_write(actor)
    lead = db.get(CrmLead, lead_id)
    if lead is None:
        raise NotFoundError("资源不存在")
    if actor.employee_role != "ADMIN" and not _is_head_of(db, actor, lead.dept_id):
        raise NotFoundError("资源不存在")
    if lead.version != expected_version:
        raise VersionConflictError(lead.version)

    forward = lead_repo.get_follow_up_by_request_key(db, request_key)
    if (forward is not None and forward.lead_id == lead.id
            and forward.follow_up_type == "REASSIGNED"):
        return {"id": str(lead.id), "owner_user_id": str(lead.owner_user_id),
                "version": lead.version}

    target = db.get(SysUser, owner_user_id)
    if (target is None or target.status != "NORMAL"
            or target.employee_role not in (*_ADVISOR_ROLES, "ADMIN")):
        raise InvalidRequestError("转派目标需为有效顾问")
    if lead.dept_id is None and actor.employee_role == "ADMIN":
        if target.dept_id is None:
            raise InvalidRequestError("目标顾问必须有有效部门")
        lead.dept_id = target.dept_id
    elif target.employee_role != "ADMIN" and target.dept_id != lead.dept_id:
        raise InvalidRequestError("转派目标须与客户同部门")

    old_owner = lead.owner_user_id
    lead.owner_user_id = target.id
    lead.version += 1
    _add_follow_up(db, lead, actor.id, follow_up_type="REASSIGNED",
                   content=reason, request_key=request_key,
                   details={"from_user_id": old_owner, "to_user_id": target.id,
                            "reason": reason})

    recipients = [target.id]
    if old_owner and old_owner != target.id:
        recipients.append(old_owner)          # 已确认：新旧 owner 都通知
    notify(db, f"lead:{lead.id}:assign:{lead.version}", recipients,
           category="LEAD_ASSIGNED",
           title=f"客户「{lead.name or ''}」已转派",
           content=f"客户已转派给{target.real_name}，请及时跟进",
           related_type="lead", related_id=lead.id)
    db.flush()
    return {"id": str(lead.id), "owner_user_id": str(lead.owner_user_id),
            "version": lead.version}


# =============================================================
# API038 跟进历史
# =============================================================
def list_follow_ups(db: Session, actor: SysUser, lead_id: int, *,
                    page: int = 1, page_size: int = 20):
    _require_lead_read(actor)
    _get_lead_in_scope(db, actor, lead_id)
    items, total = lead_repo.list_follow_ups(db, lead_id, page=page, page_size=page_size)
    return [_to_follow_up(db, fu) for fu in items], total


# =============================================================
# API039 写联系记录 / 下次计划
# =============================================================
@idempotent("crm_service.add_follow_up")
def add_follow_up(db: Session, actor: SysUser, lead_id: int, data: FollowUpIn) -> dict:
    _require_lead_write(actor)
    lead = _get_lead_in_scope(db, actor, lead_id)

    existing = lead_repo.get_follow_up_by_request_key(db, data.request_key)
    if existing is not None:
        return {"follow_up_id": str(existing.id), "lead_version": lead.version,
                "next_follow_up_at": lead.next_follow_up_at}

    if data.confirmation_token:
        verify_confirmation(actor, data.confirmation_token, operation="ADD_FOLLOWUP",
                            entity_id=lead_id,
                            payload=m3_canonical.follow_up_payload(data),
                            expected_version=data.expected_version, request_key=data.request_key)

    if lead.version != data.expected_version:
        raise VersionConflictError(lead.version)

    next_at = data.next_follow_up_at if "next_follow_up_at" in data.model_fields_set else None
    fu = _add_follow_up(db, lead, actor.id, follow_up_type="CONTACT",
                        content=data.content, request_key=data.request_key,
                        next_follow_up_at=next_at)
    # null=清除、省略=保留、新值=覆盖（同一事务更新当前计划缓存）
    if "next_follow_up_at" in data.model_fields_set:
        lead.next_follow_up_at = data.next_follow_up_at
    lead.version += 1
    db.flush()
    return {"follow_up_id": str(fu.id), "lead_version": lead.version,
            "next_follow_up_at": lead.next_follow_up_at}


# =============================================================
# API040 流失 / 恢复 / 开始跟进
# =============================================================
@idempotent("crm_service.transition_lead")
def transition_lead(db: Session, actor: SysUser, lead_id: int,
                    data: LeadTransitionIn) -> dict:
    _require_lead_write(actor)
    lead = _get_lead_in_scope(db, actor, lead_id)
    if data.confirmation_token:
        verify_confirmation(actor, data.confirmation_token, operation="TRANSITION_LEAD",
                            entity_id=lead_id,
                            payload=m3_canonical.transition_payload(data),
                            expected_version=data.expected_version, request_key=data.request_key)
    if lead.version != data.expected_version:
        raise VersionConflictError(lead.version)
    if lead.status == "SIGNED":
        raise StateTransitionDeniedError("已签约客户不能通过状态接口变更")

    before = lead.status
    now = datetime.now(timezone.utc)
    if data.target_status == "LOST":
        lead.status = "LOST"
        lead.lost_at = now
        lead.loss_reason = data.reason
    else:
        lead.status = "FOLLOWING"
        if before == "LOST":
            lead.lost_at = None
            lead.loss_reason = None

    lead.version += 1
    _add_follow_up(db, lead, actor.id, follow_up_type="STATUS",
                   content=data.reason, request_key=data.request_key,
                   status_before=before, status_after=data.target_status)
    db.flush()
    return {"id": str(lead.id), "status": lead.status, "version": lead.version}


# =============================================================
# API043 确认线下签约并转学生（5 表原子事务）
# =============================================================
@idempotent("crm_service.convert_to_student")
def convert_to_student(db: Session, actor: SysUser, lead_id: int,
                       data: ConversionIn) -> dict:
    _require_lead_write(actor)

    # 锁客户行，防并发重复转化
    lead = db.get(CrmLead, lead_id, with_for_update=True,populate_existing=True)
    if lead is None:
        raise NotFoundError("资源不存在")
    if not _can_view_lead(db, actor, lead):
        raise NotFoundError("资源不存在")

    # 幂等：同 request_key 的 SIGNED 事件 + 已有档案 → 返回既有（不再给密码）
    existing_fu = lead_repo.get_follow_up_by_request_key(db, data.request_key)
    profile = db.scalar(select(StudentProfile).where(
        StudentProfile.converted_lead_id == lead.id))
    if profile is not None:
        if (existing_fu is not None and existing_fu.follow_up_type == "SIGNED"
                and existing_fu.lead_id == lead.id):
            enrollment = db.scalar(select(StudentCourseEnrollment).where(
                StudentCourseEnrollment.student_profile_id == profile.id))
            return {
                "lead_id": str(lead.id),
                "student_profile_id": str(profile.id),
                "user_id": str(profile.user_id),
                "enrollment_id": str(enrollment.id) if enrollment else None,
                "already_converted": True,
            }
        raise AlreadyConvertedError()

    if lead.status == "SIGNED":
        raise AlreadyConvertedError()
    if lead.version != data.expected_version:
        raise VersionConflictError(lead.version)
    if not data.contract_confirmed:
        raise InvalidRequestError("必须确认线下已完成签约")

    if not lead.owner_user_id:raise InvalidRequestError("请先认领或分配负责顾问")
    # ---- 前置校验 ----
    project = db.get(CourseProject, data.course_project_id)
    if project is None:
        raise InvalidRequestError("课程项目不存在")

    cls = db.get(SysClass, data.class_id)
    if cls is None:
        raise InvalidRequestError("班级不存在")
    if not cls.head_teacher_id:
        raise ClassTeacherRequiredError()
    teacher=db.get(SysUser,cls.head_teacher_id)
    if not teacher or not teacher.is_employee or teacher.status!="NORMAL":raise ClassTeacherRequiredError()
    if actor.employee_role!="ADMIN" and cls.dept_id!=lead.dept_id:raise DepartmentMismatchError("班级与客户归属部门不一致")

    advisor = db.get(SysUser, data.advisor_user_id)
    if (advisor is None or advisor.status != "NORMAL"
            or advisor.employee_role not in (*_ADVISOR_ROLES, "ADMIN")):
        raise InvalidRequestError("个人顾问无效")
    dept_id = cls.dept_id
    if advisor.employee_role != "ADMIN" and advisor.dept_id != dept_id:
        raise DepartmentMismatchError("个人顾问与班级部门不一致")

    mobile = lead.mobile
    if db.scalar(select(SysUser.id).where(SysUser.username == mobile)):
        raise UsernameConflictError()
    if lead.name is None:
        raise InvalidRequestError("客户姓名缺失，请先补充资料")

    # ---- 合同金额校验 ----
    amount = None
    if data.contract_amount is not None:
        try:
            amount = Decimal(data.contract_amount)
        except (InvalidOperation, TypeError) as exc:
            raise InvalidRequestError("合同金额格式不正确") from exc
        precision=CrmLead.__table__.c.contract_amount.type.precision
        scale=CrmLead.__table__.c.contract_amount.type.scale
        if not amount.is_finite() or amount<0 or amount>=Decimal(10)**(precision-scale):raise InvalidRequestError("合同金额须为有效非负金额且不能超出范围")
        if amount!=amount.quantize(Decimal("0.01")):raise InvalidRequestError("合同金额最多两位小数")
    if (amount is None) != (data.contract_currency is None):
        raise InvalidRequestError("合同金额与币种必须同时提供或同时省略")

    if data.contract_currency is not None and (len(data.contract_currency)!=3 or not data.contract_currency.isascii() or not data.contract_currency.isalpha()):raise InvalidRequestError("币种须为三位字母代码")
    now = datetime.now(timezone.utc)

    # ① 学生账号（student：无角色、无部门、无敏感授权）
    temp_password = generate_temp_password()
    student_user = SysUser(
        username=mobile,
        password_hash=hash_password(temp_password),
        real_name=lead.name,
        user_type="STUDENT",
        employee_role=None,
        dept_id=None,
        status="NORMAL",
        can_handle_feedback=False,
        psych_access_enabled=False,
        must_change_password=True,
        temporary_password_expires_at=now + timedelta(days=_TEMP_PASSWORD_DAYS),
        token_version=0,
    )
    db.add(student_user)
    db.flush()

    # ② 学生档案（部门取班级所属部门，满足 (class_id,dept_id) 复合外键）
    profile = StudentProfile(
        user_id=student_user.id,
        converted_lead_id=lead.id,
        advisor_user_id=advisor.id,
        dept_id=dept_id,
        class_id=cls.id,
        gender=lead.gender,
        city=lead.city,
        education=lead.education,
        date_of_birth=lead.date_of_birth,
        enrollment_date=data.enrollment_date,
        status="ENROLLED",
        psych_consent_status="NOT_GIVEN",
        version=1,
    )
    db.add(profile)
    db.flush()

    # ③ 课程关联
    enrollment = StudentCourseEnrollment(
        student_profile_id=profile.id,
        course_project_id=project.id,
        status="ENROLLED",
        version=1,
    )
    db.add(enrollment)
    db.flush()

    # ④ 线索 SIGNED + 合同信息
    before_status = lead.status
    lead.status = "SIGNED"
    lead.signed_at = now
    lead.contract_ref = data.contract_ref
    lead.contract_amount = amount
    lead.contract_currency = data.contract_currency.upper() if data.contract_currency else None
    lead.version += 1

    # ⑤ SIGNED 跟进
    _add_follow_up(
        db, lead, actor.id, follow_up_type="SIGNED",
        content="确认线下签约并转学生", request_key=data.request_key,
        status_before=before_status, status_after="SIGNED",
        details={"student_profile_id": profile.id, "user_id": student_user.id,
                 "enrollment_id": enrollment.id, "course_project_id": project.id},
    )

    # ⑥ 通知：个人顾问 + 本部门主管（正文绝不含密码）
    recipients = [advisor.id]
    dept = db.get(SysDepartment, dept_id)
    if dept is not None and dept.head_user_id:
        recipients.append(dept.head_user_id)
    notify(db, f"lead:{lead.id}:converted:1", recipients,
           category="SYSTEM",
           title=f"客户「{lead.name}」已签约转学生",
           content="学生账号与档案已创建，请按线下流程交接初始密码。",
           related_type="lead", related_id=lead.id)
    db.flush()

    logger.info("M3 转化成功 lead=%s profile=%s（临时密码不落日志）", lead.id, profile.id)
    return {
        "lead_id": str(lead.id),
        "student_profile_id": str(profile.id),
        "user_id": str(student_user.id),
        "enrollment_id": str(enrollment.id),
        "already_converted": False,
        "initial_credentials": {
            "username": student_user.username,
            "temporary_password": temp_password,
            "expires_at": student_user.temporary_password_expires_at,
            "must_change_password": True,
        },
    }
