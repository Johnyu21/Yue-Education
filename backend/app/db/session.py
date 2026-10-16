"""
数据库 Session 管理（M1-03）

作用：统一'连库 / 关库 / 事务'，业务代码不用自己管连接。

用法（在接口里）：
    from app.db.session import get_db
    @router.get("/xxx")
    def xxx(db: Session = Depends(get_db)):
        ...

事务规则（重要）：
  - 一次业务写入 = 一个 service 管一个事务
  - 出错自动 rollback，结束自动 close
  - 业务代码不要自己 commit（除非明确知道在做什么）
"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """所有模型（表）的基类。models/ 里的类都继承它。"""
    pass


# 连接池：pool_pre_ping 防"连接断了还在用"，会自动重连
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=False,          # True 会打印所有 SQL，调试时可开
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：每个请求一个 Session，用完自动关。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
