"""
活动报名与取消（API024~API026）—— M2

核心不变量：
  1. **名额以数据库行锁内复查为准**，绝不信任页面传来的 remainingCapacity。
  2. **同一活动同一手机号唯一**（业务预检 + 数据库 UNIQUE(event_id,mobile) 双保险）。
  3. **学生绑定本人档案**（姓名/手机号取自本人账号，客户端不得指定他人）；
     **访客必须绑定线索**（复用或新建 crm_lead）。
  4. 报名与取消**遵守同一锁序**：先锁 event_lecture 行 → 再动 event_registration。
  5. 访客取消凭据为确定性签名：明文只在首次成功响应返回，库中只存哈希。
"""
from __future__ import annotations

import logging
import hmac
from app.core.public_idempotency import reserve_public_request
from app.core.errors import StateConflictError
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import EventFullError, ForbiddenError, NotFoundError, ValidationError, VersionConflictError
from app.core.mobile import mask_mobile, normalize_mobile
from app.core.transaction import with_business_transaction
from app.models.event import EventLecture, EventRegistration
from app.models.student import StudentProfile
from app.models.user import SysUser
from app.repositories import event as event_repo
from app.schemas.event import RegistrationCancelIn, RegistrationIn
from app.services import lead_service, rate_limit, voucher
from app.services.m2_errors import (
    DuplicateRegistrationError,
    MissingFieldError,
    RegistrationClosedError,
    RegistrationNotCancellableError,
)

logger = logging.getLogger(__name__)

# event_registration 有 CHECK(lead_id IS NULL OR cancel_token_hash IS NOT NULL)，
# 但访客凭据绑定的是 registration_id（插入后才由数据库生成）——
# 因此先写一个占位值满足约束，再在同一事务内覆盖为真实哈希（事务外不可见）。
_PENDING_HASH = "pending"


# ============================================================
# DTO 归一化
# ============================================================
def registration_out(reg: EventRegistration, ev: EventLecture | None) -> dict:
    """报名 DTO；**不含 cancel_token_hash**。"""
    return {
        "id": str(reg.id),
        "event": {"id": str(reg.event_id), "title": ev.title if ev else ""},
        "registrantName": reg.registrant_name,
        "mobile": reg.mobile,
        "status": reg.status,
        "registeredAt": reg.registered_at,
        "canceledAt": reg.canceled_at,
        "version": reg.version,
    }


# ============================================================
# 身份解析
# ============================================================
def _my_profile(db: Session, user: SysUser) -> StudentProfile | None:
    return db.scalar(select(StudentProfile).where(StudentProfile.user_id == user.id))


def _student_mobile(user: SysUser) -> str:
    """学生手机号来源是账号（username 约定为规范手机号）。

    ⚠️ 历史/演示数据可能用非手机号账号（如 seed 的 student01），
    此时退化为原值，保证演示可用，但会记一条告警便于排查。
    """
    try:
        return normalize_mobile(user.username)
    except ValidationError:
        logger.warning("学生账号不是规范手机号，按原值使用 user=%s", user.id)
        return user.username

def _event_lead_request_key(event_id: int, mobile: str):
    """访客报名所用线索的幂等键：同一活动 + 同一手机号 → 同一键。"""
    return uuid5(NAMESPACE_URL, f"m2:event-lead:{event_id}:{mobile}")


def _ensure_registrable(ev: EventLecture) -> None:
    """报名开放性与截止时间校验（必须在锁内调用）。"""
    if ev.status != "OPEN":
        raise RegistrationClosedError("活动未开放报名")
    if datetime.now(timezone.utc) > ev.signup_deadline:
        raise RegistrationClosedError("报名已截止")


# ============================================================
# API024 报名
# ============================================================
def register_event(db: Session, event_id: int, data: RegistrationIn, *,
                   user: SysUser | None = None, client_key: str | None = None) -> dict:
    if client_key:
        rate_limit.check(client_key)

    if not data.confirmed:
        raise ValidationError("请确认后再提交",
                              errors=[{"field": "confirmed", "reason": "必须为 true"}])

    is_student = user is not None and user.is_student
    if user is not None and user.must_change_password:
        raise ForbiddenError("请先修改初始密码")

    cancel_token: str | None = None

    with with_business_transaction(db):
        # ① 锁活动行（与取消同锁序）
        ev = event_repo.lock_by_id(db, event_id)
        if ev is None:
            raise NotFoundError("资源不存在")

        # ② 幂等：同一 request_key 直接返回既有报名
        existing = event_repo.get_registration_by_request_key(db, data.request_key)

        # ③ 身份 → 姓名/手机号/绑定对象
        if is_student:
            profile = _my_profile(db, user)
            if profile is None:
                raise NotFoundError("学生档案不存在")
            name = user.real_name
            mobile = _student_mobile(user)
            student_profile_id, lead_id = profile.id, None
        else:
            if not (data.name and str(data.name).strip()) or not data.mobile:
                missing = []
                if not (data.name and str(data.name).strip()):
                    missing.append({"field": "name", "reason": "访客报名必填"})
                if not data.mobile:
                    missing.append({"field": "mobile", "reason": "访客报名必填"})
                raise MissingFieldError("访客报名必须填写姓名与手机号", errors=missing)
            name = str(data.name).strip()
            mobile = normalize_mobile(data.mobile)
            student_profile_id, lead_id = None, None      # 访客稍后绑定线索

        fresh_request=reserve_public_request(db,"event.register",data.request_key,{"event_id":event_id,"mobile":mobile,"name":name,"student_profile_id":student_profile_id,"request":data.model_dump(mode="json")})
        if not fresh_request and existing is None:raise StateConflictError("该报名请求已结束，请使用新请求键")
        if existing is not None:
            if existing.event_id!=event_id or existing.mobile!=mobile or existing.student_profile_id!=student_profile_id:raise StateConflictError("请求键已被其他报名使用")

        # ④ 访客必须绑定线索（复用或新建，含 ACQUIRED 跟进）
        if not is_student:
            lead, _ = lead_service.acquire_lead(
                db,
                name=name,
                mobile=mobile,
                source="EVENT",
                request_key=_event_lead_request_key(event_id, mobile),
                intended_project_id=ev.course_project_id,
                facts={},
                content=f"活动报名：{ev.title}",
                details={"channel": "EVENT", "event_id": str(ev.id),
                         "engagement": "REGISTRATION"},
            )
            lead_id = lead.id

        # ⑤ 同活动同手机号唯一
        same = event_repo.get_registration_by_event_mobile(db, event_id, mobile)

        if existing is not None:
            result = _build_register_result(existing, ev)
            if existing.lead_id is not None:
                result["cancelToken"] = voucher.sign_cancel_voucher(
                    existing.event_id, existing.id, existing.request_key)
            return result

        if same is not None and same.status != "CANCELLED":
            # 已报名（同键重试在上面已处理）→ 泛化重复提示
            raise DuplicateRegistrationError("该手机号已报名此活动")

        # ⑥ 可报名性 + 名额复查（锁内）
        _ensure_registrable(ev)
        used = event_repo.count_active_registrations(db, ev.id)
        if used >= ev.capacity:
            raise EventFullError(f"名额已满（上限 {ev.capacity}）")

        # ⑦ 写报名（已取消的重新报名 → 更新同一记录，保留原 request_key）
        if same is not None:
            reg = same
            reg.request_key=data.request_key
            reg.registered_at=datetime.now(timezone.utc)
            reg.status = "REGISTERED"
            reg.canceled_at = None
            reg.registrant_name = name
            reg.student_profile_id = student_profile_id
            reg.lead_id = lead_id
            reg.version += 1
            reg.cancel_token_hash = _PENDING_HASH if lead_id is not None else None
            db.flush()
        else:
            reg = EventRegistration(
                event_id=ev.id,
                student_profile_id=student_profile_id,
                lead_id=lead_id,
                registrant_name=name,
                mobile=mobile,
                status="REGISTERED",
                cancel_token_hash=_PENDING_HASH if lead_id is not None else None,
                request_key=data.request_key,
                version=1,
            )
            db.add(reg)
            db.flush()

        # ⑧ 访客凭据：拿到 registration_id 后写入真实哈希（同一事务内覆盖占位值）
        if reg.lead_id is not None:
            cancel_token = voucher.sign_cancel_voucher(reg.event_id, reg.id, reg.request_key)
            reg.cancel_token_hash = voucher.hash_voucher(cancel_token)
            db.flush()
        else:
            cancel_token = None

        result = _build_register_result(reg, ev)
        if cancel_token:
            result["cancelToken"] = cancel_token

    logger.info("M2 报名受理 event=%s mobile=%s student=%s",
                event_id, mask_mobile(mobile), is_student)
    return result


def _build_register_result(reg: EventRegistration, ev: EventLecture) -> dict:
    return {
        "registrationId": str(reg.id),
        "eventId": str(ev.id),
        "status": reg.status,
        "registeredAt": reg.registered_at,
        "version": reg.version,
    }


# ============================================================
# API025 取消报名
# ============================================================
def cancel_registration(db: Session, registration_id: int,
                        data: RegistrationCancelIn, *,
                        user: SysUser | None = None) -> dict:
    result: dict | None = None

    with with_business_transaction(db):
        reg = event_repo.get_registration(db, registration_id)
        if reg is None:
            raise NotFoundError("资源不存在")

        # 先锁活动行：与报名保持同一锁序，避免与名额复查互相插队
        ev = event_repo.lock_by_id(db, reg.event_id)
        if ev is None:
            raise NotFoundError("资源不存在")

        reg=db.get(EventRegistration,registration_id,with_for_update=True,populate_existing=True)

        # 鉴权：学生本人 或 有效访客凭据；不通过一律 404（不暴露报名是否存在）
        if user is not None and user.is_student:
            if user.must_change_password:
                raise ForbiddenError("请先修改初始密码")
            profile = _my_profile(db, user)
            if profile is None or reg.student_profile_id != profile.id:
                raise NotFoundError("资源不存在")
        else:
            if not data.cancel_token or not hmac.compare_digest(voucher.hash_voucher(data.cancel_token),reg.cancel_token_hash or ""):
                raise NotFoundError("资源不存在")
            if not voucher.verify_cancel_voucher(data.cancel_token, reg.event_id,
                                                 reg.id, reg.request_key):
                raise NotFoundError("资源不存在")

        if reg.status == "CANCELLED":
            # 幂等：重复取消返回当前状态，不再报错（同一用户重试保持同一结果）
            result = {"id": str(reg.id), "status": reg.status, "version": reg.version}
        else:
            if reg.status != "REGISTERED":
                raise RegistrationNotCancellableError("当前报名状态不可取消")
            if reg.version != data.expected_version:
                raise VersionConflictError(reg.version)

            reg.status = "CANCELLED"
            reg.canceled_at = datetime.now(timezone.utc)
            reg.version += 1
            db.flush()
            result = {"id": str(reg.id), "status": reg.status, "version": reg.version}

    logger.info("M2 取消报名 registration=%s", registration_id)
    return result


# ============================================================
# API026 学生本人报名列表
# ============================================================
def list_my_registrations(db: Session, user: SysUser, *, page: int, page_size: int):
    profile = _my_profile(db, user)
    if profile is None:
        raise NotFoundError("学生档案不存在")

    items, total = event_repo.list_student_registrations(
        db, profile.id, page=page, page_size=page_size)

    event_ids = [r.event_id for r in items]
    events = {
        ev.id: ev
        for ev in db.scalars(select(EventLecture).where(EventLecture.id.in_(event_ids))).all()
    } if event_ids else {}

    return [registration_out(r, events.get(r.event_id)) for r in items], total
