"""
M3 专属错误码（参照 M2 的 m2_errors.py 先例）

⚠️ 按团队约定，core/errors.py 属 M1，未经 review 不改；
   M3 需要的业务错误码先集中在这里，待 P1 收编后可删除本文件。
   HTTP 语义：403 无岗位能力；404 不存在/越权；409 状态/并发/唯一冲突；422 字段/前置条件。
"""
from fastapi import status

from app.core.errors import AppError


class CapabilityDeniedError(AppError):
    """没有该岗位能力（如无售后/心理授权）"""

    def __init__(self, message="缺少该业务能力授权"):
        super().__init__("CAPABILITY_DENIED", message, status.HTTP_403_FORBIDDEN)


class StateTransitionDeniedError(AppError):
    """状态机不允许（如 SIGNED 走普通状态接口）"""

    def __init__(self, message="当前状态不允许此操作"):
        super().__init__("STATE_TRANSITION_DENIED", message, status.HTTP_409_CONFLICT)


class LeadAlreadyClaimedError(AppError):
    """线索已被他人认领（并发认领失败）"""

    def __init__(self, message="该客户已被认领"):
        super().__init__("LEAD_ALREADY_CLAIMED", message, status.HTTP_409_CONFLICT)


class LeadExistsOutOfScopeError(AppError):
    """手机号已存在客户，但不在当前员工可见范围（不泄露归属详情）"""

    def __init__(self, message="该手机号已存在客户，且不在您的可见范围内"):
        super().__init__("LEAD_ALREADY_EXISTS_OUT_OF_SCOPE", message, status.HTTP_409_CONFLICT)


class MobileConflictError(AppError):
    """手机号与既有客户重复"""

    def __init__(self, message="该手机号已被其他客户占用"):
        super().__init__("MOBILE_CONFLICT", message, status.HTTP_409_CONFLICT)


class UsernameConflictError(AppError):
    """手机号已存在登录账号"""

    def __init__(self, message="该手机号已存在登录账号"):
        super().__init__("USERNAME_CONFLICT", message, status.HTTP_409_CONFLICT)


class AlreadyConvertedError(AppError):
    """线索已转化过学生，不能重复转化"""

    def __init__(self, message="该客户已转化过学生"):
        super().__init__("ALREADY_CONVERTED", message, status.HTTP_409_CONFLICT)


class ClassTeacherRequiredError(AppError):
    """班级未配置班主任，不能完成转化"""

    def __init__(self, message="该班级未配置班主任，请先配置班主任"):
        super().__init__("CLASS_TEACHER_REQUIRED", message,
                         status.HTTP_422_UNPROCESSABLE_ENTITY)


class PendingRequestsRequireReassignError(AppError):
    """学生存在未审单，须先转派再调班/换顾问"""

    def __init__(self, message="该学生存在待审批申请，请先转派后再调整班级/顾问"):
        super().__init__("PENDING_REQUESTS_REQUIRE_REASSIGN", message,
                         status.HTTP_409_CONFLICT)


class DepartmentMismatchError(AppError):
    """班级/顾问与学生部门不一致"""

    def __init__(self, message="班级或顾问与学生所属部门不一致"):
        super().__init__("DEPARTMENT_MISMATCH", message, status.HTTP_409_CONFLICT)


class SequenceConflictError(AppError):
    """申请进度并发冲突（expected_sequence 不一致）"""

    def __init__(self, message="进度已被他人更新，请刷新后重试"):
        super().__init__("SEQUENCE_CONFLICT", message, status.HTTP_409_CONFLICT)


class EnrollmentStatusConflictError(AppError):
    """课程关联状态不允许（已报名/已完成等）"""

    def __init__(self, message="该课程关联当前状态不允许此操作"):
        super().__init__("ENROLLMENT_STATE_DENIED", message, status.HTTP_409_CONFLICT)


class ResolutionRequiredError(AppError):
    """售后解决必须提供结果说明"""

    def __init__(self, message="解决工单必须填写处理结果"):
        super().__init__("RESOLUTION_REQUIRED", message,
                         status.HTTP_422_UNPROCESSABLE_ENTITY)
