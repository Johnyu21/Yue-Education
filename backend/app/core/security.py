"""
安全工具（M1-04）：密码哈希 + JWT 令牌

密码：用 bcrypt，绝不存明文。
JWT：把 user_id + token_version 签进令牌，改密/禁用后旧令牌自动失效。
"""
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings


# =============================================================
# 密码
# =============================================================
def hash_password(plain: str) -> str:
    """明文 → 哈希。存进数据库的都是这个。"""
    if len(plain.encode("utf-8"))>72:
        from app.core.errors import InvalidRequestError
        raise InvalidRequestError("密码 UTF-8 编码长度不得超过72字节")
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """校验密码。"""
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except (ValueError, TypeError):
        return False


def generate_temp_password(length: int = 12) -> str:
    """生成安全随机初始密码（给签约后的学生用）。
    ⚠️ 不能用手机号后 6 位这种可推导的方式。
    """
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


# =============================================================
# JWT 令牌
# =============================================================
def create_access_token(user_id: int, token_version: int) -> str:
    """签发令牌。token_version 是关键：改密后它变了，旧令牌就失效。"""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),                    # 用户 id
        "tv": token_version,                    # 令牌版本
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
        "iss": settings.app_name,               # 签发者
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict | None:
    """解令牌。无效/过期返回 None。"""
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],   # ⚠️ 算法固定，不接受客户端指定
            issuer=settings.app_name,
            options={"require":["sub","tv","iat","exp","iss"]},
        )
    except jwt.PyJWTError:
        return None
