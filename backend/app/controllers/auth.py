"""
认证接口（M1-04）

API003 登录        POST /api/v1/auth/login
API004 当前身份    GET  /api/v1/auth/me
API005 自主改密    POST /api/v1/auth/change-password
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_actor
from app.core.responses import ok
from app.db.session import get_db
from app.models.user import SysUser
from app.schemas.auth import ChangePasswordIn, LoginIn, LoginOut, UserOut
from app.services import auth_service

router = APIRouter(prefix="/api/v1/auth", tags=["认证"])


def to_user_out(u: SysUser) -> dict:
    """model → 接口输出。id 转字符串，防 JS 精度丢失。"""
    return UserOut(
        id=str(u.id),
        username=u.username,
        realName=u.real_name,
        userType=u.user_type,
        employeeRole=u.employee_role,
        deptId=str(u.dept_id) if u.dept_id else None,
        mustChangePassword=u.must_change_password,
    ).model_dump()


@router.post("/login")
def login(data: LoginIn, db: Session = Depends(get_db)):
    """API003 登录。"""
    user = auth_service.authenticate(db, data.username, data.password)
    token, expires_in = auth_service.issue_token(user)
    out = LoginOut(
        accessToken=token,
        expiresIn=expires_in,
        user=UserOut(**to_user_out(user)),
    )
    return ok(out.model_dump())


@router.get("/me")
def me(user: SysUser = Depends(get_actor)):
    """API004 当前身份与能力。前端据此决定显示哪个界面。"""
    return ok(to_user_out(user))


@router.post("/change-password")
def change_password(
    data: ChangePasswordIn,
    user: SysUser = Depends(get_actor),
    db: Session = Depends(get_db),
):
    """API005 自主改密 / 首次改密。

    改完旧令牌立即失效，用户需要用新密码重新登录。
    """
    auth_service.change_password(db, user, data.old_password, data.new_password)
    return ok({"changed": True, "message": "密码已修改，请用新密码重新登录"})
