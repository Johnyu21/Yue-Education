"""
公共请求/响应 DTO：版本 + 幂等键 + 原因（M4）＋分页约定（M2 追加）
"""
from uuid import UUID

from app.core.dto import BaseModel
from pydantic import Field

# ---- 版本 + 幂等键（M4 原有，不改）----


class VersionRequest(BaseModel):
    expected_version: int = Field(gt=0)
    request_key: UUID
    confirmation_token: str | None = None


class VersionReasonRequest(VersionRequest):
    reason: str = Field(min_length=1, max_length=2000)


# ---- M2 追加：分页约定（与 M1/M4 现状一致：page 从 1 起，pageSize 最大 100）----

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def clamp_page(page: int, page_size: int) -> tuple[int, int]:
    """把分页参数收敛到合法区间，避免负数/超大值。"""
    page = max(int(page or 1), 1)
    page_size = min(max(int(page_size or DEFAULT_PAGE_SIZE), 1), MAX_PAGE_SIZE)
    return page, page_size


def paged(items: list, page: int, page_size: int, total: int) -> dict:
    """统一分页响应体：{items, page, pageSize, total}。"""
    return {"items": items, "page": page, "pageSize": page_size, "total": total}
