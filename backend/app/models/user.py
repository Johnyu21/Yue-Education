"""
sys_user 模型（M1-04 只做认证需要的字段）

注意：这里只映射认证用到的列。完整字段见 schema.sql。
      其他字段（can_handle_feedback 等）等对应模块再加，
      但列名必须和数据库一致。
"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class SysUser(Base):
    __tablename__ = "sys_user"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    real_name: Mapped[str] = mapped_column(String(80))
    user_type: Mapped[str] = mapped_column(String(20))          # STUDENT / EMPLOYEE
    employee_role: Mapped[str | None] = mapped_column(String(30))  # NEWCOMER/ADVISOR/...
    dept_id: Mapped[int | None] = mapped_column(BigInteger)
    contact_info: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(20), default="NORMAL")

    can_handle_feedback: Mapped[bool] = mapped_column(Boolean, default=False)
    psych_access_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    temporary_password_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    token_version: Mapped[int] = mapped_column(Integer, default=0)

    # 只读属性：方便判断
    @property
    def is_student(self) -> bool:
        return self.user_type == "STUDENT"

    @property
    def is_employee(self) -> bool:
        return self.user_type == "EMPLOYEE"
