"""
crm_lead 查询（M2 获客与研判）

⚠️ Repository 不自行 commit；按范围取客户一律通过 core.permissions 的 Scope
   （越权返回 404，不暴露数据是否存在）。
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.lead import CrmLead


def get_by_id(db: Session, lead_id: int) -> CrmLead | None:
    return db.get(CrmLead, lead_id)


def get_by_mobile(db: Session, mobile: str) -> CrmLead | None:
    """规范手机号全局唯一：一人一客户主档。"""
    return db.scalar(select(CrmLead).where(CrmLead.mobile == mobile))


def get_by_request_key(db: Session, request_key) -> CrmLead | None:
    """幂等重试：同一 request_key 不重复建客户。"""
    return db.scalar(select(CrmLead).where(CrmLead.request_key == request_key))
