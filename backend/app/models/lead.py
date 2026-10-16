"""
crm_lead 模型

M1 原只映射 Scope 需要的字段；这里补全 M4 读接口（API093 签约前评估摘要）需要的研判字段。
"""
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Integer, String
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
    dept_id: Mapped[int] = mapped_column(BigInteger)                # 所属部门

    # ---- 研判（M2 写，M4 只读）----
    intended_project_id: Mapped[int | None] = mapped_column(BigInteger)
    assessment_report: Mapped[dict | None] = mapped_column(JSONB)   # 最近成功研判报告
    latest_score: Mapped[int | None] = mapped_column(Integer)
    assessment_status: Mapped[str] = mapped_column(String(20), default="NONE")
    assessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
