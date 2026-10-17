from datetime import date
from typing import Literal
from uuid import UUID, uuid4
from app.core.dto import BaseModel
from pydantic import ConfigDict, Field, AliasChoices, model_validator


class Strict(BaseModel):
    model_config=ConfigDict(extra="forbid")

class WorkItem(Strict):
    category: Literal["CUSTOMER","DELIVERY","ENROLLMENT","PSYCH","COMPLAINT","LEAVE","OTHER"]="OTHER"
    description: str=Field(min_length=1,max_length=2000)
    student_ids: list[str]=Field(default_factory=list,max_length=20)
    source_event_id: str | None=None
    count: int=Field(default=1,ge=0,le=10000)
    result: str=""

class DailyContent(Strict):
    work_summary: str=Field(default="",max_length=5000)
    items: list[WorkItem]=Field(default_factory=list,max_length=100)
    difficulties: str=Field(default="",max_length=3000)
    next_plan: str=Field(default="",max_length=3000)

class DailyIn(Strict):
    request_key: UUID = Field(default_factory=uuid4)
    report_date: date
    original_text: str=Field(default="",max_length=20000)
    content: DailyContent=Field(validation_alias=AliasChoices("content","structured_content"))
    expected_version: int | None=Field(default=None,gt=0)

class DecisionIn(Strict):
    request_key: UUID = Field(default_factory=uuid4)
    action: Literal["SUBMIT","WITHDRAW","APPROVE","RETURN"]
    expected_version: int=Field(gt=0)
    reason: str=Field(default="",max_length=2000)

class GenerateIn(Strict):
    type: Literal["CUSTOMER_OPERATION","DAILY_DAY","DAILY_WEEK","PSYCH_WEEK","COMPLAINT_WEEK","MANAGER_WEEK"]
    start_date: date
    end_date: date
    employee_user_ids: list[str]=Field(default_factory=list,max_length=100)
    @model_validator(mode="before")
    @classmethod
    def legacy_types(cls,data):
        if isinstance(data,dict):
            data=dict(data)
            data['type']={'customer':'CUSTOMER_OPERATION','daily':'DAILY_WEEK','psych':'PSYCH_WEEK','complaint':'COMPLAINT_WEEK'}.get(data.get('type'),data.get('type'))
        return data
    @model_validator(mode="after")
    def check_range(self):
        if self.end_date<self.start_date or (self.end_date-self.start_date).days>366:
            raise ValueError("统计范围应在一年以内，结束日期不能早于开始日期")
        return self

class ReportSaveIn(Strict):
    snapshot_id: str | None = None
    request_key: UUID = Field(default_factory=uuid4)
    employee_user_ids: list[str]=Field(default_factory=list,max_length=100)
    id: str | None=None
    title: str=Field(min_length=1,max_length=160)
    type: Literal["CUSTOMER_OPERATION","DAILY_DAY","DAILY_WEEK","PSYCH_WEEK","COMPLAINT_WEEK","MANAGER_WEEK"]
    start_date: date
    end_date: date
    @model_validator(mode="after")
    def check_save_range(self):
        if self.end_date<self.start_date or (self.end_date-self.start_date).days>366:
            raise ValueError("报告日期范围不正确")
        return self
    narrative: str=Field(min_length=1,max_length=30000)
    expected_version: int | None=Field(default=None,gt=0)

class ChatIn(Strict):
    message: str=Field(min_length=1,max_length=8000)
    request_key: UUID
    expected_version: int=Field(gt=0)
    student_id: str | None=None
    report_date: date | None=None

class VersionRequest(Strict):
    request_key: UUID = Field(default_factory=uuid4)
    expected_version: int=Field(gt=0)

class DailySaveIn(Strict):
    request_key: UUID = Field(default_factory=uuid4)
    original_text: str=Field(default="",max_length=20000)
    content: DailyContent
    expected_version: int | None=Field(default=None,gt=0)

class AIDraftIn(Strict):
    message: str=Field(min_length=1,max_length=8000)
    content: DailyContent=Field(default_factory=DailyContent)
    student_id: str | None=None

class ReturnRequest(VersionRequest):
    reason: str=Field(min_length=1,max_length=2000)
