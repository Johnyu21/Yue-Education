"""
crm_lead / crm_follow_up 查询（M2 获客与研判 + M3 客户经营）

⚠️ Repository 不自行 commit；按范围取客户一律通过 core.permissions 的 Scope
   （越权返回 404，不暴露数据是否存在）。
"""
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.models.follow_up import CrmFollowUp
from app.models.lead import CrmLead
from app.repositories.common import paginate


def get_by_id(db: Session, lead_id: int) -> CrmLead | None:
    return db.get(CrmLead, lead_id)


def get_by_mobile(db: Session, mobile: str) -> CrmLead | None:
    """规范手机号全局唯一：一人一客户主档。"""
    return db.scalar(select(CrmLead).where(CrmLead.mobile == mobile))


def get_by_request_key(db: Session, request_key) -> CrmLead | None:
    """幂等重试：同一 request_key 不重复建客户。"""
    return db.scalar(select(CrmLead).where(CrmLead.request_key == request_key))


# =============================================================
# M3：列表查询（公共池 / 本人 / 本部门 / 全域）
# =============================================================
def _apply_filters(stmt: Select, *, keyword: str | None, status: str | None,
                   project_id: int | None) -> Select:
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(CrmLead.name.ilike(like) | CrmLead.mobile.ilike(like))
    if status:
        stmt = stmt.where(CrmLead.status == status)
    if project_id is not None:
        stmt = stmt.where(CrmLead.intended_project_id == project_id)
    return stmt


def _apply_sort(stmt: Select, sort: str | None) -> Select:
    if sort == "score_desc":
        return stmt.order_by(CrmLead.latest_score.desc().nulls_last(), CrmLead.id.desc())
    if sort == "next_followup_asc":
        return stmt.order_by(CrmLead.next_follow_up_at.asc().nulls_last(), CrmLead.id.desc())
    # created_desc（默认）：模型未映射 create_time，用自增 id 等价表达创建顺序
    return stmt.order_by(CrmLead.id.desc())


def list_leads(db: Session, *, owner_user_id: int | None = None,
               dept_id: int | None = None, pool_only: bool = False,
               all_scope: bool = False, or_unrouted: bool = False,
               keyword: str | None = None,
               status: str | None = None, project_id: int | None = None,
               sort: str = "created_desc", page: int = 1, page_size: int = 20):
    """线索列表。pool_only=部门公共池；all_scope=管理员全域。

    or_unrouted：待分配池同时包含“未路由（无部门）”客户，用于顾问抢单。
    """
    stmt = select(CrmLead)
    if pool_only:
        stmt = stmt.where(CrmLead.owner_user_id.is_(None))
        if or_unrouted:
            stmt = stmt.where(or_(CrmLead.dept_id.is_(None), CrmLead.dept_id == dept_id))
        elif dept_id is not None:
            stmt = stmt.where(CrmLead.dept_id == dept_id)
    elif not all_scope:
        if owner_user_id is not None:
            stmt = stmt.where(CrmLead.owner_user_id == owner_user_id)
        if dept_id is not None:
            # 主管看本部门（含未分配池），不含子部门
            stmt = stmt.where(CrmLead.dept_id == dept_id)
    stmt = _apply_filters(stmt, keyword=keyword, status=status, project_id=project_id)
    return paginate(db, _apply_sort(stmt, sort), page, page_size)


def list_follow_ups(db: Session, lead_id: int, *, page: int = 1, page_size: int = 20):
    stmt = (select(CrmFollowUp)
            .where(CrmFollowUp.lead_id == lead_id)
            .order_by(CrmFollowUp.create_time.desc(), CrmFollowUp.id.desc()))
    return paginate(db, stmt, page, page_size)


def get_follow_up_by_request_key(db: Session, request_key) -> CrmFollowUp | None:
    return db.scalar(select(CrmFollowUp).where(CrmFollowUp.request_key == request_key))

