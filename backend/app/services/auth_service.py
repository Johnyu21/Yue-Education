"""
认证业务逻辑（M1-04）

事务规则：一次业务写入 = 一个事务。这里都是简单写，直接 commit。
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import (
    AuthRequiredError,
    ForbiddenError,
    InvalidRequestError,
    StateConflictError,
)
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.user import SysUser


def authenticate(db: Session, username: str, password: str) -> SysUser:
    """登录校验。用户名或密码错，统一提示（不透露是哪个错）。"""
    user = db.scalar(select(SysUser).where(SysUser.username == username))
    if user is None or not verify_password(password, user.password_hash):
        raise AuthRequiredError("用户名或密码错误")

    if user.status != "NORMAL":
        raise ForbiddenError("账号已被禁用")

    # 临时密码过期检查
    if user.must_change_password and user.temporary_password_expires_at:
        if datetime.now(timezone.utc) > user.temporary_password_expires_at:
            raise ForbiddenError("初始密码已过期，请联系管理员重置")

    return user


def issue_token(user: SysUser) -> tuple[str, int]:
    """签发令牌，返回 (token, 有效秒数)。"""
    token = create_access_token(user.id, user.token_version)
    return token, settings.jwt_expire_minutes * 60


def change_password(db: Session, user: SysUser, old_password: str, new_password: str) -> None:
    """用户改密。改完 token_version+1 → 旧令牌全部失效。"""
    if not verify_password(old_password, user.password_hash):
        raise InvalidRequestError("原密码不正确")

    if verify_password(new_password, user.password_hash):
        raise InvalidRequestError("新密码不能与原密码相同")

    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    user.temporary_password_expires_at = None
    # ⚠️ 关键：版本 +1，让所有旧令牌失效
    user.token_version = user.token_version + 1
    db.commit()
    db.refresh(user)


def reset_student_password(db: Session, student: SysUser) -> str:
    """管理员重置学生初始密码，返回明文（只展示一次）。

    ⚠️ 明文只在这一刻返回，数据库只存哈希。
    """
    if not student.is_student:
        raise InvalidRequestError("只能重置学生账号的密码")

    from app.core.security import generate_temp_password

    plain = generate_temp_password()
    student.password_hash = hash_password(plain)
    student.must_change_password = True
    student.temporary_password_expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    student.token_version = student.token_version + 1   # 旧令牌失效
    db.commit()
    return plain
