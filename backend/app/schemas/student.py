"""
学生档案 / 成绩 / 日程 / 申请进度 请求与响应 DTO
"""
from datetime import date
from pydantic import AwareDatetime as datetime
from typing import Literal
from uuid import UUID

from app.core.dto import BaseModel
from pydantic import Field


# ---- 请求 ----
class ReminderRequest(BaseModel):
    """设置/取消单次提醒（remind_at 为 None 表示清除）。"""
    remind_at: datetime | None = None
    expected_version: int = Field(gt=0)
    request_key: UUID


class UpgradeInterestRequest(BaseModel):
    """升学意向确认（需明确确认，写本人来源客户跟进并通知顾问）。"""
    course_project_id: int
    note: str | None = None
    request_key: UUID
    confirmed: bool = True
    confirmation_token: str | None = None


# ---- 响应（camelCase，ID 转字符串）----
class StudentUserBrief(BaseModel):
    id: str
    realName: str
    mobile: str


class StudentAdvisorBrief(BaseModel):
    id: str
    realName: str
    contactInfo: str | None = None


class StudentClassBrief(BaseModel):
    id: str
    code: str
    name: str
    courseType: str | None = None
    deptId: str
    headTeacher: dict | None = None            # {id, realName}
    isActive: bool = True
    version: int


class StudentEnrollmentItem(BaseModel):
    version: int
    id: str
    courseProjectId: str
    projectName: str
    status: str


class StudentSelfDTO(BaseModel):
    id: str
    user: StudentUserBrief
    gender: str | None = None
    city: str | None = None
    education: str | None = None
    dateOfBirth: date | None = None
    enrollmentDate: date | None = None
    status: str
    psychConsentStatus: str | None = None          # 心理关怀授权状态（GRANTED/DENIED/...）
    classInfo: StudentClassBrief | None = None   # 04 文档的 class 字段（保留字，用 classInfo）
    advisor: StudentAdvisorBrief | None = None
    enrollments: list[StudentEnrollmentItem] = []
    version: int


class ScoreDTO(BaseModel):
    version: int = 1
    id: str
    subject: str
    scoreType: str
    scoreText: str
    scoreNumeric: str | None = None
    maxScore: str | None = None
    gradedAt: date | None = None
    enrollmentId: str | None = None
    scheduleId: str | None = None
    remark: str | None = None
    dataSource: str = "TEST"


class ScheduleDTO(BaseModel):
    id: str
    scheduleType: str
    title: str
    description: str | None = None
    startAt: datetime
    endAt: datetime | None = None
    location: str | None = None
    remindAt: datetime | None = None
    status: str
    dataSource: str
    reminderRevision: int
    version: int


class ApplicationEventDTO(BaseModel):
    id: str
    caseNo: str
    studentProfileId: str
    sequenceNo: int
    itemType: str
    title: str
    stage: str
    eventKind: str
    detail: str | None = None
    assigneeDisplayName: str | None = None
    occurredAt: datetime
    dataSource: str
    createTime: datetime


class ApplicationCaseDTO(BaseModel):
    caseNo: str
    rootId: str
    studentProfileId: str
    itemType: str
    title: str
    targetSchool: str | None = None
    targetCountry: str | None = None
    targetProgram: str | None = None
    stage: str
    latestSequence: int
    assigneeDisplayName: str | None = None
    occurredAt: datetime
    dataSource: str


# =============================================================
# M3：员工学生管理（列表/详情/调班换顾问/升学项目关联）
# =============================================================


class StudentStaffSummaryOut(BaseModel):
    id: str
    realName: str
    classId: str | None = None
    className: str | None = None
    advisorUserId: str | None = None
    status: str
    version: int


class StudentStaffOut(BaseModel):
    id: str
    userId: str
    realName: str
    mobile: str
    gender: str | None = None
    city: str | None = None
    education: str | None = None
    dateOfBirth: date | None = None
    enrollmentDate: date | None = None
    status: str
    classInfo: StudentClassBrief | None = None
    advisor: StudentAdvisorBrief | None = None
    enrollments: list[StudentEnrollmentItem] = []
    version: int


class RelationshipUpdateIn(BaseModel):
    """调班/换顾问/学籍状态（API049）。"""
    model_config = {"extra": "forbid"}

    class_id: int | None = None
    advisor_user_id: int | None = None
    status: Literal["ENROLLED", "COMPLETED", "PAUSED"] | None = None
    expected_version: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=2000)
    request_key: UUID


class EnrollmentCreateIn(BaseModel):
    """新增升学项目关联（API044）。"""
    model_config = {"extra": "forbid"}

    course_project_id: int
    enrolled_at: datetime | None = None
    request_key: UUID
    expected_student_version: int = Field(gt=0)


class EnrollmentUpdateIn(BaseModel):
    """结束/恢复项目关联（API045）。"""
    model_config = {"extra": "forbid"}

    status: Literal["ENROLLED", "COMPLETED", "WITHDRAWN"]
    ended_at: datetime | None = None
    expected_version: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=2000)
    request_key: UUID
