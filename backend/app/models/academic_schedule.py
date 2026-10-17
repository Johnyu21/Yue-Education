"""
student_academic_schedule 模型 —— 合成教务节点与学生单次提醒

data_source 本轮固定 TEST（种子数据），学生只读；remind_at 可由学生设置/取消。
"""
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class StudentAcademicSchedule(Base):
    __tablename__ = "student_academic_schedule"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    student_profile_id: Mapped[int] = mapped_column(BigInteger)
    enrollment_id: Mapped[int | None] = mapped_column(BigInteger)
    schedule_type: Mapped[str] = mapped_column(String(20))          # EXAM/DEADLINE/CLASS/APPLICATION/OTHER
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    location: Mapped[str | None] = mapped_column(String(200))
    remind_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reminder_revision: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="SCHEDULED")
    data_source: Mapped[str] = mapped_column(String(20), default="TEST")
    created_by_user_id: Mapped[int] = mapped_column(BigInteger)
    version: Mapped[int] = mapped_column(Integer, default=1)
    __mapper_args__ = {"version_id_col": version}
    create_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    update_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc))
