"""
ORM 模型导出（便于统一导入；不影响各模块按需 import）。

⚠️ 只导出 M2 新增/扩展的模型；M1/M4 的模型各自文件按需导入即可。
"""
from app.models.event import EventLecture, EventRegistration

__all__ = ["EventLecture", "EventRegistration"]
