"""
组织管理相关的输入结构（M1-06）

⚠️ DTO 白名单：只声明允许客户端传入的字段。
   权限相关字段（employee_role 变更等）走单独的、受控的接口。
"""
from pydantic import BaseModel, Field


# ---- 部门 ----
class DepartmentCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=100)
    parent_id: int | None = None


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    parent_id: int | None = None
    head_user_id: int | None = None       # 指定主管


# ---- 班级 ----
class ClassCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=80)
    dept_id: int
    course_type: str | None = Field(default=None, max_length=80)
    head_teacher_id: int | None = None


class ClassUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    course_type: str | None = Field(default=None, max_length=80)
    head_teacher_id: int | None = None


# ---- 员工账号 ----
class EmployeeCreate(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    real_name: str = Field(min_length=1, max_length=80)
    employee_role: str = Field(pattern="^(NEWCOMER|ADVISOR|SENIOR_ADVISOR|ADMIN)$")
    dept_id: int | None = None
    contact_info: str | None = Field(default=None, max_length=160)


class UserUpdate(BaseModel):
    """⚠️ 能改的字段白名单。不允许改 username / password_hash。"""
    real_name: str | None = Field(default=None, max_length=80)
    contact_info: str | None = Field(default=None, max_length=160)
    dept_id: int | None = None
    status: str | None = Field(default=None, pattern="^(NORMAL|DISABLED)$")
    can_handle_feedback: bool | None = None      # ⚠️ 敏感能力
    psych_access_enabled: bool | None = None     # ⚠️ 敏感能力
