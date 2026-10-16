"""
notification 模型（M1-07）

⚠️ business_event_key 唯一（配合 recipient_user_id）→ 同一事件只发一条。
⚠️ related_type 和 related_id 必须同时有或同时无（数据库 CHECK）。
"""
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Notification(Base):
    __tablename__ = "notification"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    recipient_user_id: Mapped[int] = mapped_column(BigInteger)
    category: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(160))
    content: Mapped[str] = mapped_column(String(1000))
    related_type: Mapped[str | None] = mapped_column(String(40))
    related_id: Mapped[int | None] = mapped_column(BigInteger)
    business_event_key: Mapped[str] = mapped_column(String(180))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    create_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
