"""
公开门户 —— 项目 / 活动 / 报名 / 访客留资 / 访客助手

⚠️ 实现要求：
  1. 统一响应：return ok(data)；报错抛 app.core.errors 里的异常类
  2. 需登录：Depends(require_password_changed)
  3. 查数据：用 build_scope(db, user, purpose) 限制范围（M1-05）
  4. 多表写：用 with_business_transaction（M1-S1）
  5. AI 调用**放事务外**（M1-S1）
  6. 每个接口下有 API 编号注释
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_password_changed
from app.core.errors import NotImplementedYetError
from app.core.responses import ok
from app.db.session import get_db
from app.models.user import SysUser

router = APIRouter(tags=["公开门户"])


def _todo(api: str, who: str = "M2"):
    raise NotImplementedYetError(f"{api} 尚未实现（负责人：{who}）")


@router.get("/api/v1/public/projects")
def list_public_projects(db: Session = Depends(get_db)):
    """API015 项目列表（仅已发布，无需登录）"""
    _todo("API015")


@router.get("/api/v1/public/projects/{project_id}")
def get_public_project(project_id: int, db: Session = Depends(get_db)):
    """API016 项目详情"""
    _todo("API016")


@router.post("/api/v1/management/projects")
def create_project(user: SysUser = Depends(require_password_changed),
                   db: Session = Depends(get_db)):
    """API017 新增项目"""
    _todo("API017")


@router.patch("/api/v1/management/projects/{project_id}")
def update_project(project_id: int,
                   user: SysUser = Depends(require_password_changed),
                   db: Session = Depends(get_db)):
    """API018 修改项目"""
    _todo("API018")


@router.get("/api/v1/public/events")
def list_public_events(db: Session = Depends(get_db)):
    """API019 活动列表"""
    _todo("API019")


@router.get("/api/v1/public/events/{event_id}")
def get_public_event(event_id: int, db: Session = Depends(get_db)):
    """API020 活动详情"""
    _todo("API020")


@router.post("/api/v1/management/events")
def create_event(user: SysUser = Depends(require_password_changed),
                 db: Session = Depends(get_db)):
    """API021 新增活动"""
    _todo("API021")


@router.patch("/api/v1/management/events/{event_id}")
def update_event(event_id: int,
                 user: SysUser = Depends(require_password_changed),
                 db: Session = Depends(get_db)):
    """API022 修改活动"""
    _todo("API022")


# ---------------- 研判 ----------------


@router.post("/api/v1/public/leads")
def capture_lead(db: Session = Depends(get_db)):
    """API023 访客留资

    注意：访客无身份；字段最小集为 姓名 + 手机号；
          request_key 必须填（幂等）；confirmed=true 表示用户已确认提交。
    """
    _todo("API023")


# ---------------- 活动报名 ----------------


@router.post("/api/v1/events/{event_id}/registrations")
def register_event(event_id: int, db: Session = Depends(get_db)):
    """API024 活动报名（锁行 + 查容量 + 写记录，同一事务）"""
    _todo("API024")


@router.post("/api/v1/registrations/{registration_id}/cancel")
def cancel_registration(registration_id: int, db: Session = Depends(get_db)):
    """API025 取消报名"""
    _todo("API025")


@router.get("/api/v1/me/registrations")
def my_registrations(user: SysUser = Depends(require_password_changed),
                     db: Session = Depends(get_db)):
    """API026 我的报名（学生）"""
    _todo("API026")


# ---------------- 助手：客服 Agent ----------------


@router.post("/api/v1/assistants/visitor/messages")
def visitor_assistant(db: Session = Depends(get_db)):
    """API027 访客客服助手

    注意：AI 只生成"提议"，写操作要返回 confirmation_token，
          用户确认后调普通业务接口（见 M1-确认令牌）。
    """
    _todo("API027")


# ---------------- 管理：项目与活动维护 ----------------

