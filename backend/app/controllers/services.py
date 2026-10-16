"""
行政服务 —— 请假 / 考务申请与审批
"""
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import require_password_changed
from app.core.errors import NotImplementedYetError
from app.core.responses import ok
from app.core.transaction import with_business_transaction
from app.db.session import get_db
from app.models.user import SysUser
from app.schemas.common import VersionReasonRequest
from app.schemas.service import ServiceCreateRequest
from app.services import student_service

router = APIRouter(tags=["行政服务"])


def _todo(api: str, who: str = "M4"):
    raise NotImplementedYetError(f"{api} 尚未实现（负责人：{who}）")


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
def decide_service(service_id: int,
                   user: SysUser = Depends(require_password_changed),
                   db: Session = Depends(get_db)):
    """API054 审批请假/考务（M3，业务函数 student_service.decide_service 已就绪）"""
    _todo("API054", "M3")


@router.post("/api/v1/services/{service_id}/assignment")
def assign_service(service_id: int,
                   user: SysUser = Depends(require_password_changed),
                   db: Session = Depends(get_db)):
    """API055 指派处理人（M3，业务函数 student_service.assign_service 已就绪）"""
    _todo("API055", "M3")
