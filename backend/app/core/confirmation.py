"""
确认令牌（M1 补充）—— AI 提议的写操作，必须用户确认后才执行

场景：
    学生在助手说"我要请假"
      → AI 生成**提议卡片**（不直接写库）
      → 用户点"确认"
      → 前端拿**确认令牌**调普通业务接口
      → 后端校验令牌，才真正执行

⚠️ 安全核心（02 文档要求）：
    令牌绑定 7 样东西，任何一样对不上就拒绝：
      actor（谁确认的）/ operation（什么操作）/ entity_id（哪条记录）
      / payload_hash（确认的内容）/ expected_version（版本）
      / request_key（幂等键）/ exp（5 分钟到期）

⚠️ 最重要的一条：
    **令牌只是"用户确认过"的证明，不是"有权限"的证明。**
    校验通过后，调用方**仍要做权限和版本检查**。
    令牌不能替代 `build_scope` / 乐观锁 —— 否则用户确认一次就能越权。

用法：
    # ① AI 生成提议时（不写库）
    token = sign_confirmation(actor, "SUBMIT_SERVICE", entity_id=None,
                              payload=service_data, expected_version=None,
                              request_key=req_key)

    # ② 用户确认后调用业务接口
    claims = verify_confirmation(actor, token, payload=service_data)
    # 之后照常做权限检查 + 事务写入
"""
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings
from app.core.errors import InvalidRequestError
from app.models.user import SysUser

# 确认令牌的有效期（分钟）——02 文档要求 5 分钟
CONFIRM_TTL_MINUTES = 5
# 独立的签发主体，和登录令牌区分开（防止混用）
_CONFIRM_ISSUER = "confirm"


def _payload_hash(payload) -> str:
    """把载荷算成指纹。载荷变了指纹就变，防止"确认后偷改内容"。"""
    if payload is None:
        return ""
    # sort_keys 保证字段顺序不同也算同一个指纹
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def sign_confirmation(
    actor: SysUser,
    operation: str,
    *,
    entity_id: int | None,
    payload,
    expected_version: int | None,
    request_key: str,
) -> str:
    """签发确认令牌，绑定 7 项信息。

    Args:
        operation: 操作名，如 SUBMIT_SERVICE / CONVERT_LEAD
        entity_id: 操作对象 id（新建时为 None）
        payload: 待执行的内容（会被算成指纹绑定）
        expected_version: 乐观锁版本（新建时为 None）
        request_key: 幂等键
    """
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(actor.id),                 # ⚠️ 绑 actor：别人的令牌用不了
        "op": operation,                      # ⚠️ 绑操作类型
        "eid": entity_id,                     # ⚠️ 绑对象
        "ph": _payload_hash(payload),         # ⚠️ 绑内容指纹
        "ev": expected_version,               # ⚠️ 绑版本
        "rk": request_key,                    # ⚠️ 绑幂等键
        "iss": _CONFIRM_ISSUER,
        "iat": now,
        "exp": now + timedelta(minutes=CONFIRM_TTL_MINUTES),   # ⚠️ 5 分钟到期
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_confirmation(
    actor: SysUser,
    token: str | None,
    *,
    operation: str,
    entity_id: int | None,
    payload,
    expected_version: int | None = None,
    request_key: str | None = None,
) -> dict:
    """校验确认令牌。任何一项对不上就拒绝。

    ⚠️ 返回的 claims 只证明"用户确认过"。
       调用方**必须继续**做权限检查（build_scope）和版本检查。
    """
    if not token:
        raise InvalidRequestError("缺少确认信息，请重新确认")

    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],   # 算法固定，防混淆
            issuer=_CONFIRM_ISSUER,
        )
    except jwt.ExpiredSignatureError as e:
        raise InvalidRequestError("确认已过期（超过 5 分钟），请重新确认") from e
    except jwt.PyJWTError as e:
        raise InvalidRequestError("确认信息无效，请重新确认") from e

    # ---- 逐项核对，任何一项不符都拒绝 ----

    # ① 必须是同一个人的确认（防止有人拿别人的令牌）
    if claims.get("sub") != str(actor.id):
        raise InvalidRequestError("确认信息与当前用户不符")

    # ② 操作类型必须一致（防止拿"确认请假"的令牌去"确认转学生"）
    if claims.get("op") != operation:
        raise InvalidRequestError("确认信息与当前操作不符，请重新确认")

    # ③ 对象必须一致
    if claims.get("eid") != entity_id:
        raise InvalidRequestError("确认信息与当前对象不符，请重新确认")

    # ④ 内容指纹必须一致（⚠️ 防止"确认了 A、实际提交 B"）
    if claims.get("ph") != _payload_hash(payload):
        raise InvalidRequestError("确认后内容已变更，请重新确认")

    # ⑤ 版本必须一致（有版本的场景）
    if entity_id is not None and expected_version is not None:
        if claims.get("ev") != expected_version:
            raise InvalidRequestError("确认信息与当前版本不符，请重新确认")

    # ⑥ 幂等键必须一致
    if not claims.get("rk"):
        raise InvalidRequestError("确认信息缺少幂等键")

    if request_key is not None and claims["rk"] != str(request_key):
        raise InvalidRequestError("确认信息与请求键不符")

    # Assistant cards are invalidated when the user changes/cancels the draft.
    # Ordinary form tokens have no draft binding and retain their existing flow.
    if claims.get("draft_key"):
        from app.core import runtime_state
        draft_state = runtime_state.get(claims["draft_key"])
        if not draft_state or draft_state.get("revision") != claims.get("draft_revision"):
            raise InvalidRequestError("助手草稿已变更或取消，请核对最新确认卡")

    return claims


def new_request_key() -> str:
    """生成幂等键。每次新的业务提交用一个，重试沿用同一个。"""
    return str(uuid.uuid4())
