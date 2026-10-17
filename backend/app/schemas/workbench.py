"""
员工工作台请求/响应 DTO —— M3

- ServiceAssignmentIn：API055 主管转派待审单（M4 assign_service 的入参）
- TodoOut：API088 统一待办（实时查询，无 todo 表）
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ServiceAssignmentIn(BaseModel):
    """主管转派待审单（API055）。"""
    model_config = {"extra": "forbid"}

    assignee_user_id: int
    expected_version: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=2000)
    request_key: UUID
    confirmation_token: str | None = None


class TodoOut(BaseModel):
    """待办项。key 由类型+对象派生，稳定可去重。"""
    key: str
    type: str
    title: str
    entityId: str
    relatedType: str
    dueAt: datetime | None = None
    actionRoute: str
