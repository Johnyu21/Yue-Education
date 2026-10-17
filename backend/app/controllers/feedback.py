"""
售后工单 —— 投诉 / 建议 / 咨询工单
"""
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.confirmation import verify_confirmation
from app.core.deps import require_password_changed
from app.core.responses import ok
from app.core.transaction import with_business_transaction
from app.db.session import get_db
from app.models.user import SysUser
from app.schemas.common import VersionReasonRequest, VersionRequest, paged
from app.schemas.feedback import FeedbackCreateRequest, FeedbackHandlingRequest, RatingRequest
from app.services import feedback_service, m3_canonical, staff_feedback_service

router = APIRouter(tags=["售后工单"])


@router.get("/api/v1/me/feedback-tickets")
def my_feedback_tickets(user: SysUser = Depends(require_password_changed),
                        db: Session = Depends(get_db),
                        page: int = Query(1, ge=1),
                        page_size: int = Query(20, ge=1, le=100),
                        status_: str | None = Query(None, alias="status")):
    """API056 我的工单"""
    items, total = feedback_service.list_my_tickets(
        db, user, status=status_, page=page, page_size=page_size)
    return ok({"items": [i.model_dump(mode="json") for i in items],
               "page": page, "pageSize": page_size, "total": total})


@router.post("/api/v1/me/feedback-tickets", status_code=201)
def create_feedback_ticket(data: FeedbackCreateRequest,
                           user: SysUser = Depends(require_password_changed),
                           db: Session = Depends(get_db)):
    """API057 提交投诉/建议（priority 由后端决定，学生不传）"""
    with with_business_transaction(db):
        dto = feedback_service.submit_feedback(db, user, data)
    return ok(dto.model_dump(mode="json"))


@router.get("/api/v1/me/feedback-tickets/{ticket_id}")
def get_feedback_ticket(ticket_id: int,
                        user: SysUser = Depends(require_password_changed),
                        db: Session = Depends(get_db)):
    """API058 工单详情（学生只看自己的）"""
    dto = feedback_service.get_my_ticket(db, user, ticket_id)
    return ok(dto.model_dump(mode="json"))


@router.post("/api/v1/me/feedback-tickets/{ticket_id}/confirm")
def confirm_feedback_ticket(ticket_id: int, data: VersionRequest,
                            user: SysUser = Depends(require_password_changed),
                            db: Session = Depends(get_db)):
    """API063 学生确认解决并关闭"""
    with with_business_transaction(db):
        dto = feedback_service.confirm_feedback(
            db, user, ticket_id, expected_version=data.expected_version,
            request_key=data.request_key)
    return ok(dto.model_dump(mode="json"))


@router.post("/api/v1/me/feedback-tickets/{ticket_id}/reopen")
def reopen_feedback_ticket(ticket_id: int, data: VersionReasonRequest,
                           user: SysUser = Depends(require_password_changed),
                           db: Session = Depends(get_db)):
    """API064 不认可，RESOLVED → PROCESSING（保留前次解决记录）"""
    with with_business_transaction(db):
        dto = feedback_service.reopen_feedback(
            db, user, ticket_id, expected_version=data.expected_version,
            request_key=data.request_key, reason=data.reason)
    return ok(dto.model_dump(mode="json"))


@router.post("/api/v1/me/feedback-tickets/{ticket_id}/rating")
def rate_feedback_ticket(ticket_id: int, data: RatingRequest,
                         user: SysUser = Depends(require_password_changed),
                         db: Session = Depends(get_db)):
    """API065 满意度评价 1~5 分"""
    with with_business_transaction(db):
        result = feedback_service.rate_feedback(db, user, ticket_id, data)
    return ok(result)


# ---------------- 员工侧（M3 控制器，业务函数已就绪）----------------


@router.get("/api/v1/employees/feedback-tickets")
def list_feedback_tickets(user: SysUser = Depends(require_password_changed),
                          db: Session = Depends(get_db),
                          page: int = Query(1, ge=1),
                          page_size: int = Query(20, ge=1, le=100),
                          status_: str | None = Query(None, alias="status"),
                          assignee: str | None = Query(None, description="me / pool"),
                          category: str | None = Query(None)):
    """API059 售后池与受理列表（需售后授权，部门范围）"""
    items, total = staff_feedback_service.list_staff_tickets(
        db, user, status=status_, assignee=assignee, category=category,
        page=page, page_size=page_size)
    return ok(paged(items, page, page_size, total))


@router.get("/api/v1/employees/feedback-tickets/{ticket_id}")
def get_feedback_ticket_employee(ticket_id: int,
                                 user: SysUser = Depends(require_password_changed),
                                 db: Session = Depends(get_db)):
    """API060 售后详情（需售后授权；部门范围外 404）"""
    return ok(staff_feedback_service.get_staff_ticket(db, user, ticket_id))


@router.post("/api/v1/employees/feedback-tickets/{ticket_id}/claim")
def claim_feedback_ticket(ticket_id: int, data: VersionRequest,
                          user: SysUser = Depends(require_password_changed),
                          db: Session = Depends(get_db)):
    """API061 售后认领（M3 调 M4 业务函数）"""
    with with_business_transaction(db):
        dto = feedback_service.claim_feedback(
            db, user, ticket_id, expected_version=data.expected_version,
            request_key=data.request_key)
    return ok(dto.model_dump(mode="json"))


@router.post("/api/v1/employees/feedback-tickets/{ticket_id}/handling")
def handle_feedback_ticket(ticket_id: int, data: FeedbackHandlingRequest,
                           user: SysUser = Depends(require_password_changed),
                           db: Session = Depends(get_db)):
    """API062 售后跟进/解决/转派（M3 调 M4 业务函数）"""
    if data.confirmation_token:
        verify_confirmation(user, data.confirmation_token, operation="HANDLE_FEEDBACK",
                            entity_id=ticket_id,
                            payload=m3_canonical.feedback_handling_payload(data),
                            expected_version=data.expected_version, request_key=data.request_key)
    with with_business_transaction(db):
        dto = feedback_service.handle_feedback(db, user, ticket_id, data)
    return ok(dto.model_dump(mode="json"))
