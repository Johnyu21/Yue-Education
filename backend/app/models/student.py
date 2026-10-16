"""
student_profile 模型（M1-05 只需范围判断用到的字段）

完整字段见 schema.sql。这里只映射 Scope 需要的列。
"""
from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class StudentProfile(Base):
    __tablename__ = "student_profile"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True)      # 指向 sys_user
    converted_lead_id: Mapped[int | None] = mapped_column(BigInteger)   # 转化自哪条线索
    advisor_user_id: Mapped[int | None] = mapped_column(BigInteger)     # 负责顾问
    dept_id: Mapped[int] = mapped_column(BigInteger)                    # 所属部门
    class_id: Mapped[int | None] = mapped_column(BigInteger)            # 所属班级
    status: Mapped[str] = mapped_column(String(30), default="ENROLLED")
