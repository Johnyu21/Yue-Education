"""
M2 专用错误码（不改 core/errors.py，直接复用 AppError 基类）

目的：让 M2 的业务错误码与《04_API接口文档》逐字一致
（如 PERIOD_INVALID / EVENT_FULL 之外的 M2 码），
同时保持全局统一响应格式与 HTTP 语义。
"""
from app.core.errors import AppError

# 直接用数字状态码：避免 fastapi/starlette 的 *_UNPROCESSABLE_ENTITY 弃用告警
_HTTP_400 = 400
_HTTP_409 = 409
_HTTP_422 = 422


class _M2Error(AppError):
    code_ = "INVALID_REQUEST"
    http_ = _HTTP_400

    def __init__(self, message: str, data: dict | None = None,
                 errors: list[dict] | None = None):
        super().__init__(self.code_, message, self.http_, errors, data)


# ---- 422：字段/语义校验 ----
class MissingFieldError(_M2Error):
    """留资等必填字段缺失（422 MISSING_FIELD）。"""
    code_ = "MISSING_FIELD"
    http_ = _HTTP_422


class PeriodInvalidError(_M2Error):
    """活动时间区间不合法（422 PERIOD_INVALID）。"""
    code_ = "PERIOD_INVALID"
    http_ = _HTTP_422


class NoReadableTextError(_M2Error):
    """附件无可提取文本（422 NO_READABLE_TEXT），提示需 OCR 或文字版。"""
    code_ = "NO_READABLE_TEXT"
    http_ = _HTTP_422


# ---- 409：唯一性/状态/并发 ----
class DuplicateCodeError(_M2Error):
    """编码重复（409 DUPLICATE_CODE）。"""
    code_ = "DUPLICATE_CODE"
    http_ = _HTTP_409


class RuleNotApprovedError(_M2Error):
    """准入规则未获审核（409 RULE_NOT_APPROVED）。"""
    code_ = "RULE_NOT_APPROVED"
    http_ = _HTTP_409


class CapacityBelowRegisteredError(_M2Error):
    """名额不能降到已报名数之下（409 CAPACITY_BELOW_REGISTERED）。"""
    code_ = "CAPACITY_BELOW_REGISTERED"
    http_ = _HTTP_409


class RegistrationClosedError(_M2Error):
    """报名未开放/已截止/活动非 OPEN（409 REGISTRATION_CLOSED）。"""
    code_ = "REGISTRATION_CLOSED"
    http_ = _HTTP_409


class DuplicateRegistrationError(_M2Error):
    """同一活动同手机号重复报名（409 DUPLICATE_REGISTRATION）。"""
    code_ = "DUPLICATE_REGISTRATION"
    http_ = _HTTP_409


class RegistrationNotCancellableError(_M2Error):
    """当前报名状态不可取消（409 REGISTRATION_NOT_CANCELLABLE）。"""
    code_ = "REGISTRATION_NOT_CANCELLABLE"
    http_ = _HTTP_409


class AssessmentRunningError(_M2Error):
    """该客户已有研判在进行中（409 ASSESSMENT_RUNNING）。"""
    code_ = "ASSESSMENT_RUNNING"
    http_ = _HTTP_409


# ---- 429：限流 ----
class RateLimitedError(_M2Error):
    """公开接口超过频率上限（429 RATE_LIMITED）。"""
    code_ = "RATE_LIMITED"
    http_ = 429
