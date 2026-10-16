"""
智能助手 —— 员工助手 / 学生助手 / 语音转写

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

router = APIRouter(tags=["智能助手"])


def _todo(api: str, who: str = "M3/M4"):
    raise NotImplementedYetError(f"{api} 尚未实现（负责人：{who}）")


@router.post("/api/v1/assistants/employee/messages")
def employee_assistant(user: SysUser = Depends(require_password_changed),
                       db: Session = Depends(get_db)):
    """API029 企业助手（受控意图，不直接写库）"""
    _todo("API029")


@router.post("/api/v1/assistants/student/messages")
def student_assistant(user: SysUser = Depends(require_password_changed),
                      db: Session = Depends(get_db)):
    """API030 学生助手（受控意图，写操作要返回提议 + confirmation_token）"""
    _todo("API030", "M3/M4")


@router.post("/api/v1/transcriptions")
def transcribe(user: SysUser = Depends(require_password_changed)):
    """API031 语音转写（ASR）"""
    _todo("API031")


# ---------------- 售后工单（员工侧）----------------

