"""
活动与报名（event_lecture / event_registration）请求与响应 DTO —— M2

约定：请求体 snake_case；响应体 camelCase；ID 为十进制字符串；时间为 ISO 8601 带时区。
"""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------- 响应 ----------------
class EventOut(BaseModel):
    id: str
    title: str
    description: str
    courseProjectId: str | None = None
    startAt: datetime
    endAt: datetime
    signupDeadline: datetime
    capacity: int
    remainingCapacity: int             # 实时值，非名额预占承诺
    location: str | None = None
    status: str
    version: int


class RegistrationEventBrief(BaseModel):
    id: str
    title: str


class RegistrationOut(BaseModel):
    id: str
    event: RegistrationEventBrief
    registrantName: str
    mobile: str
    status: str
    registeredAt: datetime
    canceledAt: datetime | None = None
    version: int


# ---------------- 请求 ----------------
class EventCreateIn(BaseModel):
    model_config = {"extra": "forbid"}

    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1)
    organizer_user_id: int
    host_department_id: int
    course_project_id: int | None = None
    start_at: datetime
    end_at: datetime
    signup_deadline: datetime
    capacity: int = Field(gt=0)
    location: str | None = Field(default=None, max_length=200)


class EventUpdateIn(BaseModel):
    model_config = {"extra": "forbid"}

    expected_version: int = Field(gt=0)
    request_key: UUID

    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, min_length=1)
    course_project_id: int | None = None
    host_department_id: int | None = None
    organizer_user_id: int | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    signup_deadline: datetime | None = None
    capacity: int | None = Field(default=None, gt=0)
    location: str | None = Field(default=None, max_length=200)
    status: Literal["DRAFT", "OPEN", "ENDED", "CANCELLED"] | None = None


class RegistrationIn(BaseModel):
    """访客必填 name/mobile；学生从本人账号取值（客户端不允许指定他人档案）。"""

    model_config = {"extra": "forbid"}

    request_key: UUID
    confirmed: bool = False
    name: str | None = Field(default=None, max_length=80)
    mobile: str | None = Field(default=None, max_length=32)


class RegistrationCancelIn(BaseModel):
    """取消凭据走 body，不放 URL。"""

    model_config = {"extra": "forbid"}

    request_key: UUID
    expected_version: int = Field(gt=0)
    cancel_token: str | None = None
