"""
认证相关的输入输出结构（M1-04）

schema 负责"接口传什么"，和 model（数据库存什么）分开。
"""
from app.core.dto import BaseModel
from pydantic import Field


# ---- 请求 ----
class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=128)


class ChangePasswordIn(BaseModel):
    old_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)   # 至少 8 位


# ---- 响应 ----
class UserOut(BaseModel):
    """当前用户信息。注意 id 是字符串（防 JS 精度丢失）。"""
    id: str
    username: str
    realName: str
    userType: str                       # STUDENT / EMPLOYEE
    employeeRole: str | None = None
    deptId: str | None = None
    mustChangePassword: bool = False
    version: int = 1
    isAdmin: bool = False
    isDeptHead: bool = False
    headOfDepartmentIds: list[str] = []
    classTeacherOfIds: list[str] = []
    canHandleFeedback: bool = False
    psychAccessEnabled: bool = False


class LoginOut(BaseModel):
    accessToken: str
    tokenType: str = "Bearer"
    expiresIn: int
    user: UserOut
