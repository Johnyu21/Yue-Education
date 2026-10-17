"""
student_feedback_ticket 模型 —— 保密售后工单（投诉/建议/咨询）及完整处理/满意度闭环

priority 只由后端按 category 决定（COMPLAINT→HIGH，其余 NORMAL），学生 DTO 不外泄。
"""
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, SmallInteger, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class StudentFeedbackTicket(Base):
    __tablename__ = "student_feedback_ticket"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    student_profile_id: Mapped[int] = mapped_column(BigInteger)
    dept_id: Mapped[int] = mapped_column(BigInteger)                 # 受理部门快照
    assignee_user_id: Mapped[int | None] = mapped_column(BigInteger)  # 售后处理人
    category: Mapped[str] = mapped_column(String(20))                # COMPLAINT/SUGGESTION/CONSULTATION
    subject: Mapped[str] = mapped_column(String(160))
    teacher_name: Mapped[str] = mapped_column(String(80))
    project_category: Mapped[str] = mapped_column(String(80))
    course_project_id: Mapped[int | None] = mapped_column(BigInteger)
    content: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(20))                # HIGH/NORMAL，不向学生返回
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    resolution: Mapped[str | None] = mapped_column(Text)
    first_response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_notified: Mapped[bool] = mapped_column(Boolean, default=False)
    reopened_count: Mapped[int] = mapped_column(Integer, default=0)
    satisfaction_rating: Mapped[int | None] = mapped_column(SmallInteger)
    satisfaction_comment: Mapped[str | None] = mapped_column(Text)
    rated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    handling_history: Mapped[list] = mapped_column(JSONB, default=list)
    request_key: Mapped[object] = mapped_column(Uuid, unique=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    __mapper_args__ = {"version_id_col": version}
    create_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    update_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc))
