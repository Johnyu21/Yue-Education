"""
M1 · 组织与账号管理、通知、文件

负责人：M1
内容：部门 / 班级 / 账号管理、员工重置密码、通知中心、文件上传

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
本文件负责的接口（共 13 个）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  【组织：查询】
   API007 GET /api/v1/organization/users           用户列表（通讯录）
   API009 GET /api/v1/organization/departments     部门树
   API012 GET /api/v1/organization/classes         班级列表

  【组织：管理】
   API010 POST  /api/v1/management/departments              建部门
   API011 PATCH /api/v1/management/departments/{id}         改部门/指定主管
   API013 POST  /api/v1/management/classes                  建班级
   API014 PATCH /api/v1/management/classes/{id}             改班级/班主任
   API092 POST  /api/v1/management/users                    创建员工账号
   API008 PATCH /api/v1/management/users/{user_id}          改账号/岗位/能力
   API006 POST  /api/v1/management/users/{user_id}/password-reset  重置学生密码

  【通知】
   API089 GET  /api/v1/me/notifications             我的消息
   API090 POST /api/v1/me/notifications/{id}/read   标记已读

  【文件】
   API028 POST /api/v1/files                        上传（私有附件）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import storage
from app.core.deps import require_password_changed
from app.core.errors import ForbiddenError, NotFoundError
from app.core.notification import list_my_notifications, mark_read
from app.core.responses import ok
from app.core.transaction import with_business_transaction
from app.db.session import get_db
from app.models.organization import SysClass, SysDepartment
from app.models.user import SysUser
from app.schemas.organization import (
    ClassCreate, ClassUpdate, DepartmentCreate, DepartmentUpdate,
    EmployeeCreate, UserUpdate,
)
from app.services import organization_service as org_svc

router = APIRouter(tags=["M1 · 组织管理"])


def _require_admin(user: SysUser) -> None:
    """管理接口：仅管理员。"""
    if user.employee_role != "ADMIN":
        raise ForbiddenError("需要管理员权限")


# ---------------- 组织：查询 ----------------

@router.get("/api/v1/organization/users")
def list_organization_users(user: SysUser = Depends(require_password_changed),
                            db: Session = Depends(get_db)):
    """API007 通讯录（员工可见，不含敏感字段）"""
    rows = db.scalars(select(SysUser).where(SysUser.status == "NORMAL")).all()
    return ok({"items": [
        {
            "id": str(u.id), "username": u.username, "realName": u.real_name,
            "userType": u.user_type, "employeeRole": u.employee_role,
            "deptId": str(u.dept_id) if u.dept_id else None,
            "contactInfo": u.contact_info,
        } for u in rows
    ]})


@router.get("/api/v1/organization/departments")
def list_departments(user: SysUser = Depends(require_password_changed),
                     db: Session = Depends(get_db)):
    """API009 部门树

    ⚠️ 部门树展示 ≠ 主管能看子部门数据（数据范围见 M1-05）
    """
    rows = db.scalars(select(SysDepartment).order_by(SysDepartment.id)).all()
    return ok({"items": [
        {
            "id": str(d.id), "code": d.code, "name": d.name,
            "parentId": str(d.parent_id) if d.parent_id else None,
            "headUserId": str(d.head_user_id) if d.head_user_id else None,
        } for d in rows
    ]})


@router.get("/api/v1/organization/classes")
def list_classes(user: SysUser = Depends(require_password_changed),
                 db: Session = Depends(get_db)):
    """API012 班级列表"""
    rows = db.scalars(select(SysClass).order_by(SysClass.id)).all()
    return ok({"items": [
        {
            "id": str(c.id), "name": c.name, "courseType": c.course_type,
            "deptId": str(c.dept_id),
            "headTeacherId": str(c.head_teacher_id) if c.head_teacher_id else None,
        } for c in rows
    ]})


# ---------------- 组织：管理 ----------------

@router.post("/api/v1/management/departments")
def create_department(data: DepartmentCreate,
                      user: SysUser = Depends(require_password_changed),
                      db: Session = Depends(get_db)):
    """API010 建部门"""
    _require_admin(user)
    with with_business_transaction(db):
        dept = org_svc.create_department(
            db, code=data.code, name=data.name, parent_id=data.parent_id)
    return ok({"id": str(dept.id), "code": dept.code, "name": dept.name})


@router.patch("/api/v1/management/departments/{dept_id}")
def update_department(dept_id: int, data: DepartmentUpdate,
                      user: SysUser = Depends(require_password_changed),
                      db: Session = Depends(get_db)):
    """API011 改部门 / 指定主管（⚠️ 不能形成树环）"""
    _require_admin(user)
    changes = {k: v for k, v in data.model_dump(exclude_unset=True).items()
               if v is not None}
    with with_business_transaction(db):
        dept = org_svc.update_department(db, dept_id, **changes)
    return ok({"id": str(dept.id), "name": dept.name,
               "headUserId": str(dept.head_user_id) if dept.head_user_id else None})


@router.post("/api/v1/management/classes")
def create_class(data: ClassCreate,
                 user: SysUser = Depends(require_password_changed),
                 db: Session = Depends(get_db)):
    """API013 建班级（⚠️ 班主任必须是员工）"""
    _require_admin(user)
    with with_business_transaction(db):
        cls = org_svc.create_class(
            db, code=data.code, name=data.name, dept_id=data.dept_id,
            course_type=data.course_type, head_teacher_id=data.head_teacher_id)
    return ok({"id": str(cls.id), "name": cls.name})


@router.patch("/api/v1/management/classes/{class_id}")
def update_class(class_id: int, data: ClassUpdate,
                 user: SysUser = Depends(require_password_changed),
                 db: Session = Depends(get_db)):
    """API014 改班级 / 换班主任（⚠️ 班主任不能是学生）"""
    _require_admin(user)
    changes = {k: v for k, v in data.model_dump(exclude_unset=True).items()
               if v is not None}
    with with_business_transaction(db):
        cls = org_svc.update_class(db, class_id, **changes)
    return ok({"id": str(cls.id), "name": cls.name,
               "headTeacherId": str(cls.head_teacher_id) if cls.head_teacher_id else None})


@router.post("/api/v1/management/users")
def create_user(data: EmployeeCreate,
                user: SysUser = Depends(require_password_changed),
                db: Session = Depends(get_db)):
    """API092 创建员工账号（仅管理员）

    ⚠️ 返回的临时密码**只在这一次出现**，数据库只存哈希。
    """
    _require_admin(user)
    with with_business_transaction(db):
        new_user, plain_pwd = org_svc.create_employee(
            db, username=data.username, real_name=data.real_name,
            employee_role=data.employee_role, dept_id=data.dept_id)
    return ok({
        "id": str(new_user.id),
        "username": new_user.username,
        "temporaryPassword": plain_pwd,     # ⚠️ 只此一次
        "mustChangePassword": True,
    })


@router.patch("/api/v1/management/users/{user_id}")
def update_user(user_id: int, data: UserUpdate,
                user: SysUser = Depends(require_password_changed),
                db: Session = Depends(get_db)):
    """API008 改账号 / 岗位 / 敏感能力

    ⚠️ 改敏感字段后 token_version+1（旧令牌失效）
    ⚠️ 主管只能改本部门普通员工，不能给自己或管理员变权
    """
    changes = {k: v for k, v in data.model_dump(exclude_unset=True).items()}
    with with_business_transaction(db):
        target = org_svc.update_user(db, user_id, actor=user, **changes)
    return ok({"id": str(target.id), "status": target.status,
               "canHandleFeedback": target.can_handle_feedback,
               "psychAccessEnabled": target.psych_access_enabled})


@router.post("/api/v1/management/users/{user_id}/password-reset")
def reset_user_password(user_id: int,
                        user: SysUser = Depends(require_password_changed),
                        db: Session = Depends(get_db)):
    """API006 重置学生临时密码（⚠️ 明文只在响应出现一次）"""
    _require_admin(user)
    with with_business_transaction(db):
        plain = org_svc.reset_student_password(db, user_id)
    return ok({"temporaryPassword": plain, "mustChangePassword": True})


# ---------------- 通知 ----------------

@router.get("/api/v1/me/notifications")
def my_notifications(user: SysUser = Depends(require_password_changed),
                     db: Session = Depends(get_db)):
    """API089 我的消息（铃铛）"""
    items = list_my_notifications(db, user.id)
    return ok({"items": [
        {
            "id": str(n.id), "category": n.category, "title": n.title,
            "content": n.content,
            "relatedType": n.related_type,
            "relatedId": str(n.related_id) if n.related_id else None,
            "read": n.read_at is not None,
            "createTime": n.create_time.isoformat(),
        } for n in items
    ], "unread": sum(1 for n in items if n.read_at is None)})


@router.post("/api/v1/me/notifications/{notification_id}/read")
def mark_notification_read(notification_id: int,
                           user: SysUser = Depends(require_password_changed),
                           db: Session = Depends(get_db)):
    """API090 标记已读（⚠️ 只能标自己的，他人的返回 404）"""
    with with_business_transaction(db):
        ok_flag = mark_read(db, user.id, notification_id)
    if not ok_flag:
        # ⚠️ 范围外返回 404（不是 403），避免暴露"这条通知存在"
        raise NotFoundError("消息不存在")
    return ok({"read": True})


# ---------------- 文件 ----------------

@router.post("/api/v1/files")
def upload_file(file: UploadFile = File(...),
                user: SysUser = Depends(require_password_changed),
                db: Session = Depends(get_db)):
    """API028 上传私有附件

    ⚠️ 安全（M1-08 验收点）：
      - 扩展名白名单 + MIME 校验 + 大小限制
      - 文件名**重新生成**（防路径穿越）
      - 按 owner 分目录（防伪造归属）
      - 返回 object_key（**不返回真实路径**）
    """
    object_key = storage.save_upload(file, owner_user_id=user.id)
    return ok({"objectKey": object_key, "filename": file.filename})
