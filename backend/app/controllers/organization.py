"""
M1 · 组织与账号管理、通知、文件 —— 接口骨架（待实现）

负责人：M1
内容：部门 / 班级 / 账号管理、员工重置密码、通知中心、文件上传

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
本文件负责的接口（共 13 个）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  【组织：查询】
   API007 GET /api/v1/organization/users           用户列表（通讯录）
   API009 GET /api/v1/organization/departments     部门树
   API012 GET /api/v1/organization/classes         班级列表

  【组织：管理（仅管理员）】
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

⚠️ 实现要点：
  1. 建部门：不能把自己当上级（`parent_id <> id`，数据库会拒）
  2. 指定主管 → 写 `sys_department.head_user_id`（唯一事实源，不用 role）
  3. 建班级班主任：**不能是学生**（要 check user_type='EMPLOYEE'）
  4. 停用班主任/顾问前：**检查有没有待处理记录和在读学生**，要求先交接
  5. 重置学生密码：随机临时密码，**只在响应出现一次**
  6. 文件：限制类型和大小，**防路径穿越**，私有存储 + 短期下载链接
  7. 通知：`business_event_key` 唯一（同一事件只发一条），他人不可读

📖 参考：docs/ 下 M1-04（认证）/ M1-05（权限）/ M1-事务管理
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_password_changed
from app.core.errors import NotImplementedYetError
from app.core.responses import ok
from app.db.session import get_db
from app.models.user import SysUser

router = APIRouter(tags=["M1 · 组织管理"])


def _todo(api: str, who: str = "M1"):
    raise NotImplementedYetError(f"{api} 尚未实现（负责人：{who}）")


# ---------------- 组织：查询 ----------------

@router.get("/api/v1/organization/users")
def list_organization_users(user: SysUser = Depends(require_password_changed),
                            db: Session = Depends(get_db)):
    """API007 通讯录（员工可见，默认不含敏感字段）"""
    _todo("API007")


@router.get("/api/v1/organization/departments")
def list_departments(user: SysUser = Depends(require_password_changed),
                     db: Session = Depends(get_db)):
    """API009 部门树"""
    _todo("API009")


@router.get("/api/v1/organization/classes")
def list_classes(user: SysUser = Depends(require_password_changed),
                 db: Session = Depends(get_db)):
    """API012 班级列表"""
    _todo("API012")


# ---------------- 组织：管理 ----------------

@router.post("/api/v1/management/departments")
def create_department(user: SysUser = Depends(require_password_changed),
                      db: Session = Depends(get_db)):
    """API010 建部门（⚠️ parent_id 不能等于自己）"""
    _todo("API010")


@router.patch("/api/v1/management/departments/{dept_id}")
def update_department(dept_id: int,
                      user: SysUser = Depends(require_password_changed),
                      db: Session = Depends(get_db)):
    """API011 改部门 / 指定主管（写 head_user_id）"""
    _todo("API011")


@router.post("/api/v1/management/classes")
def create_class(user: SysUser = Depends(require_password_changed),
                 db: Session = Depends(get_db)):
    """API013 建班级"""
    _todo("API013")


@router.patch("/api/v1/management/classes/{class_id}")
def update_class(class_id: int,
                 user: SysUser = Depends(require_password_changed),
                 db: Session = Depends(get_db)):
    """API014 改班级 / 换班主任（⚠️ 班主任不能是学生）"""
    _todo("API014")


@router.post("/api/v1/management/users")
def create_user(user: SysUser = Depends(require_password_changed),
                db: Session = Depends(get_db)):
    """API092 创建员工账号（仅管理员）"""
    _todo("API092")


@router.patch("/api/v1/management/users/{user_id}")
def update_user(user_id: int,
                user: SysUser = Depends(require_password_changed),
                db: Session = Depends(get_db)):
    """API008 改账号 / 岗位 / 敏感能力

    ⚠️ 改权限后要 token_version+1（让旧令牌失效）
    ⚠️ 主管只能给本部门普通员工授权，不能给自己或管理员变权
    """
    _todo("API008")


@router.post("/api/v1/management/users/{user_id}/password-reset")
def reset_user_password(user_id: int,
                        user: SysUser = Depends(require_password_changed),
                        db: Session = Depends(get_db)):
    """API006 重置学生临时密码（⚠️ 明文只在响应出现一次，重复请求不重展示）"""
    _todo("API006")


# ---------------- 通知 ----------------

@router.get("/api/v1/me/notifications")
def my_notifications(user: SysUser = Depends(require_password_changed),
                     db: Session = Depends(get_db)):
    """API089 我的消息（铃铛）"""
    _todo("API089")


@router.post("/api/v1/me/notifications/{notification_id}/read")
def mark_notification_read(notification_id: int,
                           user: SysUser = Depends(require_password_changed),
                           db: Session = Depends(get_db)):
    """API090 标记已读（⚠️ 只能标自己的，他人的返回 404）"""
    _todo("API090")


# ---------------- 文件 ----------------

@router.post("/api/v1/files")
def upload_file(user: SysUser = Depends(require_password_changed),
                db: Session = Depends(get_db)):
    """API028 上传私有附件

    ⚠️ 安全要求：
      - 限制类型（pdf/jpg/png/docx/xlsx）和大小（如 10MB）
      - 文件名不直接用用户输入（防路径穿越 ../../etc/passwd）
      - 私有存储，下载走鉴权接口 + 短期链接
    """
    _todo("API028")
