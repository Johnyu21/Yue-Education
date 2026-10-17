"""
申请进度（文书/院校/签证）请求 DTO —— M3 员工登记与推进

响应复用 schemas/student.py 的 ApplicationEventDTO / ApplicationCaseDTO。
⚠️ 本系统只做内部登记，不调用校方/签证外部系统。
"""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ApplicationCreateIn(BaseModel):
    """人工建立内部跟踪事项（API080）。"""
    model_config = {"extra": "forbid"}

    student_profile_id: int
    enrollment_id: int | None = None
    item_type: Literal["DOCUMENT", "SCHOOL", "VISA"]
    title: str = Field(min_length=1, max_length=160)
    target_country: str | None = Field(default=None, max_length=80)
    target_school: str | None = Field(default=None, max_length=160)
    target_program: str | None = Field(default=None, max_length=160)
    detail: str = Field(min_length=1, max_length=10000)
    assignee_user_id: int
    occurred_at: datetime
    request_key: UUID


class ApplicationAdvanceIn(BaseModel):
    """追加进度/补料说明（API081）。

    event_kind=STAGE 时 stage 必填（PROCESSING/COMPLETED，按序推进）；
    DETAIL/ASSIGNMENT 沿用当前 stage。
    """
    model_config = {"extra": "forbid"}

    expected_sequence: int = Field(gt=0)
    request_key: UUID
    event_kind: Literal["STAGE", "DETAIL", "ASSIGNMENT"]
    stage: Literal["PROCESSING", "COMPLETED"] | None = None
    detail: str = Field(min_length=1, max_length=10000)
    assignee_user_id: int | None = None
    occurred_at: datetime
    confirmation_token: str | None = None    # AI 提议确认凭据
