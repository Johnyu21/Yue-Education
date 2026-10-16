"""
心理关怀 —— 授权 / 观测 / 预警处置

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

router = APIRouter(tags=["心理关怀"])


def _todo(api: str, who: str = "M4"):
    raise NotImplementedYetError(f"{api} 尚未实现（负责人：{who}）")


@router.put("/api/v1/me/psych-consent")
def set_psych_consent(user: SysUser = Depends(require_password_changed),
                      db: Session = Depends(get_db)):
    """API066 心理授权同意 / 撤回

    ⚠️ 授权状态 GRANTED 时必须同时写 consent_at + consent_version
    """
    _todo("API066")


@router.get("/api/v1/employees/psych/students")
def list_psych_students(user: SysUser = Depends(require_password_changed),
                        db: Session = Depends(get_db)):
    """API067 可查看心理的学生列表（⚠️ 需 can_see_psych；班主任看本班、顾问看本人学生）"""
    _todo("API067", "M3/M4")


@router.get("/api/v1/employees/students/{student_id}/psych-observations")
def psych_observations(student_id: int,
                       user: SysUser = Depends(require_password_changed),
                       db: Session = Depends(get_db)):
    """API068 心理观测（⚠️ 必须 can_see_psych + 班主任/顾问/主管/管理员）"""
    _todo("API068")


@router.post("/api/v1/employees/students/{student_id}/psych-corrections")
def psych_correction(student_id: int,
                     user: SysUser = Depends(require_password_changed),
                     db: Session = Depends(get_db)):
    """API069 人工修正情绪标签（⚠️ 仅主管/管理员 + 心理授权）"""
    _todo("API069")


@router.get("/api/v1/employees/psych-alerts")
def list_psych_alerts(user: SysUser = Depends(require_password_changed),
                      db: Session = Depends(get_db)):
    """API070 预警列表（⚠️ 需 can_see_psych）"""
    _todo("API070")


@router.get("/api/v1/employees/psych-alerts/{alert_id}")
def get_psych_alert(alert_id: int,
                    user: SysUser = Depends(require_password_changed),
                    db: Session = Depends(get_db)):
    """API071 预警详情"""
    _todo("API071")


@router.post("/api/v1/employees/psych-alerts/{alert_id}/actions")
def psych_alert_action(alert_id: int,
                       user: SysUser = Depends(require_password_changed),
                       db: Session = Depends(get_db)):
    """API072 预警处置（ⓥⓒ）

    ⚠️ 必须人工确认；DISMISSED/CLOSED 要填 closed_at + action_note
    ⚠️ 同一学生同时只能有一个未关闭预警（部分唯一索引）
    """
    _todo("API072")


# ---------------- 审批 ----------------

