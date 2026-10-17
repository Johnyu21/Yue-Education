"""
组织与账号管理业务逻辑（M1-06）

作用：部门、班级、账号的增删改 —— 带**业务规则校验**。

⚠️ 关键规则（M1-06 验收标准）：
  1. 部门不能把自己当上级（防树循环）
  2. **禁止学生当班主任**
  3. 指定主管：写 head_user_id（唯一事实源，不用 role）
  4. 停用班主任/顾问前，检查有无待处理记录和在读学生 → 要求先交接
  5. 改权限后 token_version+1（旧令牌失效）
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.errors import InvalidRequestError, NotFoundError, StateConflictError
from app.core.security import generate_temp_password, hash_password
from app.models.organization import SysClass, SysDepartment
from app.models.student import StudentProfile
from app.models.user import SysUser

logger = logging.getLogger(__name__)


# =============================================================
# 部门
# =============================================================
def create_department(db: Session, *, code: str, name: str, parent_id: int | None) -> SysDepartment:
    """建部门。

    ⚠️ parent_id 不能形成环（不能把自己/自己的后代当上级）。
       新建时 id 还没有，所以只需检查 parent 存在。
    """
    if parent_id is not None:
        if db.get(SysDepartment, parent_id) is None:
            raise NotFoundError("上级部门不存在")

    if db.scalar(select(SysDepartment.id).where(SysDepartment.code == code)):
        raise StateConflictError(f"部门编码 {code} 已存在")

    dept = SysDepartment(code=code, name=name, parent_id=parent_id)
    db.add(dept)
    db.flush()
    return dept


def update_department(db: Session, dept_id: int, **changes) -> SysDepartment:
    """改部门 / 指定主管。

    ⚠️ 树循环检查：不能把"自己的某个后代"设为上级，否则遍历部门树会死循环。
    """
    db.execute(text("SELECT pg_advisory_xact_lock(910104)"))
    dept = db.get(SysDepartment, dept_id,with_for_update=True,populate_existing=True)
    if dept is None:
        raise NotFoundError("部门不存在")

    if "parent_id" in changes and changes["parent_id"] is not None:
        new_parent = changes["parent_id"]
        if new_parent == dept_id:
            raise InvalidRequestError("部门不能把自己当上级")
        # 往上追溯，看看 new_parent 是不是自己的后代
        cur, hops = new_parent, 0
        while cur is not None and hops < 50:          # hops 兜底防死循环
            if cur == dept_id:
                raise InvalidRequestError("不能把下级部门设为上级（会形成环）")
            p = db.get(SysDepartment, cur)
            if p is None:raise NotFoundError("上级部门不存在")
            cur = p.parent_id
            hops += 1
        if cur is not None:raise InvalidRequestError("部门层级过深或已存在循环")

    if "head_user_id" in changes and changes["head_user_id"] is not None:
        head = db.get(SysUser, changes["head_user_id"])
        if head is None:
            raise NotFoundError("指定的主管不存在")
        if not head.is_employee or head.status!="NORMAL":
            raise InvalidRequestError("部门主管必须是员工")
        # 主管必须属于该部门（或管理员）
        if head.dept_id != dept_id and head.employee_role != "ADMIN":
            raise InvalidRequestError("主管必须属于该部门")

    for k, v in changes.items():
        if hasattr(dept, k):
            setattr(dept, k, v)
    db.flush()
    return dept


# =============================================================
# 班级
# =============================================================
def create_class(db: Session, *, code: str, name: str, dept_id: int,
                 course_type: str | None = None,
                 head_teacher_id: int | None = None) -> SysClass:
    """建班级。

    ⚠️ 班主任必须是**员工**，不能是学生（M1-06 验收点）。
    """
    if db.get(SysDepartment, dept_id) is None:
        raise NotFoundError("所属部门不存在")

    if head_teacher_id is not None:
        _assert_valid_teacher(db, head_teacher_id)

    if db.scalar(select(SysClass.id).where(SysClass.code == code)):
        raise StateConflictError(f"班级编码 {code} 已存在")

    cls = SysClass(code=code, name=name, dept_id=dept_id, course_type=course_type,
                   head_teacher_id=head_teacher_id)
    db.add(cls)
    db.flush()
    return cls


def update_class(db: Session, class_id: int, **changes) -> SysClass:
    """改班级 / 换班主任。"""
    cls = db.get(SysClass, class_id)
    if cls is None:
        raise NotFoundError("班级不存在")

    if changes.get("head_teacher_id") is not None:
        _assert_valid_teacher(db, changes["head_teacher_id"])

    for k, v in changes.items():
        if hasattr(cls, k):
            setattr(cls, k, v)
    db.flush()
    return cls


def _assert_valid_teacher(db: Session, user_id: int) -> None:
    """⚠️ 班主任校验：必须是员工，且未被禁用。"""
    u = db.get(SysUser, user_id)
    if u is None:
        raise NotFoundError("指定的班主任不存在")
    if not u.is_employee:
        raise InvalidRequestError("班主任必须是员工，不能是学生")
    if u.status != "NORMAL":
        raise InvalidRequestError("该员工已被禁用，不能担任班主任")


# =============================================================
# 账号
# =============================================================
def create_employee(db: Session, *, username: str, real_name: str,
                    employee_role: str, dept_id: int | None,
                    password: str | None = None) -> tuple[SysUser, str]:
    """创建员工账号。返回 (用户, 初始明文密码)。

    ⚠️ 明文密码**只在这一次返回**，数据库只存哈希。
    """
    if db.scalar(select(SysUser.id).where(SysUser.username == username)):
        raise StateConflictError(f"用户名 {username} 已存在")

    if employee_role != "ADMIN" and dept_id is None:
        raise InvalidRequestError("除管理员外，员工必须有部门")

    plain = password or generate_temp_password()
    user = SysUser(
        username=username,
        password_hash=hash_password(plain),
        real_name=real_name,
        user_type="EMPLOYEE",
        employee_role=employee_role,
        dept_id=dept_id,
        status="NORMAL",
        must_change_password=True,
        token_version=0,
    )
    db.add(user)
    db.flush()
    return user, plain


def update_user(db: Session, user_id: int, actor: SysUser, **changes) -> SysUser:
    """改账号 / 岗位 / 敏感能力。

    ⚠️ 改权限后 **token_version+1** → 旧令牌立即失效
    ⚠️ 主管只能改本部门普通员工，不能给自己或管理员变权
    """
    user = db.get(SysUser, user_id,with_for_update=True,populate_existing=True)
    if user is None:
        raise NotFoundError("用户不存在")

    sensitive = {"employee_role", "dept_id", "can_handle_feedback",
                 "psych_access_enabled", "status"}

    # 主管权限边界
    if actor.employee_role == "ADMIN":
        pass                                    # 管理员：全域
    elif actor.id == db.scalar(
        select(SysDepartment.head_user_id).where(SysDepartment.id == user.dept_id)
    ):
        # 是目标用户所在部门的主管
        if user.employee_role == "ADMIN":
            raise InvalidRequestError("主管不能修改管理员")
        if actor.id == user_id:
            raise InvalidRequestError("主管不能给自己变权")
        if changes.get("employee_role")=="ADMIN" or ("dept_id" in changes and changes["dept_id"]!=user.dept_id):raise InvalidRequestError("仅管理员可创建管理员或调整跨部门归属")
    else:
        raise InvalidRequestError("没有权限修改该账号")

    if user.employee_role=="ADMIN" and (changes.get("status")=="DISABLED" or ("employee_role" in changes and changes["employee_role"]!="ADMIN")):
        db.execute(text("SELECT pg_advisory_xact_lock(910105)"))
        if db.scalar(select(func.count()).select_from(SysUser).where(SysUser.employee_role=="ADMIN",SysUser.status=="NORMAL",SysUser.id!=user_id))==0:raise StateConflictError("必须保留至少一个有效管理员")
    if changes.get("employee_role")=="NEWCOMER" or changes.get("status") == "DISABLED" or ("dept_id" in changes and changes["dept_id"] != user.dept_id):
        check_can_deactivate(db, user_id)
    changed_sensitive = False
    for k, v in changes.items():
        if not hasattr(user, k):
            continue
        if getattr(user, k) != v:
            setattr(user, k, v)
            if k in sensitive:
                changed_sensitive = True

    # ⚠️ 权限变更 → 旧令牌作废
    if changed_sensitive:
        user.token_version = user.token_version + 1

    db.flush()
    return user


def reset_student_password(db: Session, user_id: int) -> str:
    """重置学生临时密码，返回明文（**只展示一次**）。"""
    user = db.get(SysUser, user_id)
    if user is None:
        raise NotFoundError("用户不存在")
    if not user.is_student:
        raise InvalidRequestError("只能重置学生账号的密码")

    from datetime import timedelta
    plain = generate_temp_password()
    user.password_hash = hash_password(plain)
    user.must_change_password = True
    user.temporary_password_expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    user.token_version = user.token_version + 1
    db.flush()
    return plain


def check_can_deactivate(db: Session, user_id: int) -> None:
    """停用员工前检查：有没有待交接的活。

    ⚠️ M1-06 要求："停用班主任/顾问前检查待处理记录和在读学生，要求交接"
    """
    from app.models.admin_service import StudentAdminService
    from app.models.feedback_ticket import StudentFeedbackTicket
    from app.models.lead import CrmLead
    from app.models.psych import StudentPsychAlert
    pending = [(SysDepartment, SysDepartment.head_user_id == user_id),
        (StudentAdminService, (StudentAdminService.assignee_user_id == user_id) & (StudentAdminService.status == "PENDING")),
        (StudentFeedbackTicket, (StudentFeedbackTicket.assignee_user_id == user_id) & StudentFeedbackTicket.status.in_(["PENDING","PROCESSING"])),
        (CrmLead, (CrmLead.owner_user_id == user_id) & CrmLead.status.in_(["NEW","FOLLOWING"])),
        (StudentPsychAlert, (StudentPsychAlert.follow_up_user_id == user_id) & StudentPsychAlert.status.in_(["PENDING_REVIEW","CONFIRMED","HANDLING"]))]
    for model,condition in pending:
        if db.scalar(select(model.id).where(condition).limit(1)) is not None:
            raise StateConflictError("该员工仍有负责关系或待处理事项，请先交接")
    # 是否还是班主任
    cls = db.scalar(select(SysClass.id).where(SysClass.head_teacher_id == user_id))
    if cls is not None:
        raise StateConflictError("该员工仍是班主任，请先交接班级")

    # 是否还带着在读学生
    n = db.scalar(
        select(func.count()).select_from(StudentProfile).where(
            StudentProfile.advisor_user_id == user_id,
            StudentProfile.status == "ENROLLED",
        )
    )
    if n:
        raise StateConflictError(f"该员工还负责 {n} 名在读学生，请先交接")
