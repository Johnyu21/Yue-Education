"""
Dify HTTP 客户端 —— 后端调用 Dify 的唯一出口（key 只在后端）

调用 Dify 1.12.1 Workflow 应用：POST {base_url}/v1/workflows/run
"""
import logging

import httpx

from app.core.errors import AIBadResponseError, AITimeoutError, AIUnavailableError

logger = logging.getLogger(__name__)


class DifyClient:
    """Dify Workflow 应用的 HTTP 客户端（不保存 key，key 由调用方传入）。"""

    def __init__(self, base_url: str, timeout: float = 45.0):
        self.base_url = (base_url or "").rstrip("/")
        self.timeout = timeout

    def run_workflow(self, api_key: str, inputs: dict, user: str) -> dict:
        """调用 /v1/workflows/run，返回 data.outputs（dict）。

        ⚠️ 超时/鉴权失败/服务不可用分别映射为 AI 异常，便于上层降级。
        """
        if not self.base_url:
            raise AIUnavailableError("Dify 未配置")

        # 兼容 base_url 是否以 /v1 结尾（Dify 控制台展示的地址自带 /v1）
        base = self.base_url
        url = f"{base}/workflows/run" if base.endswith("/v1") else f"{base}/v1/workflows/run"
        headers = {"Authorization": f"Bearer {api_key}"}
        body = {"inputs": inputs, "response_mode": "blocking", "user": user}

        try:
            resp = httpx.post(url, json=body, headers=headers, timeout=self.timeout)
        except httpx.TimeoutException as exc:
            logger.warning("Dify 调用超时（%ss）", self.timeout)
            raise AITimeoutError() from exc
        except httpx.HTTPError as exc:
            logger.warning("Dify 连接失败：%s", exc.__class__.__name__)
            raise AIUnavailableError("AI 服务连接失败") from exc

        if resp.status_code in (401, 403):
            raise AIUnavailableError("AI 服务鉴权失败")
        if resp.status_code==429:
            raise AIUnavailableError("AI服务繁忙，请稍后重试")
        if resp.status_code >= 500:
            raise AIUnavailableError("AI 服务暂不可用")
        if resp.status_code != 200:
            logger.warning("Dify 返回异常状态 %s", resp.status_code)
            raise AIBadResponseError("AI 返回异常状态")

        try:
            data = resp.json()
        except ValueError as exc:
            raise AIBadResponseError("AI 返回不是合法 JSON") from exc

        if not isinstance(data,dict) or not isinstance(data.get("data"),dict):raise AIBadResponseError("AI返回结构异常")
        run = data["data"]
        if run.get("status") == "failed":
            logger.warning("Dify 工作流执行失败")
            raise AIBadResponseError("AI 工作流执行失败")

        if run.get("status") not in (None,"succeeded"):raise AIBadResponseError("AI工作流未完成")
        outputs=run.get("outputs")
        if not isinstance(outputs,dict):raise AIBadResponseError("AI输出结构异常")
        return outputs
