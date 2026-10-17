"""
course_project 模型 —— 项目展示（M2 负责写入，M4 只读用于课程关联/升学推荐/可见摘要）

M4 已建基础字段；M2 追加经审核的结构化准入条件与路由部门、规则审核信息。
"""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class CourseProject(Base):
    __tablename__ = "course_project"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    country: Mapped[str | None] = mapped_column(String(80))
    education_level: Mapped[str | None] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text)
    admission_requirements: Mapped[str | None] = mapped_column(Text)
    faculty_summary: Mapped[str | None] = mapped_column(Text)
    duration_months: Mapped[int | None] = mapped_column(Integer)
    fee_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    fee_currency: Mapped[str | None] = mapped_column(String(3))
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    __mapper_args__ = {"version_id_col": version}
    create_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    update_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc))

    # ---- M2 追加：结构化准入条件与审核信息（仅追加，不改 M4 已用字段）----
    admission_rules: Mapped[dict | None] = mapped_column(JSONB)      # 经审核的结构化条件与可选评分规则
    rule_version: Mapped[str | None] = mapped_column(String(40))
    rule_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rule_approved_by: Mapped[int | None] = mapped_column(BigInteger)
    default_dept_id: Mapped[int | None] = mapped_column(BigInteger)  # 新线索路由部门
