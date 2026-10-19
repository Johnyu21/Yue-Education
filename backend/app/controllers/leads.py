"""
线索 CRM 与研判 —— 线索增删改查 / 跟进 / 认领 / 转派 / 研判 / 转学生

M2：API041/042/096（研判与简历提取）
M3：API032~040、043（客户经营与转化）
"""
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import require_password_changed
from app.core.responses import ok
from app.core.transaction import with_business_transaction
from app.db.session import get_db
from app.models.user import SysUser
from app.schemas.common import VersionRequest, paged
from app.schemas.lead import (
    AssessmentIn,
    ConversionIn,
    FollowUpIn,
    LeadAssignmentIn,
    LeadManualIn,
    LeadTransitionIn,
    LeadUpdateIn,
    ResumeExtractionIn,
)
from app.services import assessment_service, crm_service

router = APIRouter(tags=["线索 CRM 与研判"])


# =============================================================
# M3：客户列表 / 详情 / 建客户 / 补充资料
# =============================================================
@router.get("/api/v1/employees/leads")
def list_leads(
    user: SysUser = Depends(require_password_changed),
    db: Session = Depends(get_db),
    view: Literal["mine", "pool"] = Query("mine"),
    keyword: str | None = Query(None, max_length=80),
    status_: str | None = Query(None, alias="status"),
    project_id: int | None = Query(None),
    dept_id: int | None = Query(None, description="仅管理员可用"),
    sort: Literal["created_desc", "score_desc", "next_followup_asc"] = Query("created_desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """API032 公共池/本人客户列表（池视图手机号脱敏）"""
    items, total = crm_service.list_leads(
        db, user, view=view, keyword=keyword, status=status_, project_id=project_id,
        dept_id=dept_id, sort=sort, page=page, page_size=page_size)
    return ok(paged([i.model_dump(mode="json") for i in items], page, page_size, total))


@router.get("/api/v1/employees/leads/{lead_id}")
def get_lead(lead_id: int,
             user: SysUser = Depends(require_password_changed),
             db: Session = Depends(get_db)):
    """API033 客户详情（本人/主管部门/管理员，范围外 404）"""
    dto = crm_service.get_lead(db, user, lead_id)
    return ok(dto.model_dump(mode="json"))


@router.post("/api/v1/employees/leads", status_code=201)
def create_lead(data: LeadManualIn,
                user: SysUser = Depends(require_password_changed),
                db: Session = Depends(get_db)):
    """API034 员工手工/转写确认建客户（复用 M2 acquire_lead）"""
    with with_business_transaction(db):
        result = crm_service.create_lead(db, user, data)
    return ok(result)


@router.patch("/api/v1/employees/leads/{lead_id}")
def update_lead(lead_id: int, data: LeadUpdateIn,
                user: SysUser = Depends(require_password_changed),
                db: Session = Depends(get_db)):
    """API035 补充核对后的客户资料（事实白名单 + 乐观锁）"""
    with with_business_transaction(db):
        dto = crm_service.update_lead(db, user, lead_id, data)
    return ok(dto.model_dump(mode="json"))


# =============================================================
# M3：认领 / 转派 / 跟进 / 状态机
# =============================================================
@router.post("/api/v1/employees/leads/{lead_id}/claim")
def claim_lead(lead_id: int, data: VersionRequest,
               user: SysUser = Depends(require_password_changed),
               db: Session = Depends(get_db)):
    """API036 认领线索（条件更新，并发只有一人成功）"""
    with with_business_transaction(db):
        result = crm_service.claim_lead(
            db, user, lead_id, expected_version=data.expected_version,
            request_key=data.request_key)
    return ok(result)


@router.post("/api/v1/employees/leads/{lead_id}/assignment")
def assign_lead(lead_id: int, data: LeadAssignmentIn,
                user: SysUser = Depends(require_password_changed),
                db: Session = Depends(get_db)):
    """API037 分配/转派（仅本部门主管/管理员，须记录原因）"""
    with with_business_transaction(db):
        result = crm_service.assign_lead(
            db, user, lead_id, owner_user_id=data.owner_user_id,
            expected_version=data.expected_version, reason=data.reason,
            request_key=data.request_key)
    return ok(result)


@router.get("/api/v1/employees/leads/{lead_id}/follow-ups")
def list_follow_ups(lead_id: int,
                    user: SysUser = Depends(require_password_changed),
                    db: Session = Depends(get_db),
                    page: int = Query(1, ge=1),
                    page_size: int = Query(20, ge=1, le=100)):
    """API038 跟进历史（客户详情同权限）"""
    items, total = crm_service.list_follow_ups(
        db, user, lead_id, page=page, page_size=page_size)
    return ok(paged([i.model_dump(mode="json") for i in items], page, page_size, total))


@router.post("/api/v1/employees/leads/{lead_id}/follow-ups", status_code=201)
def add_follow_up(lead_id: int, data: FollowUpIn,
                  user: SysUser = Depends(require_password_changed),
                  db: Session = Depends(get_db)):
    """API039 写联系记录/下次计划（同事务更新客户当前计划）"""
    with with_business_transaction(db):
        result = crm_service.add_follow_up(db, user, lead_id, data)
    return ok(result)


@router.post("/api/v1/employees/leads/{lead_id}/status")
def update_lead_status(lead_id: int, data: LeadTransitionIn,
                       user: SysUser = Depends(require_password_changed),
                       db: Session = Depends(get_db)):
    """API040 流失/恢复/开始跟进（SIGNED 仅转化入口可设置）"""
    with with_business_transaction(db):
        result = crm_service.transition_lead(db, user, lead_id, data)
    return ok(result)


# =============================================================
# M2：研判与简历提取（保持不变）
# =============================================================
@router.post("/api/v1/employees/leads/{lead_id}/assessments", status_code=201)
def assess_lead(lead_id: int,
                data: AssessmentIn,
                user: SysUser = Depends(require_password_changed),
                db: Session = Depends(get_db)):
    """API041 执行研判（M2）"""
    return ok(assessment_service.assess_lead(db, user, lead_id, data))


@router.get("/api/v1/employees/leads/{lead_id}/assessment")
def get_lead_assessment(lead_id: int,
                        user: SysUser = Depends(require_password_changed),
                        db: Session = Depends(get_db)):
    """API042 取最近一份研判报告（M2）"""
    return ok(assessment_service.get_assessment(db, user, lead_id))


@router.post("/api/v1/employees/leads/{lead_id}/assessment/accept")
def accept_extracted_facts(lead_id: int,
                           user: SysUser = Depends(require_password_changed),
                           db: Session = Depends(get_db)):
    """采纳研判提取的画像事实到客户主档（AI 提取 → 顾问核对确认）"""
    with with_business_transaction(db):
        dto = crm_service.accept_extracted_facts(db, user, lead_id)
    return ok(dto.model_dump(mode="json"))


# =============================================================
# M3：签约转学生
# =============================================================
@router.post("/api/v1/employees/leads/{lead_id}/conversion", status_code=201)
def convert_lead(lead_id: int, data: ConversionIn,
                 user: SysUser = Depends(require_password_changed),
                 db: Session = Depends(get_db)):
    """API043 确认线下签约并转学生（5 表原子事务，临时密码仅首次返回）"""
    with with_business_transaction(db):
        result = crm_service.convert_to_student(db, user, lead_id, data)
    return ok(result)


# =============================================================
# M2：简历提取（保持不变）
# =============================================================
@router.post("/api/v1/employees/leads/{lead_id}/resume-extraction")
def extract_resume(lead_id: int,
                   data: ResumeExtractionIn,
                   user: SysUser = Depends(require_password_changed),
                   db: Session = Depends(get_db)):
    """API096 简历文本/文件解析（M2）"""
    return ok(assessment_service.extract_resume_draft(db, user, lead_id, data))
