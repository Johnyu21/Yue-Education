"""
数据范围 Scope（M1-05）—— 权限的核心

作用：算出"当前登录人能看哪些数据"，并把过滤条件加到查询里。

⚠️ 核心原则（防越权的关键）：
    **在查询阶段就过滤，不是查出来再筛。**
    错误做法：先查全表 → 在 Python 里 if 判断 → 越权数据已经出了数据库
    正确做法：把条件写进 SQL 的 WHERE → 数据库层就不返回不该看的

用法：
    scope = build_scope(user, 'lead')
    if not scope.can_see(obj):  # 按 id 取详情时：不在范围内 → 抛 404
        raise NotFoundError()
    stmt = scope.apply(select(CrmLead))   # 列表查询：自动加 WHERE
"""
from dataclasses import dataclass

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.core.errors import NotFoundError
from app.models.organization import SysClass, SysDepartment
from app.models.user import SysUser


# 用途（不同业务查不同字段，但规则一致）
PURPOSE_FIELD = {
    "lead": "owner_user_id",              # 线索：看负责顾问
    "student": "advisor_user_id",         # 学生：看负责顾问
    "admin_service": "dept_id",           # 行政服务：看部门
    "feedback": "assignee_user_id",       # 工单：看处理人
    "daily_report": "employee_user_id",   # 日报：看提交人
    "enrollment": "student_profile_id",   # 课程报名：跟随学生
    "score": "student_profile_id",        # 成绩：跟随学生
    "schedule": "student_profile_id",     # 日程：跟随学生
    "progress": "student_profile_id",     # 进度：跟随学生
    "psych": "student_profile_id",        # 心理：跟随学生（另有敏感标志）
}


@dataclass
class Scope:
    """一个登录人的数据范围。由 build_scope 生成，调用方不要自己 new。"""

    user: SysUser
    purpose: str
    is_admin: bool = False                  # 管理员：全域普通业务
    dept_ids: tuple[int, ...] = ()          # 主管：本部门（默认不含子部门）
    is_head_of: tuple[int, ...] = ()        # 我是主管的部门
    class_teacher_of: tuple[int, ...] = ()  # 我是班主任的班级
    own_field: str | None = None            # "本人"对应的字段名

    # ---------- 构造过滤条件 ----------
    def _conditions(self, model):
        """拼出 SQL 的 WHERE 条件。"""
        conds = []

        # 管理员：全域（但心理/投诉另有敏感标志，见 can_see_psych / can_see_feedback）
        if self.is_admin:
            conds.append(model.id.isnot(None))     # 永真：放宽到全表
        else:
            # 主管：本部门
            if self.dept_ids and hasattr(model, "dept_id"):
                conds.append(model.dept_id.in_(self.dept_ids))

            # 本人：负责的线索/学生
            if self.own_field and hasattr(model, self.own_field):
                conds.append(getattr(model, self.own_field) == self.user.id)

            # 待分配池（仅线索）：未分配客户（未路由∪本部门）对员工可见，
            # 与 crm_service._can_view_lead 的"顾问可看未路由客户"保持同一口径。
            if (self.purpose == "lead" and not self.user.is_student
                    and hasattr(model, "owner_user_id")):
                conds.append(and_(model.owner_user_id.is_(None),
                                  or_(model.dept_id.is_(None),
                                      model.dept_id == self.user.dept_id)))

            # 学生本人：只能看自己
            if self.user.is_student and hasattr(model, "student_profile_id"):
                conds.append(model.student_profile_id == self._my_profile_id())

        if not conds:
            # 没匹配到任何范围 → 返回"谁都不给"，绝不放开
            conds.append(model.id == -1)
        return or_(*conds)

    def _my_profile_id(self) -> int:
        """当前学生对应的 student_profile.id。"""
        return getattr(self, "_profile_id", -1)

    # ---------- 对外接口 ----------
    def apply(self, stmt: Select, model) -> Select:
        """把范围条件加到查询上。列表接口必须用它。"""
        return stmt.where(self._conditions(model))

    def can_see(self, obj) -> bool:
        """按 id 取详情时判断。不在范围 → False，调用方应抛 404。"""
        if self.is_admin:
            return True
        # 待分配池（仅线索）：未分配客户（未路由∪本部门）对员工可见，
        # 与 crm_service._can_view_lead 的"顾问可看未路由客户"保持同一口径。
        if (self.purpose == "lead" and not self.user.is_student
                and getattr(obj, "owner_user_id", None) is None):
            return getattr(obj, "dept_id", None) is None or getattr(obj, "dept_id", None) == self.user.dept_id
        # 主管：同部门
        if self.dept_ids and getattr(obj, "dept_id", None) in self.dept_ids:
            return True
        # 本人负责
        if self.own_field and getattr(obj, self.own_field, None) == self.user.id:
            return True
        # 学生本人
        if self.user.is_student and getattr(obj, "student_profile_id", None) == self._my_profile_id():
            return True
        return False

    def get_or_404(self, db: Session, model, obj_id: int):
        """取详情：存在且可见才返回，否则一律 404。

        ⚠️ 范围外也返回 404（不是 403）——避免暴露"这条数据存在"。
        """
        obj = db.get(model, obj_id)
        if obj is None or not self.can_see(obj):
            raise NotFoundError("资源不存在")
        return obj

    # ---------- 敏感标志 ----------
    def can_see_feedback(self) -> bool:
        """能否看投诉正文。管理员也不自动获得，要有 can_handle_feedback。"""
        return bool(self.user.can_handle_feedback)

    def can_see_psych(self) -> bool:
        """能否看心理数据。必须有 psych_access_enabled，管理员也不例外。"""
        return bool(self.user.psych_access_enabled)

    def can_modify_psych(self) -> bool:
        """能否人工改心理状态。要求主管/管理员 + 心理授权。"""
        return self.can_see_psych() and (
            self.is_admin or bool(self.is_head_of)
        )


def build_scope(db: Session, user: SysUser, purpose: str) -> Scope:
    """算出当前用户在这个用途下的数据范围。

    依据实时关系生成，**不接受调用方传 is_admin**（那等于让人自己声明权限）。
    """
    is_admin = user.employee_role == "ADMIN"

    # 主管：查 sys_department.head_user_id 是我 的部门（唯一事实源）
    head_of = tuple(
        db.scalars(select(SysDepartment.id).where(SysDepartment.head_user_id == user.id))
    )

    # 班主任：查 sys_class.head_teacher_id 是我 的班级
    teacher_of = tuple(
        db.scalars(select(SysClass.id).where(SysClass.head_teacher_id == user.id))
    )

    # 主管能看本部门数据
    dept_ids = head_of

    scope = Scope(
        user=user,
        purpose=purpose,
        is_admin=is_admin,
        dept_ids=dept_ids,
        is_head_of=head_of,
        class_teacher_of=teacher_of,
        own_field=PURPOSE_FIELD.get(purpose),
    )

    # 学生：找到他的档案 id
    if user.is_student:
        from app.models.student import StudentProfile
        pid = db.scalar(select(StudentProfile.id).where(StudentProfile.user_id == user.id))
        scope._profile_id = pid or -1

    return scope
