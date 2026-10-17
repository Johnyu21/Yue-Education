"""
心理关怀模型 —— student_psych_profile（逐条版本化情绪观测）+ student_psych_alert（需人工复核的关怀事件）

⚠️ 敏感：读取必须 psych_access_enabled；告警正文不含学生敏感原文。
"""
from datetime import date, datetime, timezone

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Integer, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class StudentPsychProfile(Base):
    __tablename__ = "student_psych_profile"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    student_profile_id: Mapped[int] = mapped_column(BigInteger)
    version_no: Mapped[int] = mapped_column(Integer)                 # 该学生递增版本
    assessment_date: Mapped[date] = mapped_column(Date)             # 业务时区自然日
    business_timezone: Mapped[str] = mapped_column(String(64))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_event_key: Mapped[object] = mapped_column(Uuid, unique=True)  # 幂等键
    assessment_source: Mapped[str] = mapped_column(String(20))       # DIFY/RULE/MANUAL
    emotion_state: Mapped[str] = mapped_column(String(20))           # HEALTHY/NEGATIVE/VERY_NEGATIVE/UNKNOWN
    assessment_data: Mapped[dict] = mapped_column(JSONB)             # 置信度/规则版本/最小证据摘要
    summary: Mapped[str | None] = mapped_column(Text)
    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="AUTO_RECORDED")
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True)
    invalidated_reason: Mapped[str | None] = mapped_column(Text)
    replaces_profile_id: Mapped[int | None] = mapped_column(BigInteger)
    created_by_user_id: Mapped[int | None] = mapped_column(BigInteger)
    verified_by_user_id: Mapped[int | None] = mapped_column(BigInteger)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    create_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class StudentPsychAlert(Base):
    __tablename__ = "student_psych_alert"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    student_profile_id: Mapped[int] = mapped_column(BigInteger)
    psych_profile_id: Mapped[int] = mapped_column(BigInteger)        # 最近触发的同学生观测
    severity: Mapped[str] = mapped_column(String(20))                # HIGH/MEDIUM/LOW
    signal_code: Mapped[str] = mapped_column(String(40))
    trigger_summary: Mapped[str] = mapped_column(Text)               # 不含敏感原话
    status: Mapped[str] = mapped_column(String(20), default="PENDING_REVIEW")
    follow_up_user_id: Mapped[int | None] = mapped_column(BigInteger)
    created_by_user_id: Mapped[int | None] = mapped_column(BigInteger)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(BigInteger)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    action_note: Mapped[str | None] = mapped_column(Text)
    handling_history: Mapped[list] = mapped_column(JSONB, default=list)
    trigger_key: Mapped[str] = mapped_column(String(160), unique=True)
    repeat_count: Mapped[int] = mapped_column(Integer, default=1)
    last_triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1)
    __mapper_args__ = {"version_id_col": version}
    create_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    update_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc))
