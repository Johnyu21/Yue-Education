"""
员工日报 —— 日报草稿 / 提交 / 退回 / 查看

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

router = APIRouter(tags=["员工日报"])


def _todo(api: str, who: str = "M3"):
    raise NotImplementedYetError(f"{api} 尚未实现（负责人：{who}）")


@router.get("/api/v1/me/daily-reports")
def my_daily_reports(user: SysUser = Depends(require_password_changed),
                     db: Session = Depends(get_db)):
    """API082 我的日报"""
    _todo("API082")


@router.put("/api/v1/me/daily-reports/{report_date}")
def save_daily_report(report_date: str,
                      user: SysUser = Depends(require_password_changed),
                      db: Session = Depends(get_db)):
    """API083 保存日报草稿（一人一天一份，重复提交是更新）"""
    _todo("API083")


@router.post("/api/v1/me/daily-reports/{report_date}/ai-draft")
def ai_draft_daily_report(report_date: str,
                          user: SysUser = Depends(require_password_changed)):
    """API084 AI 生成日报草稿（⚠️ 不写库，返回草稿让用户确认）"""
    _todo("API084")


@router.post("/api/v1/me/daily-reports/{report_id}/submit")
def submit_daily_report(report_id: int,
                        user: SysUser = Depends(require_password_changed),
                        db: Session = Depends(get_db)):
    """API085 提交日报"""
    _todo("API085")


@router.post("/api/v1/employees/daily-reports/{report_id}/return")
def return_daily_report(report_id: int,
                        user: SysUser = Depends(require_password_changed),
                        db: Session = Depends(get_db)):
    """API086 退回日报（主管）"""
    _todo("API086")


@router.get("/api/v1/employees/daily-reports")
def list_daily_reports(user: SysUser = Depends(require_password_changed),
                       db: Session = Depends(get_db)):
    """API087 查看本部门日报（主管）"""
    _todo("API087")


# ---------------- 工作台 ----------------

