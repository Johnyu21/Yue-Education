"""
项目（course_project）请求与响应 DTO —— M2

约定：
- 请求体 snake_case；响应体 camelCase（与 M1/M4 现状一致）
- ID 一律十进制字符串；金额一律字符串 + 币种
- 写入 DTO 禁止未知字段（extra=forbid），权限字段永不接受客户端传入
"""
from pydantic import AwareDatetime as datetime
from decimal import Decimal
from uuid import UUID

from app.core.dto import BaseModel
from pydantic import Field


# ---------------- 响应 ----------------
class ProjectPublicOut(BaseModel):
    """公开可见字段（不含未审内部规则、不含路由部门）。"""

    id: str
    code: str
    name: str
    country: str | None = None
    educationLevel: str | None = None
    description: str
    admissionRequirements: str | None = None
    facultySummary: str | None = None
    durationMonths: int | None = None
    feeAmount: str | None = None        # 参考费用，字符串；不代表实收
    feeCurrency: str | None = None


class ProjectStaffOut(ProjectPublicOut):
    """员工可见字段：公开字段 + 发布状态与结构化规则。"""

    defaultDeptId: str | None = None
    isPublished: bool = False
    admissionRules: dict | None = None
    ruleVersion: str | None = None
    ruleApprovedAt: datetime | None = None
    version: int


# ---------------- 请求 ----------------
class ProjectCreateIn(BaseModel):
    model_config = {"extra": "forbid"}

    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1)
    default_dept_id: int | None = None
    country: str | None = Field(default=None, max_length=80)
    education_level: str | None = Field(default=None, max_length=80)
    admission_requirements: str | None = None
    faculty_summary: str | None = None
    duration_months: int | None = Field(default=None, gt=0)
    fee_amount: Decimal | None = Field(default=None, ge=0)
    fee_currency: str | None = Field(default=None, min_length=3, max_length=3)


class ProjectUpdateIn(BaseModel):
    """只写白名单字段；用 model_fields_set 区分"未提供"与"显式置空"。"""

    model_config = {"extra": "forbid"}

    expected_version: int = Field(gt=0)
    request_key: UUID

    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, min_length=1)
    country: str | None = Field(default=None, max_length=80)
    education_level: str | None = Field(default=None, max_length=80)
    admission_requirements: str | None = None
    faculty_summary: str | None = None
    duration_months: int | None = Field(default=None, gt=0)
    fee_amount: Decimal | None = Field(default=None, ge=0)
    fee_currency: str | None = Field(default=None, min_length=3, max_length=3)
    default_dept_id: int | None = None

    # 发布与规则审核（只有主管/管理员可审核）
    is_published: bool | None = None
    admission_rules: dict | None = None
    rule_version: str | None = Field(default=None, max_length=40)
    approve_rules: bool | None = None
