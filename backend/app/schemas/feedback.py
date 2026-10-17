"""
售后工单（投诉/建议/咨询）请求与响应 DTO

priority 只由后端决定，学生请求与响应白名单均不接受/不返回 priority。
"""
from pydantic import AwareDatetime as datetime
from typing import Literal
from uuid import UUID

from app.core.dto import BaseModel
from pydantic import Field


# ---- 请求 ----
class FeedbackCreateRequest(BaseModel):
    category: Literal["COMPLAINT", "SUGGESTION", "CONSULTATION"]
    subject: str = Field(min_length=1, max_length=160)
    teacher_name: str = Field(min_length=1, max_length=80)
    project_category: str = Field(min_length=1, max_length=80)
    course_project_id: int | None = None
    content: str = Field(min_length=1)
    request_key: UUID
    confirmed: bool = True
    confirmation_token: str | None = None


class FeedbackHandlingRequest(BaseModel):
    """员工处理（M3 控制器调用 handle_feedback 业务函数）。"""
    action: Literal["NOTE", "RESOLVE", "ASSIGN"]
    note: str = Field(min_length=1, max_length=2000)
    resolution: str | None = None
    assignee_user_id: int | None = None
    expected_version: int = Field(gt=0)
    request_key: UUID
    confirmation_token: str | None = None


class RatingRequest(BaseModel):
    """学生评价 1~5 分。"""
    rating: int = Field(ge=1, le=5)
    comment: str | None = None
    expected_version: int = Field(gt=0)
    request_key: UUID


# ---- 响应 ----
class FeedbackStudentDTO(BaseModel):
    id: str
    category: str
    subject: str
    teacherName: str
    projectCategory: str
    courseProjectId: str | None = None
    content: str
    status: str
    resolution: str | None = None
    firstResponseAt: datetime | None = None
    resolvedAt: datetime | None = None
    closedAt: datetime | None = None
    satisfactionRating: int | None = None
    satisfactionComment: str | None = None
    createTime: datetime
    version: int


class FeedbackStaffDTO(FeedbackStudentDTO):
    """员工侧：附加 priority 与内部字段，需 can_handle_feedback。"""
    priority: str
    deptId: str
    assigneeUserId: str | None = None
    dueAt: datetime | None = None
    firstResolvedAt: datetime | None = None
    isNotified: bool
    reopenedCount: int
    handlingHistory: list = []
