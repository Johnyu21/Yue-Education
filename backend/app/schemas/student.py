"""
学生档案 / 成绩 / 日程 / 申请进度 请求与响应 DTO
"""
from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


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
    classInfo: StudentClassBrief | None = None   # 04 文档的 class 字段（保留字，用 classInfo）
    advisor: StudentAdvisorBrief | None = None
    enrollments: list[StudentEnrollmentItem] = []
    version: int


class ScoreDTO(BaseModel):
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
