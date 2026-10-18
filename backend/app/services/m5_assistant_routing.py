"""Small deterministic router for existing report capabilities, not a CRUD agent."""
import re
from datetime import date, timedelta


def classify(message):
    if "生成" in message and any(word in message for word in ("报告", "周报", "日汇总", "周汇总")):
        return "REPORT"
    if any(word in message for word in ("新增客户", "意向学生", "意向客户")) and any(
            word in message for word in ("查", "多少", "几位", "几个", "几人", "统计", "名单", "有哪些")):
        return "QUERY"
    return "DAILY_COLLECT"


def period(message, today, weekly=False):
    """Resolve only explicit supported ranges; never silently substitute today."""
    dates = re.findall(r"\d{4}-\d{2}-\d{2}", message)
    if dates:
        if len(dates) > 2:
            raise ValueError("请提供一个起止日期范围")
        start, end = date.fromisoformat(dates[0]), date.fromisoformat(dates[-1])
    elif "上周" in message:
        end = today - timedelta(days=today.weekday() + 1)
        start = end - timedelta(days=6)
    elif "本周" in message or "这周" in message:
        start, end = today - timedelta(days=today.weekday()), today
    elif "上月" in message or "上个月" in message:
        end = today.replace(day=1) - timedelta(days=1)
        start = end.replace(day=1)
    elif "本月" in message or "这个月" in message:
        start, end = today.replace(day=1), today
    elif "昨天" in message:
        start = end = today - timedelta(days=1)
    elif "前天" in message:
        start = end = today - timedelta(days=2)
    elif any(word in message for word in ("去年", "今年", "明天", "下周", "下月", "最近", "过去", "年", "月", "号", "日")) and not any(word in message for word in ("今日", "今天", "日报", "日汇总")):
        raise ValueError("请用YYYY-MM-DD提供日期或起止范围，或到报告中心选择")
    else:
        start, end = (today - timedelta(days=today.weekday()) if weekly else today), today
    if end > today or end < start or (end - start).days > 366:
        raise ValueError("日期范围须为过去至今天的366天以内，且结束不早于开始")
    return start, end
