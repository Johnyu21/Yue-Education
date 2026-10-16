"""
M2 配置读取桥（临时模块）

⚠️ 背景：core/ 是公共目录，M2 需要的配置项（Dify 模式/超时、访客会话 TTL、
   公开限流、研判回收阈值）按约定必须经 P1 review 才能写进 core/config.py。
   在 P1 合并之前，本模块按固定优先级读取：

      ① core.config.settings 的同名属性（P1 一旦合并，自动改用正式值）
      ② 进程环境变量（M2_CONFIG_NAME，全大写）
      ③ backend/.env 文件中的键（小写）
      ④ 任务卡建议的默认值

   ⚠️ 为什么要 ②③：Settings 的 model_config 是 extra="ignore"，`.env` 里
   未在 Settings 声明的键**不会**进入 settings，也不会进入 os.environ。
   只靠 getattr(settings, ...) 永远拿不到 M2 私有键，"mock 优先、可切 live"
   就会失效。因此这里补 env 与 .env 兜底，仍然不动 core/config.py。

✅ P1 合并配置项后，可删除本文件，各调用点改回 `settings.xxx`。

⚠️ 值为进程启动时读取并缓存：改 .env 后需重启后端。
"""
from __future__ import annotations

import os
from functools import lru_cache

from app.core.config import settings

# 默认值（与任务卡/文档建议一致）
_DEFAULTS: dict[str, object] = {
    "dify_mode": "mock",
    "ai_timeout_visitor_seconds": 30,
    "ai_timeout_assessment_seconds": 60,
    "visitor_session_ttl_minutes": 60,
    "visitor_rate_limit_per_minute": 20,
    "assessment_reclaim_after_seconds": 300,
}


@lru_cache(maxsize=1)
def _env_file_values() -> dict[str, str]:
    """读取 .env（与 pydantic-settings 使用同一文件），键统一小写。"""
    try:
        from dotenv import dotenv_values

        env_file = settings.model_config.get("env_file", ".env")
        if isinstance(env_file, (list, tuple)):
            env_file = env_file[0]
        return {
            key.lower(): value
            for key, value in (dotenv_values(str(env_file)) or {}).items()
            if value is not None and str(value).strip() != ""
        }
    except Exception:      # 缺 python-dotenv / 文件不存在 → 退回默认值
        return {}


def _raw(name: str):
    """按优先级取原始值；都取不到返回 None。"""
    if hasattr(settings, name):
        return getattr(settings, name)

    env_value = os.environ.get(name.upper())
    if env_value is not None and str(env_value).strip() != "":
        return env_value

    return _env_file_values().get(name)


def _get_str(name: str, default: str) -> str:
    value = _raw(name)
    return str(value) if value not in (None, "") else default


def _get_int(name: str, default: int) -> int:
    value = _raw(name)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def dify_mode() -> str:
    """mock=离线样本（并行开发默认）；live=真实调用 Dify。"""
    return _get_str("dify_mode", str(_DEFAULTS["dify_mode"]))


def ai_timeout_visitor_seconds() -> int:
    """访客客服 AI 超时（秒）。"""
    return _get_int("ai_timeout_visitor_seconds", int(_DEFAULTS["ai_timeout_visitor_seconds"]))


def ai_timeout_assessment_seconds() -> int:
    """客户研判 AI 超时（秒）。"""
    return _get_int("ai_timeout_assessment_seconds",
                    int(_DEFAULTS["ai_timeout_assessment_seconds"]))


def visitor_session_ttl_minutes() -> int:
    """访客会话草稿保留时长（分钟）。"""
    return _get_int("visitor_session_ttl_minutes",
                    int(_DEFAULTS["visitor_session_ttl_minutes"]))


def visitor_rate_limit_per_minute() -> int:
    """公开接口每 IP+会话 每分钟请求上限。"""
    return _get_int("visitor_rate_limit_per_minute",
                    int(_DEFAULTS["visitor_rate_limit_per_minute"]))


def assessment_reclaim_after_seconds() -> int:
    """研判 RUNNING 超时回收阈值（秒）。"""
    return _get_int("assessment_reclaim_after_seconds",
                    int(_DEFAULTS["assessment_reclaim_after_seconds"]))
