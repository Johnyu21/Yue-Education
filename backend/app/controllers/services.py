"""
行政服务 —— 请假 / 考务申请与审批

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

router = APIRouter(tags=["行政服务"])


def _todo(api: str, who: str = "M4"):
    raise NotImplementedYetError(f"{api} 尚未实现（负责人：{who}）")


@router.get("/api/v1/services")
def list_services(user: SysUser = Depends(require_password_changed),
                  db: Session = Depends(get_db)):
    """API050 行政申请列表（学生看自己，员工看授权范围）"""
    _todo("API050")


@router.get("/api/v1/services/{service_id}")
def get_service(service_id: int, user: SysUser = Depends(require_password_changed),
                db: Session = Depends(get_db)):
    """API051 申请详情（scope.get_or_404）"""
    _todo("API051")


@router.post("/api/v1/services")
def create_service(user: SysUser = Depends(require_password_changed),
                   db: Session = Depends(get_db)):
    """API052 提交请假/考务

    ⚠️ LEAVE 必须 start_at < end_at（数据库会拒）
    ⚠️ 若由助手提议 → 校验 confirmation_token（ⓒ）
    """
    _todo("API052")


@router.post("/api/v1/services/{service_id}/cancel")
def cancel_service(service_id: int,
                   user: SysUser = Depends(require_password_changed),
                   db: Session = Depends(get_db)):
    """API053 撤销申请（仅待审批状态可撤销）"""
    _todo("API053")


@router.post("/api/v1/services/{service_id}/decision")
def decide_service(service_id: int,
                   user: SysUser = Depends(require_password_changed),
                   db: Session = Depends(get_db)):
    """API054 审批请假/考务（ⓥⓒ）

    ⚠️ 状态更新 + 写通知 必须在同一事务
    ⚠️ 重复审批要返回 409（乐观锁兜）
    """
    _todo("API054")


@router.post("/api/v1/services/{service_id}/assignment")
def assign_service(service_id: int,
                   user: SysUser = Depends(require_password_changed),
                   db: Session = Depends(get_db)):
    """API055 指派处理人"""
    _todo("API055")


# ---------------- 骨架补齐（z 审核时发现遗漏）----------------

