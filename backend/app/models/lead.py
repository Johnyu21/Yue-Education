"""
crm_lead 模型 —— 客户主档（三渠道统一获客 + 研判）

M1 原只映射 Scope 需要的字段；M4 补了签约前评估摘要所需字段；
M2 补齐获客/事实/完整度/研判/签约与流失字段，并把 dept_id 放宽为可空
（DDL 中 crm_lead.dept_id 本就可空：未路由客户进管理员待分配池）。
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import BigInteger, Date, DateTime, Integer, Numeric, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class CrmLead(Base):
    __tablename__ = "crm_lead"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str | None] = mapped_column(String(80))
    mobile: Mapped[str] = mapped_column(String(32), unique=True)
    source: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="NEW")
    owner_user_id: Mapped[int | None] = mapped_column(BigInteger)   # 负责顾问
    dept_id: Mapped[int | None] = mapped_column(BigInteger)         # 所属部门（未路由时可空）

    # ---- 获客事实（M2 写）----
    gender: Mapped[str | None] = mapped_column(String(20))
    city: Mapped[str | None] = mapped_column(String(100))
    education: Mapped[str | None] = mapped_column(String(80))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    study_purpose: Mapped[str | None] = mapped_column(String(30))
    interest_level: Mapped[str | None] = mapped_column(String(30))
    profile_completeness: Mapped[str] = mapped_column(String(20), default="MINIMAL")
    profile_summary: Mapped[dict | None] = mapped_column(JSONB)      # 核对后的基础事实与证据
    resume_object_key: Mapped[str | None] = mapped_column(String(500))

    # ---- 研判（M2 写，M4 只读）----
    intended_project_id: Mapped[int | None] = mapped_column(BigInteger)
    assessment_report: Mapped[dict | None] = mapped_column(JSONB)   # 最近成功研判报告
    latest_score: Mapped[int | None] = mapped_column(Integer)
    assessment_status: Mapped[str] = mapped_column(String(20), default="NONE")
    assessment_request_id: Mapped[UUID | None] = mapped_column(Uuid)   # 当前研判请求，防旧任务覆盖
    assessment_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assessment_error_code: Mapped[str | None] = mapped_column(String(60))
    assessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # ---- 跟进/签约/流失 ----
    next_follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lost_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    loss_reason: Mapped[str | None] = mapped_column(Text)
    contract_ref: Mapped[str | None] = mapped_column(String(100))
    contract_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    contract_currency: Mapped[str | None] = mapped_column(String(3))

    # ---- 幂等与并发 ----
    request_key: Mapped[UUID] = mapped_column(Uuid, unique=True)     # 首次创建幂等键
    version: Mapped[int] = mapped_column(Integer, default=1)
    __mapper_args__ = {"version_id_col": version}

    create_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    update_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
