"""
心理预警处置的 M3 控制器层权限兜底

背景：M4 的 review_alert 用 employee_role ∈ (ADVISOR, SENIOR_ADVISOR, ADMIN) 判断
      "主管/管理员"，但设计 D04 规定"主管由 sys_department.head_user_id 派生，
      主管仍保留顾问身份"。若照 M4 现状，任何有心理授权的普通顾问都能复核/终结风险。

本模块只在 M3 的 API072 调用前加一道"部门主管或管理员"的兜底校验，
不改 M4 文件；同时把该缺陷反馈给 M4 负责人正式修复。
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.organization import SysDepartment
from app.models.psych import StudentPsychAlert
from app.models.student import StudentProfile
from app.models.user import SysUser
from app.services.m3_errors import CapabilityDeniedError

_NOTE_ACTION = "NOTE"


def guard_alert_action(db: Session, actor: SysUser, alert_id: int, action: str) -> None:
    """NOTE 由 M4 校验跟进关系；其余动作要求 心理授权 + (部门主管 或 管理员)。"""
    if action == _NOTE_ACTION:
        return

    if not actor.psych_access_enabled:
        raise CapabilityDeniedError("需要心理数据授权")

    alert = db.get(StudentPsychAlert, alert_id)
    if alert is None:
        raise NotFoundError("资源不存在")

    if actor.employee_role == "ADMIN":
        return

    profile = db.get(StudentProfile, alert.student_profile_id)
    if profile is None:
        raise NotFoundError("资源不存在")

    is_head = db.scalar(select(SysDepartment.id).where(
        SysDepartment.id == profile.dept_id,
        SysDepartment.head_user_id == actor.id)) is not None
    if not is_head:
        raise CapabilityDeniedError("仅主管部门或管理员可复核/终结预警")
