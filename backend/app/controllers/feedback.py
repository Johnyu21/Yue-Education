"""
售后工单 —— 投诉 / 建议 / 咨询工单

⚠️ 实现要求：
  1. 统一响应：return ok(data)；报错抛 app.core.errors 里的异常类
  2. 需登录：Depends(require_password_changed)
  3. 查数据：用 build_scope(db, user, purpose) 限制范围（M1-05）
  4. 多表写：用 with_business_transaction（M1-S1）
  5. AI 调用**放事务外**（M1-S1）
  6. 每个接口下有 API 编号注释
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_password_changed
from app.core.errors import NotImplementedYetError
from app.core.responses import ok
from app.db.session import get_db
from app.models.user import SysUser

router = APIRouter(tags=["售后工单"])


def _todo(api: str, who: str = "M3/M4"):
    raise NotImplementedYetError(f"{api} 尚未实现（负责人：{who}）")


@router.get("/api/v1/me/feedback-tickets")
def my_feedback_tickets(user: SysUser = Depends(require_password_changed),
                        db: Session = Depends(get_db)):
    """API056 我的工单"""
    _todo("API056")


@router.post("/api/v1/me/feedback-tickets")
def create_feedback_ticket(user: SysUser = Depends(require_password_changed),
                           db: Session = Depends(get_db)):
    """API057 提交投诉/建议

    ⚠️ priority 由后端按 category 决定（COMPLAINT→HIGH），**不接受客户端传入**
    """
    _todo("API057")


@router.get("/api/v1/me/feedback-tickets/{ticket_id}")
def get_feedback_ticket(ticket_id: int,
                        user: SysUser = Depends(require_password_changed),
                        db: Session = Depends(get_db)):
    """API058 工单详情（学生只看自己的）"""
    _todo("API058")


@router.get("/api/v1/employees/feedback-tickets")
def list_feedback_tickets(user: SysUser = Depends(require_password_changed),
                          db: Session = Depends(get_db)):
    """API059 工单列表 —— ⚠️ 先查 can_handle_feedback，再按范围"""
    _todo("API059")


@router.get("/api/v1/employees/feedback-tickets/{ticket_id}")
def get_feedback_ticket(ticket_id: int,
                        user: SysUser = Depends(require_password_changed),
                        db: Session = Depends(get_db)):
    """API060 工单详情（需售后授权）"""
    _todo("API060")


@router.post("/api/v1/employees/feedback-tickets/{ticket_id}/claim")
def claim_feedback_ticket(ticket_id: int,
                          user: SysUser = Depends(require_password_changed),
                          db: Session = Depends(get_db)):
    """API061 认领工单"""
    _todo("API061")


@router.post("/api/v1/employees/feedback-tickets/{ticket_id}/handling")
def handle_feedback_ticket(ticket_id: int,
                           user: SysUser = Depends(require_password_changed),
                           db: Session = Depends(get_db)):
    """API062 处理工单（ⓥⓒ）

    ⚠️ RESOLVE 必填 resolution；状态与通知同事务（否则学生收不到）
    """
    _todo("API062")


# ---------------- 申请单维护 ----------------


@router.post("/api/v1/me/feedback-tickets/{ticket_id}/confirm")
def confirm_feedback_ticket(ticket_id: int,
                            user: SysUser = Depends(require_password_changed),
                            db: Session = Depends(get_db)):
    """API063 学生确认关闭（写 closed_at）"""
    _todo("API063")


@router.post("/api/v1/me/feedback-tickets/{ticket_id}/reopen")
def reopen_feedback_ticket(ticket_id: int,
                           user: SysUser = Depends(require_password_changed),
                           db: Session = Depends(get_db)):
    """API064 不认可，RESOLVED → PROCESSING（保留前次解决记录）"""
    _todo("API064")


@router.post("/api/v1/me/feedback-tickets/{ticket_id}/rating")
def rate_feedback_ticket(ticket_id: int,
                         user: SysUser = Depends(require_password_changed),
                         db: Session = Depends(get_db)):
    """API065 满意度评价 1~5 分"""
    _todo("API065")

