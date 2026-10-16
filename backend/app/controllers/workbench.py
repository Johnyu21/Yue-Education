"""
工作台 —— 待办

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

router = APIRouter(tags=["工作台"])


def _todo(api: str, who: str = "M3"):
    raise NotImplementedYetError(f"{api} 尚未实现（负责人：{who}）")


@router.get("/api/v1/workbench/todos")
def workbench_todos(user: SysUser = Depends(require_password_changed),
                    db: Session = Depends(get_db)):
    """API088 待办列表

    ⚠️ 实时查询（不建待办表）：待审批请假、待跟进线索、待处理工单
    """
    _todo("API088")


# ---------------- 骨架补齐（z 审核时发现遗漏）----------------

