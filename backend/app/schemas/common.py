"""
公共请求 DTO：版本 + 幂等键 + 原因
"""
from uuid import UUID

from pydantic import BaseModel, Field


class VersionRequest(BaseModel):
    expected_version: int = Field(gt=0)
    request_key: UUID
    confirmation_token: str | None = None


class VersionReasonRequest(VersionRequest):
    reason: str = Field(min_length=1, max_length=2000)
