"""
sys_department / sys_class 模型（M1-05）

数据范围（Scope）需要它们判断：
  - sys_department.head_user_id → 谁是部门主管
  - sys_class.head_teacher_id   → 谁是班主任
"""
from sqlalchemy import BigInteger, Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class SysDepartment(Base):
    __tablename__ = "sys_department"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    parent_id: Mapped[int | None] = mapped_column(BigInteger)
    head_user_id: Mapped[int | None] = mapped_column(BigInteger)   # 部门主管
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SysClass(Base):
    __tablename__ = "sys_class"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)   # ⚠️ 班级编码（必填）
    name: Mapped[str] = mapped_column(String(80))
    course_type: Mapped[str | None] = mapped_column(String(80))
    head_teacher_id: Mapped[int | None] = mapped_column(BigInteger)  # 班主任
    dept_id: Mapped[int] = mapped_column(BigInteger)
