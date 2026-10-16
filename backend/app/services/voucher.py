"""
访客取消凭据（确定性 HMAC）—— M2

背景：`core/confirmation` 的签名绑定登录 actor，访客没有账号，不适用。

设计：
  - 凭据对 (event_id, registration_id, request_key) 做**确定性** HMAC-SHA256；
    因此**同一个 request_key 重试报名能重建完全相同的凭据**（满足契约）。
  - 明文只随首次成功响应返回；数据库只存 sha256 哈希（cancel_token_hash），
    泄库也拿不到可用凭据。
  - 校验用 compare_digest 防时序侧信道。

⚠️ 明文凭据绝不写日志。
"""
from __future__ import annotations

import hashlib
import hmac

from app.core.config import settings

# 与登录令牌/确认令牌用不同前缀，避免跨用途混用
_SIGNING_PREFIX = "m2-cancel-voucher:"


def _signing_key() -> bytes:
    return (_SIGNING_PREFIX + settings.jwt_secret).encode("utf-8")


def _message(event_id: int, registration_id: int, request_key) -> bytes:
    return f"{event_id}:{registration_id}:{request_key}".encode("utf-8")


def sign_cancel_voucher(event_id: int, registration_id: int, request_key) -> str:
    """生成确定性取消凭据（返回明文，只在首次成功响应里出现一次）。"""
    return hmac.new(_signing_key(), _message(event_id, registration_id, request_key),
                    hashlib.sha256).hexdigest()


def hash_voucher(token: str) -> str:
    """入库前哈希；数据库永不保存明文凭据。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_cancel_voucher(token: str | None, event_id: int, registration_id: int,
                          request_key) -> bool:
    """校验访客取消凭据。

    ⚠️ 用 **bytes** 比对：`hmac.compare_digest` 不接受含非 ASCII 的 str，
       否则伪造一个中文凭据会直接抛 TypeError（500），而不是干净地返回"不匹配"。
    """
    if not token:
        return False
    expected = sign_cancel_voucher(event_id, registration_id, request_key)
    try:
        candidate = token.encode("utf-8")
    except (AttributeError, UnicodeError):
        return False
    return hmac.compare_digest(candidate, expected.encode("utf-8"))
