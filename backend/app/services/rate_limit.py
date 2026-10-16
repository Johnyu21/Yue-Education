"""
公开接口限流（进程内令牌桶）—— M2

⚠️ 本项目依赖里没有 Redis，这里用**进程内**实现：
   - 仅适用于**单实例开发/演示**环境；多实例部署会各算一份，需换共享存储。
   - 桶按"客户端 IP + 用途"维度计数，桶满即拒绝。

用法（在 controller 里）：
    from app.services import rate_limit
    rate_limit.enforce(request, "public")      # 超限抛 429 RATE_LIMITED
"""
from __future__ import annotations

import threading
import time

from fastapi import Request

from app.services import m2_config
from app.services.m2_errors import RateLimitedError

# key -> (tokens, last_refill_ts)
_buckets: dict[str, tuple[float, float]] = {}
_lock = threading.Lock()

_PRUNE_AFTER_SECONDS = 600      # 超过 10 分钟没活动的桶直接清掉，防内存增长


def client_key(request: Request, purpose: str) -> str:
    """客户端标识：优先 X-Forwarded-For 首段（经代理时），否则 peer IP。

    ⚠️ 只用于限流，不用于鉴权；伪造该头只会影响"自己被限流"的范围。
    """
    forwarded = request.headers.get("x-forwarded-for")
    ip = forwarded.split(",")[0].strip() if forwarded else None
    if not ip:
        ip = request.client.host if request.client else "unknown"
    return f"{purpose}:{ip}"


def _refill(tokens: float, last_ts: float, rate_per_minute: int, now: float) -> float:
    capacity = float(rate_per_minute)
    return min(capacity, tokens + (now - last_ts) * (capacity / 60.0))


def check(key: str) -> None:
    """消耗一个令牌；不足则抛 429。"""
    rate = m2_config.visitor_rate_limit_per_minute()
    if rate <= 0:                       # 配 0 视为关闭限流
        return

    now = time.monotonic()
    with _lock:
        tokens, last_ts = _buckets.get(key, (float(rate), now))
        tokens = _refill(tokens, last_ts, rate, now)
        if tokens < 1.0:
            _buckets[key] = (tokens, now)
            raise RateLimitedError("请求过于频繁，请稍后再试")

        _buckets[key] = (tokens - 1.0, now)

        # 顺手清理过期桶（低频操作，成本可忽略）
        if len(_buckets) > 512:
            cutoff = now - _PRUNE_AFTER_SECONDS
            for k, (_, ts) in list(_buckets.items()):
                if ts < cutoff:
                    _buckets.pop(k, None)


def enforce(request: Request, purpose: str) -> None:
    """按请求来源限流。"""
    check(client_key(request, purpose))
