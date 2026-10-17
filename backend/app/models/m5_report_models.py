from datetime import datetime, timezone, date
from sqlalchemy import Date, DateTime, String, Integer, BigInteger, Text, JSON, UniqueConstraint, ForeignKey, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base

def now():
    return datetime.now(timezone.utc).isoformat()

def utcnow():
    return datetime.now(timezone.utc)

class Daily(Base):
    __tablename__="m5_daily"
    __table_args__=(UniqueConstraint("user_id","report_date",name="uq_m5_daily_user_date"),
        CheckConstraint("status IN ('DRAFT','SUBMITTED','APPROVED','RETURNED')",name="ck_m5_daily_status"),
        Index("ix_m5_daily_dept_date","dept_id","report_date"),)
    id: Mapped[str]=mapped_column(String,primary_key=True)
    user_id: Mapped[int]=mapped_column(BigInteger, ForeignKey("sys_user.id"))
    dept_id: Mapped[int]=mapped_column(BigInteger, ForeignKey("sys_department.id"))
    report_date: Mapped[date]=mapped_column(Date)
    original_text: Mapped[str]=mapped_column(Text,default="")
    content: Mapped[dict]=mapped_column(JSON,default=dict)
    status: Mapped[str]=mapped_column(String,default="DRAFT")
    return_reason: Mapped[str]=mapped_column(Text,default="")
    version: Mapped[int]=mapped_column(Integer,default=1)
    required_capabilities: Mapped[list]=mapped_column(JSON,default=list)
    approved_required_capabilities: Mapped[list]=mapped_column(JSON,default=list)
    approved_version: Mapped[int | None]=mapped_column(Integer,nullable=True)
    approved_at: Mapped[datetime | None]=mapped_column(DateTime(timezone=True),nullable=True)
    approved_snapshot: Mapped[dict | None]=mapped_column(JSON(none_as_null=True),nullable=True)
    submitted_at: Mapped[datetime | None]=mapped_column(DateTime(timezone=True),nullable=True)
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class Report(Base):
    __table_args__=(CheckConstraint("status IN ('DRAFT','SUBMITTED')",name="ck_m5_report_status"),Index("ix_m5_report_dept_owner","dept_id","owner_id"))
    __tablename__="m5_report"
    id: Mapped[str]=mapped_column(String,primary_key=True)
    owner_id: Mapped[int]=mapped_column(BigInteger, ForeignKey("sys_user.id"))
    dept_id: Mapped[int | None]=mapped_column(BigInteger, ForeignKey("sys_department.id"),nullable=True)
    required_capabilities: Mapped[list]=mapped_column(JSON,default=list)
    snapshot_id: Mapped[str | None]=mapped_column(String,nullable=True)
    kind: Mapped[str]=mapped_column(String)
    scope_employee_ids: Mapped[list]=mapped_column(JSON,default=list)
    scope_student_ids: Mapped[list]=mapped_column(JSON,default=list)
    title: Mapped[str]=mapped_column(String)
    start_date: Mapped[date]=mapped_column(Date)
    end_date: Mapped[date]=mapped_column(Date)
    narrative: Mapped[str]=mapped_column(Text)
    metrics: Mapped[list]=mapped_column(JSON)
    scope: Mapped[str]=mapped_column(String)
    ai_status: Mapped[str]=mapped_column(String)
    warnings: Mapped[list]=mapped_column(JSON)
    status: Mapped[str]=mapped_column(String,default="DRAFT")
    version: Mapped[int]=mapped_column(Integer,default=1)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class Chat(Base):
    __tablename__="m5_chat"
    user_id: Mapped[int]=mapped_column(BigInteger, ForeignKey("sys_user.id"),primary_key=True)
    messages: Mapped[list]=mapped_column(JSON,default=list)
    draft: Mapped[dict]=mapped_column(JSON,default=dict)
    last_key: Mapped[str]=mapped_column(String,default="")
    last_result: Mapped[dict]=mapped_column(JSON,default=dict)
    version: Mapped[int]=mapped_column(Integer,default=1)


class DailyRevision(Base):
    __tablename__='m5_daily_revision'
    __table_args__=(UniqueConstraint('daily_id','version'),)
    id: Mapped[str]=mapped_column(String,primary_key=True)
    daily_id: Mapped[str]=mapped_column(String,ForeignKey('m5_daily.id'))
    version: Mapped[int]=mapped_column(Integer)
    approved_by: Mapped[int]=mapped_column(BigInteger,ForeignKey('sys_user.id'))
    approved_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    content: Mapped[dict]=mapped_column(JSON)
    required_capabilities: Mapped[list]=mapped_column(JSON)

class GeneratedSnapshot(Base):
    __tablename__='m5_report_snapshot'
    id: Mapped[str]=mapped_column(String,primary_key=True)
    owner_id: Mapped[int]=mapped_column(BigInteger,ForeignKey('sys_user.id'))
    request_data: Mapped[dict]=mapped_column(JSON)
    response_data: Mapped[dict]=mapped_column(JSON)
    student_ids: Mapped[list]=mapped_column(JSON)
    required_capabilities: Mapped[list]=mapped_column(JSON)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
