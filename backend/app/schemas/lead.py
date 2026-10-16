"""
客户留资与研判（crm_lead）请求与响应 DTO —— M2

约定：请求体 snake_case；响应体 camelCase；ID 为十进制字符串。
写入 DTO 禁止未知字段；owner_user_id / dept_id / status / profile_summary 等
一律由后端按业务规则决定，不接受客户端传入。
"""
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------- 留资 ----------------
class LeadCaptureIn(BaseModel):
    """三渠道统一留资入口。

    channel=FORM：要求 gender/city/education（完整表单）
    channel=ASSISTANT：至少 name/mobile（会话最小集）
    跨字段规则在 service 层校验，便于返回字段级 422。
    """

    model_config = {"extra": "forbid"}

    name: str = Field(min_length=1, max_length=80)
    mobile: str = Field(min_length=1, max_length=32)
    channel: Literal["FORM", "ASSISTANT"]
    request_key: UUID
    confirmed: bool = False

    gender: str | None = Field(default=None, max_length=20)
    city: str | None = Field(default=None, max_length=100)
    education: str | None = Field(default=None, max_length=80)
    date_of_birth: date | None = None
    intended_project_id: int | None = None
    study_purpose: str | None = Field(default=None, max_length=30)
    interest_level: str | None = Field(default=None, max_length=30)
    confirmation_token: str | None = None


class LeadCaptureOut(BaseModel):
    """统一回执：不返回客户是否存在、客户 id、姓名或顾问（防匿名探测）。"""

    accepted: bool = True
    receiptNo: str


# ---------------- 研判 ----------------
class AssessmentIn(BaseModel):
    model_config = {"extra": "forbid"}

    request_key: UUID
    expected_version: int = Field(gt=0)
    project_ids: list[int] = Field(min_length=1, max_length=20)
    resume_object_key: str | None = None
    upload_proof: str | None = None          # M1 的 API028 暂未返回，可选
    confirmed_facts: dict = Field(default_factory=dict)


class AssessmentStartOut(BaseModel):
    assessmentRequestId: str
    status: str                              # RUNNING / SUCCEEDED
    leadVersion: int


class AssessmentOut(BaseModel):
    assessmentStatus: str                    # NONE / RUNNING / SUCCEEDED / FAILED
    assessmentRequestId: str | None = None
    assessedAt: datetime | None = None
    report: dict | None = None
    latestScore: int | None = None           # 无已批准权重时为 null（不显示 0 分）
    isPreviousReport: bool = False


# ---------------- 简历提取草稿 ----------------
class ResumeExtractionIn(BaseModel):
    model_config = {"extra": "forbid"}

    object_key: str = Field(min_length=1)
    upload_proof: str | None = None
    request_key: UUID
    expected_version: int = Field(gt=0)


class ResumeExtractionOut(BaseModel):
    draftId: str
    facts: dict
    evidence: list[dict] = []
    missingFields: list[str] = []
    expiresAt: datetime
    aiStatus: str                            # LIVE / UNAVAILABLE
