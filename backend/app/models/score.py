"""
student_score 模型 —— 合成成绩（只读，不提供业务写接口）

data_source 本轮固定 TEST；score_type NUMERIC/GRADE/PASS_FAIL。
"""
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class StudentScore(Base):
    __tablename__ = "student_score"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    student_profile_id: Mapped[int] = mapped_column(BigInteger)
    enrollment_id: Mapped[int | None] = mapped_column(BigInteger)
    schedule_id: Mapped[int | None] = mapped_column(BigInteger)
    subject: Mapped[str] = mapped_column(String(120))
    score_type: Mapped[str] = mapped_column(String(20))             # NUMERIC/GRADE/PASS_FAIL
    score_text: Mapped[str] = mapped_column(String(80))
    score_numeric: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    max_score: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    graded_at: Mapped[date | None] = mapped_column(Date)
    recorded_by_user_id: Mapped[int] = mapped_column(BigInteger)
    remark: Mapped[str | None] = mapped_column(Text)
    data_source: Mapped[str] = mapped_column(String(20), default="TEST")
    create_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
