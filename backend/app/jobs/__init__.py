"""
定时任务（Jobs）

⚠️ 目前实现在 `app/core/scheduler.py`（含单实例锁 + 两个扫描任务）。
   本目录保留给后续任务拆分（如心理日状态核对）。

现有任务：
  - scan_schedule_reminders   日程提醒（M1-09）
  - scan_followup_reminders   跟进提醒（M1-09）
"""
