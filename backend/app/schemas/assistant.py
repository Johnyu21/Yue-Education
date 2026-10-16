"""
学生智能助手 请求与响应 DTO，及 Dify WF_STUDENT 输出校验 Schema

Dify 与后端内部契约（payload_json / output_json）使用 snake_case（对齐 M4 文档示例）；
HTTP 响应 AssistantResult 使用 camelCase。
"""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ---- 请求 ----
class AssistantContext(BaseModel):
    """context 只给定位提示，不授予权限。"""
    page: str | None = None
    selected_id: int | None = None


class AssistantRequest(BaseModel):
    message_id: UUID
    conversation_id: str | None = None
    message: str = Field(min_length=1, max_length=8000)
    input_kind: Literal["CHAT", "CHECK_IN"] = "CHAT"   # CHECK_IN 仅学生入口
    context: AssistantContext | None = None


# ---- 响应 ----
class SourceItem(BaseModel):
    documentId: str | None = None
    title: str | None = None
    section: str | None = None


class Proposal(BaseModel):
    """AI 提议卡片：写操作先返回此结构，用户确认后走普通业务接口。"""
    operation: str
    entityId: str | None = None
    preview: dict | None = None
    expectedVersion: int | None = None
    requestKey: str | None = None
    confirmationToken: str | None = None
    expiresAt: datetime | None = None


class AssistantResult(BaseModel):
    conversationId: str | None = None
    messageId: str
    answer: str
    sources: list[SourceItem] = []
    missingFields: list[str] = []
    proposal: Proposal | None = None
    aiStatus: Literal["LIVE", "UNAVAILABLE"] = "LIVE"
    warnings: list[str] = []


# ---- Dify WF_STUDENT 输出（snake_case，后端内部使用）----
class ObservationOutput(BaseModel):
    """Dify 产生的情绪观测（不回显给学生）。"""
    emotion_state: Literal["HEALTHY", "NEGATIVE", "VERY_NEGATIVE", "UNKNOWN"] = "UNKNOWN"
    direct_signal: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class WfStudentOutput(BaseModel):
    """Dify End 节点 output_json 的解析结构。"""
    schema_version: str = "1.0"
    answer: str = ""
    intent: str | None = None
    draft: dict | None = None
    missing_fields: list[str] = []
    sources: list[dict] = []
    warnings: list[str] = []
    observation: ObservationOutput | None = None
