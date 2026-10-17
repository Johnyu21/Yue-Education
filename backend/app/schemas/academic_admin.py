from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import AwareDatetime, Field, model_validator
from app.core.dto import BaseModel

class ScoreWrite(BaseModel):
    request_key: UUID
    expected_version: int | None = Field(default=None,gt=0)
    enrollment_id: int | None = None
    schedule_id: int | None = None
    subject: str = Field(min_length=1,max_length=120)
    score_type: Literal['NUMERIC','GRADE','PASS_FAIL']
    score_text: str = Field(min_length=1,max_length=80)
    score_numeric: Decimal | None = None
    max_score: Decimal | None = None
    graded_at: date | None = None
    remark: str | None = Field(default=None,max_length=2000)
    @model_validator(mode='after')
    def check_score(self):
        if self.score_type=='NUMERIC':
            if self.score_numeric is None or self.max_score is None or not self.score_numeric.is_finite() or not self.max_score.is_finite() or self.max_score<=0 or not 0<=self.score_numeric<=self.max_score:
                raise ValueError('数值成绩必须在0到满分之间')
        elif self.score_numeric is not None or self.max_score is not None:raise ValueError('非数值成绩不能填写分数或满分')
        if self.score_type=='PASS_FAIL' and self.score_text not in {'PASS','FAIL'}:raise ValueError('通过制使用PASS/FAIL')
        return self

class ScheduleWrite(BaseModel):
    request_key: UUID
    expected_version: int | None = Field(default=None,gt=0)
    enrollment_id: int | None = None
    schedule_type: Literal['EXAM','DEADLINE','CLASS','APPLICATION','OTHER']
    title: str = Field(min_length=1,max_length=160)
    description: str | None = Field(default=None,max_length=10000)
    start_at: AwareDatetime
    end_at: AwareDatetime | None = None
    location: str | None = Field(default=None,max_length=200)
    status: Literal['SCHEDULED','COMPLETED','CANCELLED'] = 'SCHEDULED'
    @model_validator(mode='after')
    def check_period(self):
        if self.end_at is not None and self.end_at<=self.start_at:raise ValueError('结束必须晚于开始')
        return self
