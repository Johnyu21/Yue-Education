"""
售后工单 —— 投诉 / 建议 / 咨询工单
"""
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import require_password_changed
from app.core.errors import NotImplementedYetError
from app.core.responses import ok
from app.core.transaction import with_business_transaction
from app.db.session import get_db
from app.models.user import SysUser
from app.schemas.common import VersionReasonRequest, VersionRequest
from app.schemas.feedback import FeedbackCreateRequest, RatingRequest
from app.services import feedback_service

router = APIRouter(tags=["售后工单"])


def _todo(api: str, who: str = "M3/M4"):
    raise NotImplementedYetError(f"{api} 尚未实现（负责人：{who}）")


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
                          db: Session = Depends(get_db)):
    """API059 工单列表（M3）"""
    _todo("API059", "M3")


@router.get("/api/v1/employees/feedback-tickets/{ticket_id}")
def get_feedback_ticket_employee(ticket_id: int,
                                 user: SysUser = Depends(require_password_changed),
                                 db: Session = Depends(get_db)):
    """API060 工单详情（M3，需售后授权）"""
    _todo("API060", "M3")


@router.post("/api/v1/employees/feedback-tickets/{ticket_id}/claim")
def claim_feedback_ticket(ticket_id: int,
                          user: SysUser = Depends(require_password_changed),
                          db: Session = Depends(get_db)):
    """API061 认领工单（M3，业务函数 feedback_service.claim_feedback 已就绪）"""
    _todo("API061", "M3")


@router.post("/api/v1/employees/feedback-tickets/{ticket_id}/handling")
def handle_feedback_ticket(ticket_id: int,
                           user: SysUser = Depends(require_password_changed),
                           db: Session = Depends(get_db)):
    """API062 处理工单（M3，业务函数 feedback_service.handle_feedback 已就绪）"""
    _todo("API062", "M3")
