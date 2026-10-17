"""
行政服务 —— 请假 / 考务申请与审批
"""
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import require_password_changed
from app.core.responses import ok
from app.core.transaction import with_business_transaction
from app.db.session import get_db
from app.models.user import SysUser
from app.schemas.common import VersionReasonRequest
from app.schemas.service import ServiceCreateRequest, ServiceDecisionRequest
from app.schemas.workbench import ServiceAssignmentIn
from app.services import student_service

router = APIRouter(tags=["行政服务"])


@router.get("/api/v1/services")
def list_services(user: SysUser = Depends(require_password_changed),
                  db: Session = Depends(get_db),
                  page: int = Query(1, ge=1),
                  page_size: int = Query(20, ge=1, le=100),
                  status_: str | None = Query(None, alias="status"),
                  service_type: str | None = Query(None)):
    """API050 行政申请列表（学生看自己，员工看授权范围）"""
    items, total = student_service.list_services(
        db, user, status=status_, service_type=service_type, page=page, page_size=page_size)
    return ok({"items": [i.model_dump(mode="json") for i in items],
               "page": page, "pageSize": page_size, "total": total})


@router.get("/api/v1/services/{service_id}")
def get_service(service_id: int, user: SysUser = Depends(require_password_changed),
                db: Session = Depends(get_db)):
    """API051 申请详情（scope 过滤，范围外 404）"""
    dto = student_service.get_service(db, user, service_id)
    return ok(dto.model_dump(mode="json"))


@router.post("/api/v1/services", status_code=201)
def create_service(data: ServiceCreateRequest,
                   user: SysUser = Depends(require_password_changed),
                   db: Session = Depends(get_db)):
    """API052 提交请假/考务（学生确认提交）"""
    with with_business_transaction(db):
        result = student_service.submit_service(db, user, data)
    return ok(result)


@router.post("/api/v1/services/{service_id}/cancel")
def cancel_service(service_id: int, data: VersionReasonRequest,
                   user: SysUser = Depends(require_password_changed),
                   db: Session = Depends(get_db)):
    """API053 撤销申请（仅本人 PENDING 可撤销）"""
    with with_business_transaction(db):
        result = student_service.cancel_service(
            db, user, service_id, expected_version=data.expected_version,
            request_key=data.request_key, reason=data.reason)
    return ok(result)


@router.post("/api/v1/services/{service_id}/decision")
def decide_service(service_id: int, data: ServiceDecisionRequest,
                   user: SysUser = Depends(require_password_changed),
                   db: Session = Depends(get_db)):
    """API054 审批请假/考务/信息修改（M3 调 M4 业务函数）"""
    with with_business_transaction(db):
        dto = student_service.decide_service(db, user, service_id, data)
    return ok(dto.model_dump(mode="json"))


@router.post("/api/v1/services/{service_id}/assignment")
def assign_service(service_id: int, data: ServiceAssignmentIn,
                   user: SysUser = Depends(require_password_changed),
                   db: Session = Depends(get_db)):
    """API055 主管转派待审单（M3 调 M4 业务函数）"""
    with with_business_transaction(db):
        dto = student_service.assign_service(
            db, user, service_id,
            assignee_user_id=data.assignee_user_id,
            expected_version=data.expected_version,
            reason=data.reason, request_key=data.request_key)
    return ok(dto.model_dump(mode="json"))
