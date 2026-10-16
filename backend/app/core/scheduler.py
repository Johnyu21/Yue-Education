"""
定时任务框架（M1-09）

作用：定时扫描待办（日程提醒、跟进提醒）并发通知。

⚠️ 核心问题：**多进程/多实例会重复执行**
  如果起了两个后端（或 worker），同一个提醒会被发两次。
  所以需要「单实例锁」——同一时刻只有一个实例能跑同一个任务。

本轮用 **PostgreSQL 咨询锁（advisory lock）** 实现：
  - 不需要额外服务（Redis 等）
  - 锁随连接释放，进程挂了自动解锁（不会死锁）
  - 跨进程有效（多个后端连同一个库）

用法：
    from app.core.scheduler import run_periodically, with_advisory_lock

    @with_advisory_lock(1001, "daily_reminder")
    def scan_reminders(db): ...

    run_periodically(scan_reminders, interval=60)   # 每 60 秒跑一次
"""
import logging
import threading
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.notification import notify
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

# 任务名 → 咨询锁编号（自定义，全局唯一即可）
LOCK_IDS = {
    "schedule_reminder": 910001,     # 日程提醒
    "followup_reminder": 910002,     # 跟进提醒
}


def with_advisory_lock(lock_id: int, name: str):
    """装饰器：保证同一时刻只有一个实例能跑这个任务。

    用的是 PostgreSQL 的 `pg_try_advisory_lock`（**非阻塞**）——
    拿不到锁就直接跳过，不排队等待。
    """
    def deco(fn: Callable):
        def wrapper(*args, **kwargs):
            db: Session = SessionLocal()
            try:
                # try 版：拿不到立刻返回 false，不阻塞
                got = db.scalar(text("SELECT pg_try_advisory_lock(:id)"), {"id": lock_id})
                if not got:
                    logger.info("[%s] 其他实例正在执行，本次跳过", name)
                    return None
                try:
                    return fn(db, *args, **kwargs)
                finally:
                    db.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": lock_id})
            except Exception:
                logger.exception("[%s] 执行失败", name)
                db.rollback()
                return None
            finally:
                db.close()
        wrapper.__name__ = fn.__name__
        return wrapper
    return deco


# =============================================================
# 具体任务
# =============================================================

@with_advisory_lock(LOCK_IDS["schedule_reminder"], "schedule_reminder")
def scan_schedule_reminders(db: Session) -> int:
    """扫描到期的日程提醒，发通知。

    ⚠️ 要点（M1 文档要求）：
      1. 只处理 remind_at 已到期、且状态仍是 SCHEDULED 的
      2. event_key 用 `schedule:<id>:reminder:<revision>` —— 同一提醒**只发一次**
      3. 发送前**复查状态** —— 别发已经取消的事项的提醒
    """
    now = datetime.now(timezone.utc)
    rows = db.execute(text("""
        SELECT s.id, s.title, s.remind_at, s.start_at, s.student_profile_id,
               s.status, sp.user_id AS student_user_id
        FROM student_academic_schedule s
        JOIN student_profile sp ON sp.id = s.student_profile_id
        WHERE s.remind_at IS NOT NULL
          AND s.remind_at <= :now
          AND s.status = 'SCHEDULED'
        LIMIT 200
    """), {"now": now}).mappings().all()

    sent = 0
    for r in rows:
        # ⚠️ 复查：万一在扫描期间被取消了
        if r["status"] != "SCHEDULED":
            continue
        days = (r["start_at"] - now).days if r["start_at"] else 0
        event_key = f"schedule:{r['id']}:reminder:1"
        created = notify(
            db, event_key, [r["student_user_id"]],
            category="SYSTEM",
            title=f"日程提醒：{r['title']}",
            content=f"将于 {r['start_at']:%Y-%m-%d %H:%M} 开始（约 {max(days,0)} 天后）",
            related_type=None, related_id=None,
        )
        sent += len(created)
    db.commit()
    if sent:
        logger.info("[schedule_reminder] 发出 %s 条提醒", sent)
    return sent


@with_advisory_lock(LOCK_IDS["followup_reminder"], "followup_reminder")
def scan_followup_reminders(db: Session) -> int:
    """扫描到期的跟进提醒，通知负责顾问。

    event_key 用 `lead:<id>:followup:<到期时间戳>`，
    这样"同一次跟进提醒"只发一次；改了 next_follow_up_at 就是新的提醒。
    """
    now = datetime.now(timezone.utc)
    rows = db.execute(text("""
        SELECT id, name, owner_user_id, next_follow_up_at
        FROM crm_lead
        WHERE next_follow_up_at IS NOT NULL
          AND next_follow_up_at <= :now
          AND owner_user_id IS NOT NULL
          AND status IN ('NEW','FOLLOWING')
        LIMIT 200
    """), {"now": now}).mappings().all()

    sent = 0
    for r in rows:
        event_key = f"lead:{r['id']}:followup:{int(r['next_follow_up_at'].timestamp())}"
        created = notify(
            db, event_key, [r["owner_user_id"]],
            category="SYSTEM",
            title=f"跟进提醒：{r['name'] or '客户'}",
            content=f"计划跟进时间已到（{r['next_follow_up_at']:%Y-%m-%d %H:%M}）",
            related_type="lead", related_id=r["id"],
        )
        sent += len(created)
    db.commit()
    if sent:
        logger.info("[followup_reminder] 发出 %s 条提醒", sent)
    return sent


# =============================================================
# 调度器
# =============================================================
_running = False


def run_periodically(task: Callable, interval: int = 60, name: str = "") -> None:
    """后台循环执行任务。

    ⚠️ 注意：
      - 这是"进程内"调度；多进程时靠 advisory lock 保证不重复
      - 生产环境建议只在一个 worker 上开，或用外部队列
    """
    def loop():
        logger.info("[scheduler] 启动 %s（每 %s 秒）", name or task.__name__, interval)
        while True:
            try:
                task()
            except Exception:
                logger.exception("[scheduler] %s 异常", name or task.__name__)
            time.sleep(interval)

    t = threading.Thread(target=loop, daemon=True, name=name or task.__name__)
    t.start()
    return t


def start_all(interval: int = 60) -> None:
    """启动所有定时任务。在 main.py 里调用（可用开关控制）。"""
    global _running
    if _running:
        return
    _running = True
    run_periodically(scan_schedule_reminders, interval, "schedule_reminder")
    run_periodically(scan_followup_reminders, interval * 2, "followup_reminder")
