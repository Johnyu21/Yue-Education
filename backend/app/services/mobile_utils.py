"""
手机号规范化（M2 BE-06）

⚠️ 位置说明：任务卡原计划放 `core/mobile.py`，但 core/ 是公共目录（P1 地盘），
   按约定先不放；本模块先放在 M2 自己的 services/ 下，
   **待 P1 确认后可上移到 core/ 并通知全组**。

规则（BE-06 / 待决事项 G3，小组如有既有规范以其为准）：
  1. 去首尾空白与内部空格/连字符/括号
  2. 统一剥离 +86 / 86 前缀
  3. 仅保留大陆 11 位：^1[3-9]\\d{9}$
规范化后的值在 crm_lead.mobile / event_registration(event_id,mobile) 上靠唯一约束兜底。
"""
import re

from app.core.errors import ValidationError

_MOBILE_RE = re.compile(r"^1[3-9]\d{9}$")


def normalize_mobile(raw: str | None) -> str:
    """规范化手机号；不合法抛 422 VALIDATION_ERROR（带字段级 errors）。"""
    if raw is None or not str(raw).strip():
        raise ValidationError(
            "手机号不能为空",
            errors=[{"field": "mobile", "reason": "必填"}],
        )
    s = re.sub(r"[\s\-()（）]", "", str(raw))
    if s.startswith("+86"):
        s = s[3:]
    elif s.startswith("86") and len(s) == 13:
        s = s[2:]
    if not _MOBILE_RE.match(s):
        raise ValidationError(
            "手机号格式不正确",
            errors=[{"field": "mobile", "reason": "应为 11 位大陆手机号"}],
        )
    return s


def mask_mobile(mobile: str | None) -> str:
    """脱敏展示（138****1234）。用于预览/日志，绝不记录明文。"""
    if not mobile:
        return ""
    if len(mobile) == 11:
        return f"{mobile[:3]}****{mobile[-4:]}"
    return "***"
