"""
统一响应格式 + 异常处理器 + request_id（M1-03）

作用：让**所有接口**返回同一种结构，出错也不泄露敏感信息。

统一格式：
    成功：{"code":"OK",   "message":"成功", "data":{...}, "request_id":"<UUID>"}
    失败：{"code":"XXX",  "message":"...",  "data":null,  "errors":[...], "request_id":"<UUID>"}

request_id 自动注入：
    中间件把 request_id 存进 contextvar，ok()/fail() 自动取。
    → 接口里只写 ok(data) 就行，**不用手动传 request_id**（防遗忘）。
"""
import uuid
import logging
from contextvars import ContextVar

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import AppError

logger = logging.getLogger(__name__)

# 当前请求的 request_id（每个请求独立，线程/协程安全）
_request_id: ContextVar[str] = ContextVar("request_id", default="")


def current_request_id() -> str:
    """取当前请求的 request_id。"""
    return _request_id.get()


# =============================================================
# request_id 中间件
# =============================================================
def setup_request_id(app: FastAPI) -> None:
    """给每个请求分配 request_id：存进 contextvar + 放进响应头。"""

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        # 客户端带了就用它的（限长防注入），否则自己生成
        # ⚠️ 规范要求 request_id 是合法 UUID（便于日志系统索引）
        rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        try:rid=str(uuid.UUID(rid))
        except (ValueError,TypeError):rid=str(uuid.uuid4())
        request.state.request_id = rid
        token = _request_id.set(rid)          # 存进 contextvar，ok()/fail() 自动读
        try:
            response = await call_next(request)
        finally:
            _request_id.reset(token)
        response.headers["X-Request-ID"] = rid
        return response


# =============================================================
# 统一响应封装（无需传 request_id，自动注入）
# =============================================================
def ok(data=None, message: str = "成功") -> dict:
    """成功响应。接口里直接 return ok(data)。"""
    return {"code": "OK", "message": message, "data": data,
            "request_id": current_request_id()}


def fail(code: str, message: str, errors=None, data=None) -> dict:
    """失败响应。data 可为错误附带的上下文（如 current_version）。"""
    return {"code": code, "message": message, "data": data,
            "errors": errors or [], "request_id": current_request_id()}


# =============================================================
# 异常处理器：把各种异常统一成上面的格式
# =============================================================
def setup_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器。一处写好，所有接口生效。"""

    # ---- ① 业务异常（我们自己抛的 AppError）----
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.http_status,
            content=fail(exc.code, exc.message, exc.errors, exc.data),
        )

    # ---- ② 字段校验失败（FastAPI/Pydantic 自动抛的，如手机号格式错）----
    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, exc: RequestValidationError):
        errors = [
            {"field": ".".join(str(x) for x in e["loc"][1:]), "reason": e["msg"]}
            for e in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=fail("VALIDATION_ERROR", "参数校验失败", errors),
        )

    # ---- ③ 找不到路由等 HTTP 异常 ----
    @app.exception_handler(StarletteHTTPException)
    async def handle_http(request: Request, exc: StarletteHTTPException):
        mapping = {401: "AUTH_REQUIRED", 403: "FORBIDDEN", 404: "NOT_FOUND"}
        code = mapping.get(exc.status_code, "INVALID_REQUEST")
        return JSONResponse(
            status_code=exc.status_code,
            content=fail(code, str(exc.detail)),
        )

    # ---- ④ 兜底：未预期异常（返回 500，但绝不泄露堆栈/SQL/密钥）----
    @app.exception_handler(Exception)
    async def handle_unknown(request: Request, exc: Exception):
        # 完整错误写日志（后端自己看），响应只给一句通用提示
        logger.error("未预期异常 request_id=%s type=%s", current_request_id(),exc.__class__.__name__)
        return JSONResponse(
            status_code=500,
            content=fail("INTERNAL_ERROR", "服务器内部错误"),
        )
