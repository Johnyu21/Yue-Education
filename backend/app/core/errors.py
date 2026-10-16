"""
统一异常定义（M1-03）

作用：全项目的错误，都从 AppError 派生。
为什么：如果各人各写“抛异常”，前端要处理 N 种格式；
       统一成一个类，异常处理器一处搞定。

用法：
    from app.core.errors import AppError, StateConflictError
    raise StateConflictError("该申请已审批过")
"""
from fastapi import status


class AppError(Exception):
    """所有业务异常的基类。"""

    def __init__(
        self,
        code: str,
        message: str,
        http_status: int = status.HTTP_400_BAD_REQUEST,
        errors: list[dict] | None = None,
    ):
        self.code = code              # 业务错误码，如 STATE_CONFLICT
        self.message = message        # 给用户看的提示
        self.http_status = http_status
        self.errors = errors or []    # 字段级错误，如 [{field, reason}]
        super().__init__(message)


# ---- 常用异常：直接 new，不用每次写 code/status ----

class InvalidRequestError(AppError):
    """请求语义无法处理"""
    def __init__(self, message="请求无法处理"):
        super().__init__("INVALID_REQUEST", message, status.HTTP_400_BAD_REQUEST)


class AuthRequiredError(AppError):
    """未登录 / 令牌无效"""
    def __init__(self, message="请先登录"):
        super().__init__("AUTH_REQUIRED", message, status.HTTP_401_UNAUTHORIZED)


class TokenExpiredError(AppError):
    """令牌过期"""
    def __init__(self, message="登录已过期，请重新登录"):
        super().__init__("TOKEN_EXPIRED", message, status.HTTP_401_UNAUTHORIZED)


class ForbiddenError(AppError):
    """没有该功能权限（角色不对）"""
    def __init__(self, message="没有权限"):
        super().__init__("FORBIDDEN", message, status.HTTP_403_FORBIDDEN)


class NotFoundError(AppError):
    """不存在，或不在你的数据范围内
    注意：范围外也返回它，避免暴露“这条数据存在”
    """
    def __init__(self, message="资源不存在"):
        super().__init__("NOT_FOUND", message, status.HTTP_404_NOT_FOUND)


class VersionConflictError(AppError):
    """乐观锁冲突（并发覆盖）"""
    def __init__(self, message="数据已被他人修改，请刷新后重试"):
        super().__init__("VERSION_CONFLICT", message, status.HTTP_409_CONFLICT)


class StateConflictError(AppError):
    """状态不允许（如已审批过）"""
    def __init__(self, message="当前状态不允许此操作"):
        super().__init__("STATE_CONFLICT", message, status.HTTP_409_CONFLICT)


class DuplicateResourceError(AppError):
    """重复资源（如手机号已存在）"""
    def __init__(self, message="资源已存在"):
        super().__init__("DUPLICATE_RESOURCE", message, status.HTTP_409_CONFLICT)


class EventFullError(AppError):
    """活动名额满"""
    def __init__(self, message="名额已满"):
        super().__init__("EVENT_FULL", message, status.HTTP_409_CONFLICT)


class ValidationError(AppError):
    """字段校验失败"""
    def __init__(self, message="参数校验失败", errors=None):
        super().__init__("VALIDATION_ERROR", message, status.HTTP_422_UNPROCESSABLE_ENTITY, errors)


class NotImplementedYetError(AppError):
    """接口骨架已建、逻辑未实现（开发期用，上线前应全部消失）"""
    def __init__(self, message="该接口尚未实现"):
        super().__init__("NOT_IMPLEMENTED", message, status.HTTP_501_NOT_IMPLEMENTED)


# ---- AI 相关（Dify 出错时用）----

class AIBadResponseError(AppError):
    """Dify 返回了，但不符合约定"""
    def __init__(self, message="AI 返回格式异常"):
        super().__init__("AI_BAD_RESPONSE", message, status.HTTP_502_BAD_GATEWAY)


class AIUnavailableError(AppError):
    """Dify / 模型不可用"""
    def __init__(self, message="AI 服务暂不可用"):
        super().__init__("AI_UNAVAILABLE", message, status.HTTP_503_SERVICE_UNAVAILABLE)


class AITimeoutError(AppError):
    """AI 超时"""
    def __init__(self, message="AI 响应超时"):
        super().__init__("AI_TIMEOUT", message, status.HTTP_504_GATEWAY_TIMEOUT)
