"""
student_admin_service 模型 —— 请假 / 考务 / 资料修改申请与审批

handling_history 为 JSONB 数组（固定事件结构），change_request 为 JSONB 对象。
"""
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class StudentAdminService(Base):
    __tablename__ = "student_admin_service"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    student_profile_id: Mapped[int] = mapped_column(BigInteger)
    dept_id: Mapped[int] = mapped_column(BigInteger)                 # 提交时部门快照
    service_type: Mapped[str] = mapped_column(String(20))            # LEAVE/EXAM/INFO_CHANGE/OTHER
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    change_request: Mapped[dict | None] = mapped_column(JSONB)       # INFO_CHANGE 新旧值
    submitted_by_user_id: Mapped[int] = mapped_column(BigInteger)
    assignee_user_id: Mapped[int] = mapped_column(BigInteger)        # 审批人
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    decision_note: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    handling_history: Mapped[list] = mapped_column(JSONB, default=list)
    request_key: Mapped[object] = mapped_column(Uuid, unique=True)   # 幂等键
    version: Mapped[int] = mapped_column(Integer, default=1)
    __mapper_args__ = {"version_id_col": version}
    create_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    update_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc))
