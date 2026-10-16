"""
student_application_progress 模型 —— 申请进度（文书/院校/签证）同表分组保存独立事项及追加历史

同一 case_no 为一事项，sequence_no 递增、previous_id 防分叉；学生只读。
"""
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class StudentApplicationProgress(Base):
    __tablename__ = "student_application_progress"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    case_no: Mapped[object] = mapped_column(Uuid)                    # 同一事项固定 UUID
    student_profile_id: Mapped[int] = mapped_column(BigInteger)
    enrollment_id: Mapped[int | None] = mapped_column(BigInteger)
    sequence_no: Mapped[int] = mapped_column(Integer)                # 事项内递增
    previous_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    item_type: Mapped[str] = mapped_column(String(20))               # DOCUMENT/SCHOOL/VISA
    title: Mapped[str] = mapped_column(String(160))
    target_country: Mapped[str | None] = mapped_column(String(80))
    target_school: Mapped[str | None] = mapped_column(String(160))
    target_program: Mapped[str | None] = mapped_column(String(160))
    stage: Mapped[str] = mapped_column(String(20))                   # SUBMITTED/PROCESSING/COMPLETED/NOTIFIED
    event_kind: Mapped[str] = mapped_column(String(20), default="STAGE")  # STAGE/DETAIL/ASSIGNMENT
    detail: Mapped[str | None] = mapped_column(Text)
    assignee_user_id: Mapped[int] = mapped_column(BigInteger)
    recorded_by_user_id: Mapped[int] = mapped_column(BigInteger)
    data_source: Mapped[str] = mapped_column(String(20), default="MANUAL")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    request_key: Mapped[object] = mapped_column(Uuid, unique=True)
    create_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
