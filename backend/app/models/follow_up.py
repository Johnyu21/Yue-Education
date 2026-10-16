"""
crm_follow_up 模型 —— 客户跟进/状态/分配事件（不可删除）

API095 升学意向确认会追加 UPSELL_INTEREST 跟进并通知顾问（与 M3 共用此表）。
"""
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class CrmFollowUp(Base):
    __tablename__ = "crm_follow_up"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    lead_id: Mapped[int] = mapped_column(BigInteger)
    actor_user_id: Mapped[int | None] = mapped_column(BigInteger)
    follow_up_type: Mapped[str] = mapped_column(String(30))          # ACQUIRED/CLAIMED/.../UPSELL_INTEREST
    content: Mapped[str] = mapped_column(Text)
    status_before: Mapped[str | None] = mapped_column(String(20))
    status_after: Mapped[str | None] = mapped_column(String(20))
    next_follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    details: Mapped[dict | None] = mapped_column(JSONB)
    request_key: Mapped[object] = mapped_column(Uuid, unique=True)
    create_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
