"""
event_lecture / event_registration 模型（M2）

- EventLecture：活动/讲座发布与名额（status: DRAFT/OPEN/ENDED/CANCELLED）
- EventRegistration：报名记录；学生或访客其一（num_nonnulls(student_profile_id, lead_id)=1）
  访客取消凭据只存 sha256 哈希（cancel_token_hash），不存明文
"""
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class EventLecture(Base):
    __tablename__ = "event_lecture"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    course_project_id: Mapped[int | None] = mapped_column(BigInteger)
    host_department_id: Mapped[int | None] = mapped_column(BigInteger)
    organizer_user_id: Mapped[int] = mapped_column(BigInteger)          # 组织员工（必填）
    description: Mapped[str] = mapped_column(Text)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    signup_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    capacity: Mapped[int] = mapped_column(Integer)
    location: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    version: Mapped[int] = mapped_column(Integer, default=1)
    create_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    update_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc))


class EventRegistration(Base):
    __tablename__ = "event_registration"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    event_id: Mapped[int] = mapped_column(BigInteger)
    student_profile_id: Mapped[int | None] = mapped_column(BigInteger)   # 学生报名
    lead_id: Mapped[int | None] = mapped_column(BigInteger)              # 访客报名（必绑线索）
    registrant_name: Mapped[str] = mapped_column(String(80))
    mobile: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(20), default="REGISTERED")
    cancel_token_hash: Mapped[str | None] = mapped_column(String(255))   # 只存哈希
    request_key: Mapped[UUID] = mapped_column(Uuid, unique=True)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1)
