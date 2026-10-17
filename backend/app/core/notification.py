"""
通知（M1-07）—— 审批/工单闭环的关键

作用：业务动作发生时，给相关人发站内消息（铃铛）。

⚠️ 三条关键约定（M1 文档要求）：
  1. notify 接受**外部传入的 Session**，绝不内部 commit
     → 这样"业务状态 + 通知"能在同一个事务里，要么全成要么全败
  2. 同一 event_key 对同一人**只发一条**（防重复通知）
  3. 默认标题**不含投诉/心理原文**（敏感信息不进通知）

用法：
    from app.core.notification import notify

    # 在业务事务里调用（跟着业务一起提交）
    with with_business_transaction(db):
        service.status = "APPROVED"
        notify(db, f"service:{service.id}:decision:2",
               recipients=[student_user_id],
               category="SERVICE_DECISION",
               title="您的请假申请已通过",
               related_type="admin_service", related_id=service.id)
    # ⚠️ 别在 notify 里 commit —— 交给外层事务
"""
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notification import Notification

logger = logging.getLogger(__name__)

# 允许跳转的关联类型白名单（防止跳转到非法页面）
RELATED_TYPE_WHITELIST = {
    "admin_service", "feedback_ticket", "psych_alert",
    "lead", "enrollment", "application_case", "event", "report",
}

# 通知类别白名单
CATEGORY_WHITELIST = {
    "SERVICE_DECISION",     # 请假/考务审批结果
    "SERVICE_SUBMITTED",    # 学生提交申请（推给老师）
    "FEEDBACK_HANDLING",    # 工单处理进展
    "FEEDBACK_RESOLVED",    # 工单已解决
    "FEEDBACK_REOPENED",    # 工单被重新打开
    "PSYCH_ALERT",          # 心理预警（⚠️ 不含原文）
    "LEAD_ASSIGNED",        # 线索分配
    "DAILY_REPORT_RETURN",  # 日报退回
    "EVENT_OPENED",         # 新活动
    "SYSTEM",
}


def notify(
    db: Session,
    event_key: str,
    recipients: list[int],
    *,
    category: str,
    title: str,
    content: str = "",
    related_type: str | None = None,
    related_id: int | None = None,
) -> list[Notification]:
    """发通知。**不 commit**，由外层事务统一提交。

    Args:
        event_key: 业务事件键，如 "service:301:decision:2"。
                   同一 (recipient, event_key) 只会有一条 → 天然幂等。
        recipients: 接收人 user_id 列表（去重）
        category: 通知类别（见 CATEGORY_WHITELIST）
        related_type / related_id: 关联业务，用于点击跳转（**必须两个都给或都不给**）

    Returns:
        新建的通知列表（已存在的不会重复创建）

    ⚠️ 调用方必须在事务里 —— 这样业务失败时通知也会回滚。
    """
    # ---- 参数校验 ----
    if category not in CATEGORY_WHITELIST:
        logger.warning("未知通知类别 %s，按 SYSTEM 处理", category)
        category = "SYSTEM"

    if related_type is not None and related_type not in RELATED_TYPE_WHITELIST:
        # 不允许任意跳转（防钓鱼）
        logger.warning("关联类型 %s 不在白名单，忽略跳转", related_type)
        related_type, related_id = None, None

    if (related_type is None) != (related_id is None):
        raise ValueError("related_type 和 related_id 必须同时给或同时不给")

    # ---- 去重 & 创建 ----
    created = []
    for user_id in dict.fromkeys(recipients):        # 去重且保序
        from sqlalchemy.dialects.postgresql import insert
        statement = insert(Notification).values(
            recipient_user_id=user_id,category=category,title=title,content=content,
            related_type=related_type,related_id=related_id,business_event_key=event_key,
        ).on_conflict_do_nothing(index_elements=["recipient_user_id","business_event_key"]).returning(Notification.id)
        if db.scalar(statement) is not None:created.append(user_id)

    if created:
        db.flush()          # 让新建的通知有 id，但不提交（交给外层事务）
        logger.info("通知已创建 event=%s recipients=%s", event_key, created)

    return created


def list_my_notifications(db: Session, user_id: int, *, limit: int = 50):
    """我的消息列表（最近的在前）。"""
    return db.scalars(
        select(Notification)
        .where(Notification.recipient_user_id == user_id)
        .order_by(Notification.create_time.desc())
        .limit(limit)
    ).all()


def mark_read(db: Session, user_id: int, notification_id: int) -> bool:
    """标记已读。**只能标自己的**（他人的返回 False，调用方应 404）。"""
    from datetime import datetime, timezone

    n = db.get(Notification, notification_id)
    if n is None or n.recipient_user_id != user_id:
        return False
    if n.read_at is None:
        n.read_at = datetime.now(timezone.utc)
        db.flush()              # 不 commit，交给外层
    return True
