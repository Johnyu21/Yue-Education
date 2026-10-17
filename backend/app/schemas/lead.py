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


# =============================================================
# M3：员工客户经营（列表/详情/建客户/修改/跟进/状态/转化）
# 请求 snake_case（extra=forbid），响应 camelCase，ID 字符串。
# =============================================================


class LeadManualIn(BaseModel):
    """员工手工/转写确认建客户（API034）。

    dept_id 仅管理员可指定；owner 恒由后端设为当前员工。
    """
    model_config = {"extra": "forbid"}

    name: str = Field(min_length=1, max_length=80)
    mobile: str = Field(min_length=1, max_length=32)
    request_key: UUID
    gender: str | None = Field(default=None, max_length=20)
    city: str | None = Field(default=None, max_length=100)
    education: str | None = Field(default=None, max_length=80)
    date_of_birth: date | None = None
    intended_project_id: int | None = None
    study_purpose: str | None = Field(default=None, max_length=30)
    interest_level: str | None = Field(default=None, max_length=30)
    dept_id: int | None = None               # 仅管理员可指定
    content: str | None = Field(default=None, max_length=2000)
    confirmation_token: str | None = None    # AI 提议确认凭据（表单可空）


class LeadUpdateIn(BaseModel):
    """补充核对后的客户资料（API035）：只接受事实白名单。"""
    model_config = {"extra": "forbid"}

    expected_version: int = Field(gt=0)
    request_key: UUID
    name: str | None = Field(default=None, min_length=1, max_length=80)
    mobile: str | None = Field(default=None, min_length=1, max_length=32)
    gender: str | None = Field(default=None, max_length=20)
    city: str | None = Field(default=None, max_length=100)
    education: str | None = Field(default=None, max_length=80)
    date_of_birth: date | None = None
    intended_project_id: int | None = None
    study_purpose: str | None = Field(default=None, max_length=30)
    interest_level: str | None = Field(default=None, max_length=30)
    profile_summary: dict | None = None


class FollowUpIn(BaseModel):
    """写联系记录/下次计划（API039）。next_follow_up_at 省略=保留，null=清除。"""
    model_config = {"extra": "forbid"}

    content: str = Field(min_length=1, max_length=10000)
    follow_up_type: Literal["CONTACT"] = "CONTACT"
    next_follow_up_at: datetime | None = None
    expected_version: int = Field(gt=0)
    request_key: UUID
    confirmation_token: str | None = None    # AI 提议确认凭据


class LeadTransitionIn(BaseModel):
    """流失/恢复/开始跟进（API040）；SIGNED 禁止从此接口写入。"""
    model_config = {"extra": "forbid"}

    target_status: Literal["FOLLOWING", "LOST"]
    reason: str = Field(min_length=1, max_length=2000)
    expected_version: int = Field(gt=0)
    request_key: UUID
    confirmation_token: str | None = None    # AI 提议确认凭据


class LeadAssignmentIn(BaseModel):
    """分配/转派（API037，仅本部门主管/管理员）。"""
    model_config = {"extra": "forbid"}

    owner_user_id: int
    expected_version: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=2000)
    request_key: UUID


class ConversionIn(BaseModel):
    """确认线下签约并转学生（API043）。"""
    model_config = {"extra": "forbid"}

    request_key: UUID
    expected_version: int = Field(gt=0)
    contract_confirmed: bool
    course_project_id: int
    class_id: int
    advisor_user_id: int
    enrollment_date: date
    contract_ref: str | None = Field(default=None, max_length=100)
    contract_amount: str | None = None       # 十进制字符串
    contract_currency: str | None = Field(default=None, max_length=3)


class LeadSummaryOut(BaseModel):
    id: str
    name: str
    mobileMasked: str
    education: str | None = None
    intendedProjectId: str | None = None
    status: str
    ownerDisplayName: str | None = None
    latestScore: int | None = None
    profileCompleteness: str
    nextFollowUpAt: datetime | None = None
    version: int


class LeadStaffOut(LeadSummaryOut):
    mobile: str
    gender: str | None = None
    city: str | None = None
    dateOfBirth: date | None = None
    studyPurpose: str | None = None
    interestLevel: str | None = None
    deptId: str | None = None
    profileSummary: dict | None = None
    assessmentStatus: str
    assessmentStartedAt: datetime | None = None
    assessmentErrorCode: str | None = None
    assessedAt: datetime | None = None
    contractRef: str | None = None
    contractAmount: str | None = None
    contractCurrency: str | None = None


class FollowUpOut(BaseModel):
    id: str
    actorDisplayName: str | None = None
    followUpType: str
    content: str
    statusBefore: str | None = None
    statusAfter: str | None = None
    nextFollowUpAt: datetime | None = None
    createTime: datetime
    details: dict | None = None
