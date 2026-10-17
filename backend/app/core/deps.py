"""
公共依赖（M1-04）：从请求里取出当前登录人

get_actor(token) 的核心逻辑：
  1. 取 Authorization 头里的令牌
  2. 解令牌，拿 user_id 和 token_version
  3. 查数据库，看用户还在不在、有没有被禁用
  4. **比对 token_version** —— 不一致说明改过密码，旧令牌作废
  5. 返回当前用户

这是"身份是第一道门"的落地：所有要登录的接口都 Depends(get_current_user)。
"""
from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.errors import (
    AuthRequiredError,
    ForbiddenError,
    TokenExpiredError,
)
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import SysUser


def _extract_token(authorization: str | None) -> str:
    """从 'Bearer xxx' 里取出令牌。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthRequiredError("缺少登录令牌")
    return authorization[7:].strip()


def get_actor(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> SysUser:
    """取当前登录用户。token 无效一律 401。"""
    token = _extract_token(authorization)

    payload = decode_token(token)
    if payload is None:
        raise TokenExpiredError("登录已失效，请重新登录")

    try:
        user_id = int(payload["sub"])
        if user_id<1 or not isinstance(payload.get("tv"),int):raise ValueError()
    except (ValueError,TypeError,KeyError):raise TokenExpiredError("登录令牌无效")
    token_tv = payload.get("tv")

    user = db.get(SysUser, user_id)
    if user is None:
        raise AuthRequiredError("账号不存在")

    # 禁用账号：即使令牌有效也拒绝
    if user.status != "NORMAL":
        raise ForbiddenError("账号已被禁用")

    # ⚠️ 令牌版本比对：改密/权限变更后 token_version 会 +1，旧令牌立刻失效
    if token_tv != user.token_version:
        raise TokenExpiredError("登录状态已变更，请重新登录")

    return user


def require_password_changed(user: SysUser = Depends(get_actor)) -> SysUser:
    """已登录 + 必须已改过初始密码。

    首次登录（must_change_password=True）时，除改密外的接口一律拒绝。
    """
    if user.must_change_password:
        raise ForbiddenError("请先修改初始密码")
    return user
