"""
student_profile 模型

完整字段对齐 deploy/schema.sql 的 student_profile 表。
M1 原只映射 Scope 需要的列，这里补全 M4 需要的业务字段（档案、心理授权、版本、时间）。
"""
from datetime import date, datetime, timezone

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class StudentProfile(Base):
    __tablename__ = "student_profile"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True)          # 指向 sys_user
    converted_lead_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)  # 来源客户
    advisor_user_id: Mapped[int | None] = mapped_column(BigInteger)        # 个人顾问
    dept_id: Mapped[int] = mapped_column(BigInteger)                       # 业务部门
    class_id: Mapped[int | None] = mapped_column(BigInteger)               # 当前行政班

    gender: Mapped[str | None] = mapped_column(String(20))
    city: Mapped[str | None] = mapped_column(String(100))
    education: Mapped[str | None] = mapped_column(String(80))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    enrollment_date: Mapped[date | None] = mapped_column(Date)

    status: Mapped[str] = mapped_column(String(30), default="ENROLLED")

    # 心理观测授权
    psych_consent_status: Mapped[str] = mapped_column(String(20), default="NOT_GIVEN")
    psych_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    psych_consent_version: Mapped[str | None] = mapped_column(String(40))
    psych_withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)

    create_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    update_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc))
