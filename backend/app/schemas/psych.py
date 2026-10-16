"""
心理关怀 请求与响应 DTO（⚠️ 敏感，读取需 psych_access_enabled）
"""
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ---- 请求 ----
class PsychConsentRequest(BaseModel):
    granted: bool
    consent_version: str = Field(min_length=1, max_length=40)
    expected_version: int = Field(gt=0)
    request_key: UUID


class PsychCorrectionRequest(BaseModel):
    """主管人工修正情绪观测（追加新版本，不删旧记录）。"""
    replaces_profile_id: int
    expected_latest_version: int = Field(gt=0)
    emotion_state: Literal["HEALTHY", "NEGATIVE", "VERY_NEGATIVE", "UNKNOWN"]
    reason: str = Field(min_length=1, max_length=2000)
    request_key: UUID


class PsychActionRequest(BaseModel):
    """人工复核/跟进/终结（M3 控制器调用 review_alert 业务函数）。"""
    action: Literal["CONFIRM", "DISMISS", "START_HANDLING", "NOTE", "CLOSE"]
    note: str = Field(min_length=1, max_length=2000)
    expected_version: int = Field(gt=0)
    request_key: UUID
    confirmation_token: str | None = None


# ---- 响应 ----
class ActiveAlertBrief(BaseModel):
    id: str
    severity: str
    status: str


class PsychStudentSummary(BaseModel):
    studentProfileId: str
    realName: str
    classId: str | None = None
    assessmentDate: date | None = None
    emotionState: str                            # 缺失日 UNKNOWN
    latestObservedAt: datetime | None = None
    activeAlert: ActiveAlertBrief | None = None


class PsychObservationDTO(BaseModel):
    id: str
    versionNo: int
    assessmentDate: date
    observedAt: datetime
    emotionState: str
    assessmentSource: str
    status: str
    isValid: bool
    summary: str | None = None
    verifiedAt: datetime | None = None


class PsychAlertDTO(BaseModel):
    id: str
    studentProfileId: str
    studentDisplayName: str
    classId: str | None = None
    severity: str
    signalCode: str
    triggerSummary: str
    status: str
    followUpUserId: str | None = None
    repeatCount: int
    lastTriggeredAt: datetime
    reviewedAt: datetime | None = None
    actionNote: str | None = None
    handlingHistory: list = []
    version: int
