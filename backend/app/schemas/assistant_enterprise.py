"""
企业助手（API029）Dify WF_ENTERPRISE 输出契约

Dify 只输出意图/参数/草稿；写操作由后端签发提议卡片（confirmation_token），
员工确认后调普通业务接口再鉴权。本 Schema 只做结构校验，不做业务授权。
"""
from app.core.dto import BaseModel
from pydantic import Field
from typing import Literal


class WfEnterpriseOutput(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    intent: str = "OTHER"
    action: str | None = None
    params: dict = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    answer: str = ""
    draft: dict | None = None
    sources: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# 业务意图白名单（读 + 写 + 知识）
READ_INTENTS = {
    "LEAD_SEARCH", "LEAD_DETAIL", "FOLLOWUP_LIST", "TODO_LIST",
    "SERVICE_LIST", "FEEDBACK_LIST", "PSYCH_LIST", "APPLICATION_SEARCH",
    "METRIC_QUERY", "ORG_SEARCH", "DAILY_SEARCH",
}
WRITE_INTENTS = {
    "LEAD_CREATE", "FOLLOWUP_ADD", "LEAD_CHANGE_STATUS",
    "DAILY_DRAFT", "LEAVE_DECIDE", "FEEDBACK_HANDLE",
    "PSYCH_NOTE", "APPLICATION_UPDATE",
}
KNOWLEDGE_INTENTS = {"KNOWLEDGE", "OTHER"}
ALLOWED_INTENTS = READ_INTENTS | WRITE_INTENTS | KNOWLEDGE_INTENTS
