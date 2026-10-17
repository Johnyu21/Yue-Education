"""
Dify 适配器 —— 选工作流、组装 payload_json、超时、output_json 校验、失败降级

统一约定（02 文档）：
  Start 变量 payload_json（字符串 JSON），End 变量 output_json（字符串 JSON）；
  后端对 data.outputs.output_json 解析一次并按模式校验。
"""
import json
import logging

from app.core.config import settings
from app.core.errors import AIBadResponseError, AIUnavailableError
from app.integrations.dify.client import DifyClient

logger = logging.getLogger(__name__)

# 受众 → 工作流 key 的配置项
_AUDIENCE_KEYS = {
    "visitor": lambda: settings.dify_visitor_key,
    "assessment": lambda: settings.dify_assessment_key,
    "enterprise": lambda: settings.dify_enterprise_key,
    "student": lambda: settings.dify_student_key,
    "report": lambda: settings.dify_report_key,
}


def _client() -> DifyClient:
    return DifyClient(settings.dify_base_url)


def run_workflow(audience: str, payload: dict, user: str, timeout: float = 45.0) -> dict:
    """按受众选择工作流并调用，返回解析后的 output_json（dict）。"""
    if settings.dify_mode == "disabled":
        raise AIUnavailableError("AI能力未启用")
    if settings.dify_mode == "mock" and audience == "student":
        from app.integrations.dify.mock_samples import student_output
        return student_output(payload)
    get_key = _AUDIENCE_KEYS.get(audience)
    if get_key is None:
        raise AIUnavailableError(f"未知工作流受众 {audience}")
    key = get_key()
    if not key:
        raise AIUnavailableError(f"{audience} 工作流未配置 key")

    client = DifyClient(settings.dify_base_url, timeout=timeout)
    outputs = client.run_workflow(
        key,
        {"payload_json": json.dumps(payload, ensure_ascii=False)},
        user,
    )

    raw = outputs.get("output_json")
    if raw is None:
        raise AIBadResponseError("工作流未返回 output_json")
    if isinstance(raw, str):
        try:
            parsed=json.loads(raw)
            if not isinstance(parsed,dict):raise AIBadResponseError("output_json必须为对象")
            return parsed
        except json.JSONDecodeError as exc:
            raise AIBadResponseError("output_json 不是合法 JSON") from exc
    if isinstance(raw, dict):
        return raw
    raise AIBadResponseError("output_json 类型异常")


def call_student_workflow(payload: dict, user_id: int, timeout: float = 45.0) -> dict:
    """学生助手工作流（WF_STUDENT）。"""
    return run_workflow("student", payload, str(user_id), timeout=timeout)


def ai_status() -> str:
    """AI 结果来源标识：mock 必须标 MOCK，真实调用标 LIVE。

    ⚠️ 各助手的 aiStatus 统一从这里取，避免"某人写 settings、某人写桥接层"两套口径。
    disabled 模式不会走到这里（run_workflow 先抛 AIUnavailableError → 上层降级 UNAVAILABLE）。
    """
    return "MOCK" if settings.dify_mode == "mock" else "LIVE"


# =============================================================
# M2 追加：访客客服（WF_VISITOR）与客户研判（WF_ASSESSMENT）入口
#
# ⚠️ 函数体内延迟 import，避免与 visitor.py / assessment.py
#    对本包的 run_workflow 引用形成循环导入。
# ⚠️ 这两个函数只是便捷入口；mock 判定在 visitor/assessment 内完成。
# =============================================================


def run_visitor_workflow(payload: dict, *, user: str = "visitor",
                         timeout_s: int | None = None) -> dict:
    """访客客服工作流（WF_VISITOR）。"""
    from app.integrations.dify.visitor import run_visitor

    return run_visitor(payload, user=user, timeout_s=timeout_s)


def run_assessment_workflow(payload: dict, *, user: str = "assessment",
                            timeout_s: int | None = None) -> dict:
    """客户研判字段提取工作流（WF_ASSESSMENT）。"""
    from app.integrations.dify.assessment import run_assessment

    return run_assessment(payload, user=user, timeout_s=timeout_s)


def run_enterprise_workflow(payload: dict, *, user: str | int = "employee",
                            timeout_s: int | None = None) -> dict:
    """企业助手工作流（WF_ENTERPRISE）。"""
    from app.integrations.dify.enterprise import run_enterprise

    return run_enterprise(payload, user=str(user), timeout_s=timeout_s)
