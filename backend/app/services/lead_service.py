"""
三渠道统一获客（API023）—— M2

设计要点（对齐 M2 模块文档与需求 R03）：
  1. **统一入口**：表单 / 客服对话 / 活动报名都走 acquire_lead，页面与助手不各写一套。
  2. **规范手机号 + 一人一档**：手机号规范化后查重；重复咨询只在既有客户下追加跟进，
     **不改销售状态、不改归属**。
  3. **幂等**：新建主档用 request_key 唯一键；追加跟进用 uuid5 派生键，重试不产生重复事件。
  4. **完整度与状态分离**：profile_completeness 只表达信息是否齐全，status 只表达销售阶段。
  5. **部门路由**：意向项目有默认部门 → 落到该部门公共池；无默认部门 → dept_id 留空，
     进管理员待分配池。
  6. **匿名不泄露**：回执永远是 {accepted:true, receiptNo:request_key}，
     不返回客户是否存在、客户 ID、姓名或顾问。
"""
from __future__ import annotations

import logging
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select, text
from app.core.public_idempotency import reserve_public_request
from app.core.errors import StateConflictError
from sqlalchemy.orm import Session

from app.core.errors import ValidationError
from app.core.mobile import mask_mobile, normalize_mobile
from app.core.transaction import with_business_transaction
from app.models.follow_up import CrmFollowUp
from app.models.lead import CrmLead
from app.repositories import lead as lead_repo
from app.repositories import project as project_repo
from app.schemas.lead import LeadCaptureIn
from app.services import rate_limit
from app.services.m2_errors import MissingFieldError

logger = logging.getLogger(__name__)

# 渠道 → 客户首次来源（EVENT 由活动报名路径传入）
CHANNEL_SOURCE = {"FORM": "WEBSITE", "ASSISTANT": "CHAT"}

# 表单渠道必填字段（04/01 文档：姓名、手机号、性别、城市、学历）
_FORM_REQUIRED = ("gender", "city", "education")

# 影响"完整度"的事实字段
_COMPLETENESS_FIELDS = ("gender", "city", "education")

# 允许从留资/简历里补齐的事实字段（只补空值，绝不覆盖已核对事实）
_FACT_FIELDS = ("gender", "city", "education", "date_of_birth",
                "study_purpose", "interest_level")


# ============================================================
# 内部工具（调用方负责事务）
# ============================================================
def _route_dept_id(db: Session, intended_project_id: int | None) -> int | None:
    """按意向项目的默认部门路由；无默认部门返回 None（管理员待分配池）。"""
    if not intended_project_id:
        return None
    project = project_repo.get_by_id(db, intended_project_id)
    if project is None:
        raise ValidationError("意向项目不存在",
                              errors=[{"field": "intended_project_id", "reason": "项目不存在"}])
    return project.default_dept_id


def _fill_missing_facts(lead: CrmLead, facts: dict) -> None:
    """只补空字段；已有事实（含顾问核对过的）绝不被覆盖。"""
    for field in _FACT_FIELDS:
        if getattr(lead, field, None) in (None, "") and facts.get(field) not in (None, ""):
            setattr(lead, field, facts[field])


def _recompute_completeness(lead: CrmLead) -> None:
    """完整度只表达"信息是否齐全"，与销售状态无关。"""
    complete = bool(lead.name) and bool(lead.mobile) and all(
        getattr(lead, field, None) for field in _COMPLETENESS_FIELDS)
    lead.profile_completeness = "COMPLETE" if complete else "MINIMAL"


def _add_follow_up(db: Session, lead: CrmLead, *, follow_up_type: str, content: str,
                   details: dict, request_key, actor_user_id: int | None = None) -> None:
    """追加不可删除的跟进事件；uuid5 派生键保证重试不重复写。"""
    event_key = uuid5(NAMESPACE_URL, f"m2:{follow_up_type}:{lead.id}:{request_key}")
    exists = db.scalar(select(CrmFollowUp.id).where(CrmFollowUp.request_key == event_key))
    if exists:
        return
    db.add(CrmFollowUp(
        lead_id=lead.id,
        actor_user_id=actor_user_id,
        follow_up_type=follow_up_type,
        content=content,
        status_before=lead.status,
        status_after=lead.status,
        details=details,
        request_key=event_key,
    ))
    db.flush()


def acquire_lead(db: Session, *, name: str, mobile: str, source: str, request_key,
                 intended_project_id: int | None = None, facts: dict | None = None,
                 content: str = "新增留资", details: dict | None = None,
                 actor_user_id: int | None = None) -> tuple[CrmLead, bool]:
    """在既有事务内**复用或创建**客户主档，并写 ACQUIRED 跟进。

    ⚠️ 手机号必须是**已规范化**的值；本函数不 commit。

    Returns:
        (lead, created)：created 表示本次是否新建了主档。
    """
    mobile=normalize_mobile(mobile)
    db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 9102))"),{"key":mobile})
    facts = facts or {}
    meta = {"source": source, **(details or {})}

    # ① 幂等快捷路径：该 request_key 已经建过主档
    lead = lead_repo.get_by_request_key(db, request_key)
    if lead is not None:
        if lead.mobile!=mobile:raise StateConflictError("请求键已被其他客户使用")
        return lead, False

    created = False

    # ② 一人一档：按规范手机号复用
    lead = lead_repo.get_by_mobile(db, mobile)
    if lead is not None:
        lead.version+=1
        _fill_missing_facts(lead, facts)
        if intended_project_id and lead.intended_project_id is None:
            lead.intended_project_id = intended_project_id
        _recompute_completeness(lead)
        db.flush()
        _add_follow_up(db, lead, follow_up_type="ACQUIRED",
                       content=f"重复咨询：{content}", details={**meta, "reused": True},
                       request_key=request_key, actor_user_id=actor_user_id)
        return lead, False

    # ③ 新建主档
    lead = CrmLead(
        name=name,
        mobile=mobile,
        source=source,
        status="NEW",
        dept_id=_route_dept_id(db, intended_project_id),
        intended_project_id=intended_project_id,
        profile_completeness="MINIMAL",
        request_key=request_key,
        version=1,
    )
    _fill_missing_facts(lead, facts)
    _recompute_completeness(lead)
    db.add(lead)
    db.flush()
    created = True

    _add_follow_up(db, lead, follow_up_type="ACQUIRED", content=content,
                   details={**meta, "reused": False},
                   request_key=request_key, actor_user_id=actor_user_id)
    return lead, created


# ============================================================
# API023 访客确认留资
# ============================================================
def capture_lead(db: Session, data: LeadCaptureIn) -> dict:
    """三渠道统一留资入口。

    ⚠️ 回执不区分"新客户/已有客户"，避免匿名调用探测客户是否存在。
    """
    if not data.confirmed:
        raise ValidationError("请确认后再提交",
                              errors=[{"field": "confirmed", "reason": "必须为 true"}])

    if data.channel == "FORM":
        missing = [f for f in _FORM_REQUIRED
                   if not str(getattr(data, f) or "").strip()]
        if missing:
            raise MissingFieldError(
                "表单渠道缺少必填项",
                errors=[{"field": f, "reason": "表单渠道必填"} for f in missing],
            )

    name = str(data.name).strip()
    mobile = normalize_mobile(data.mobile)
    source = CHANNEL_SOURCE[data.channel]
    facts = {
        "gender": data.gender,
        "city": data.city,
        "education": data.education,
        "date_of_birth": data.date_of_birth,
        "study_purpose": data.study_purpose,
        "interest_level": data.interest_level,
    }

    with with_business_transaction(db):
        reserve_public_request(db,"lead.capture",data.request_key,data.model_dump(mode="json"))
        _, created = acquire_lead(
            db,
            name=name,
            mobile=mobile,
            source=source,
            request_key=data.request_key,
            intended_project_id=data.intended_project_id,
            facts=facts,
            content="访客留资" if data.channel == "FORM" else "客服对话留资",
            details={"channel": data.channel, "engagement": "LEAD_CAPTURE"},
        )

    logger.info("M2 留资受理 channel=%s mobile=%s created=%s",
                data.channel, mask_mobile(mobile), created)
    return {"accepted": True, "receiptNo": str(data.request_key)}
