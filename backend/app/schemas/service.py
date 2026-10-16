"""
行政服务（请假/考务/信息修改）请求与响应 DTO

请求字段 snake_case（对齐 04 文档），响应字段 camelCase（对齐 M1 UserOut 风格），ID 转字符串。
"""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ---- 请求 ----
class ChangeRequest(BaseModel):
    """INFO_CHANGE 的新旧值；核验信息由审批员工提交，客户端不能声明验证已通过。"""
    old_values: dict
    new_values: dict


class ServiceCreateRequest(BaseModel):
    request_key: UUID
    service_type: Literal["LEAVE", "EXAM", "INFO_CHANGE", "OTHER"]
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1)
    start_at: datetime | None = None
    end_at: datetime | None = None
    change_request: ChangeRequest | None = None
    confirmed: bool = True
    confirmation_token: str | None = None


class IdentityVerification(BaseModel):
    """信息修改批准前的核验信息（仅有权员工提交）。"""
    verified_fields: list[str]
    note: str | None = None


class ServiceDecisionRequest(BaseModel):
    decision: Literal["APPROVE", "REJECT"]
    note: str = Field(min_length=1, max_length=2000)
    expected_version: int = Field(gt=0)
    request_key: UUID
    confirmation_token: str | None = None
    identity_verification: IdentityVerification | None = None


# ---- 响应 ----
class ServiceDTO(BaseModel):
    id: str
    studentProfileId: str
    studentDisplayName: str
    serviceType: str
    title: str
    description: str
    startAt: datetime | None = None
    endAt: datetime | None = None
    changeRequest: dict | None = None          # 学生仅本人可见
    assigneeDisplayName: str | None = None
    status: str
    decisionNote: str | None = None
    decidedAt: datetime | None = None
    createTime: datetime
    version: int
