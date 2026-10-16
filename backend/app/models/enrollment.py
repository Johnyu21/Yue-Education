"""
student_course_enrollment 模型 —— 学生多项目关联

一个学生可报名多个课程项目，一个项目一名学生一条关联（UNIQUE 约束）。
"""
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class StudentCourseEnrollment(Base):
    __tablename__ = "student_course_enrollment"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    student_profile_id: Mapped[int] = mapped_column(BigInteger)      # 学生
    course_project_id: Mapped[int] = mapped_column(BigInteger)       # 项目
    status: Mapped[str] = mapped_column(String(20), default="ENROLLED")
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1)
