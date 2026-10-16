"""
crm_lead 模型（M1-05 范围判断用）

⚠️ 特别注意：dept_id 是必填（建库验证时发现的）。
"""
from sqlalchemy import BigInteger, String
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
