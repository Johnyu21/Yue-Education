"""
工作台 —— 统一待办（API088，实时查询，无 todo 表）
"""
from pydantic import AwareDatetime as datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import require_password_changed
from app.core.responses import ok
from app.db.session import get_db
from app.models.user import SysUser
from app.schemas.common import paged
from app.services import todo_service

router = APIRouter(tags=["工作台"])


@router.get("/api/v1/workbench/todos")
def workbench_todos(user: SysUser = Depends(require_password_changed),
                    db: Session = Depends(get_db),
                    type: str | None = Query(None),
                    due_before: datetime | None = Query(None),
                    page: int = Query(1, ge=1),
                    page_size: int = Query(20, ge=1, le=100)):
    """API088 统一待办（按岗位能力与关系过滤，操作完成后刷新即消失）"""
    items, total = todo_service.list_todos(
        db, user, type=type, due_before=due_before,
        page=page, page_size=page_size)
    return ok(paged([i.model_dump(mode="json") for i in items], page, page_size, total))
