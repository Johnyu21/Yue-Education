"""
事务管理（M1 补充）—— 多表操作的命根子

作用：一次业务改动涉及多张表时，**要么全成功、要么全回滚**。

⚠️ 为什么必须有它：
    "签约转学生"要同时做 5 件事：
      建账号 → 建档案 → 建课程关联 → 改线索状态 → 写跟进记录
    如果第 3 步失败，前 2 步已经写进数据库了 → **脏数据**。
    有了事务，失败时前 2 步自动撤销。

用法：
    from app.core.transaction import with_business_transaction

    def convert_lead(db, lead, ...):
        with with_business_transaction(db):
            account = create_account(db, ...)
            profile = create_profile(db, account, ...)
            enroll  = create_enrollment(db, profile, ...)
            lead.status = "SIGNED"
            add_follow_up(db, lead, ...)
        # 块内任一步抛异常 → 全部回滚，一行都不留
"""
import logging
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.core.errors import DuplicateResourceError, StateConflictError

logger = logging.getLogger(__name__)


class _Outcome:
    """记录事务结果，供块内代码判断（如"是否插入成功"）。"""
    def __init__(self):
        self.committed = False


@contextmanager
def with_business_transaction(db: Session) -> Iterator[_Outcome]:
    """业务事务上下文。

    - 正常结束 → commit
    - 抛异常   → rollback，并把底层异常翻译成业务异常
    """
    outcome = _Outcome()
    try:
        yield outcome
        db.commit()
        outcome.committed = True
    except Exception as exc:
        db.rollback()
        # 把数据库异常翻译成对用户友好的业务异常
        friendly = _translate(exc)
        if friendly is not exc:
            logger.warning("事务回滚（已翻译）: %s", exc.__class__.__name__)
            raise friendly from exc
        logger.exception("事务回滚（未翻译异常）")
        raise


def _translate(exc: Exception) -> Exception:
    """把底层数据库错误翻译成 AppError，避免 500 泄露细节。"""
    if isinstance(exc, IntegrityError):
        msg = str(exc.orig) if exc.orig else str(exc)
        low = msg.lower()
        if "duplicate key" in low or "unique" in low:
            # 如手机号已存在、重复报名
            return DuplicateResourceError("数据已存在（可能重复提交）")
        if "foreign key" in low:
            return StateConflictError("关联数据不存在或状态不允许")
        if "check constraint" in low:
            return StateConflictError("数据不满足业务规则")
        return StateConflictError("数据冲突")
    if isinstance(exc, (OperationalError, DBAPIError)):
        logger.error("数据库连接类错误: %s", exc.__class__.__name__)
    return exc


@contextmanager
def safe_commit(db: Session):
    """简单写操作用（不涉及多表）。

    与 with_business_transaction 的区别：
      - 这个不翻译异常，适合单表简单写
      - 复杂的多表业务用 with_business_transaction
    """
    try:
        yield
        db.commit()
    except Exception:
        db.rollback()
        raise
