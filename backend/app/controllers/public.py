"""
M2 · 访客客服与客户研判 —— 接口骨架（待实现）

负责人：M2
内容：三渠道获客、客服 Agent、项目/活动展示、研判、简历解析

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
本文件负责的接口（共 15 个）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  【公开】访客无需登录
   API015 GET  /api/v1/public/projects            项目列表
   API016 GET  /api/v1/public/projects/{id}       项目详情
   API019 GET  /api/v1/public/events              活动列表
   API020 GET  /api/v1/public/events/{id}         活动详情
   API023 POST /api/v1/public/leads               访客留资（ⓒ 支持确认令牌）

  【活动报名】部分需登录
   API024 POST /api/v1/events/{event_id}/registrations   报名（ⓒ）
   API025 POST /api/v1/registrations/{id}/cancel         取消
   API026 GET  /api/v1/me/registrations                  我的报名（需登录）

  【助手】客服 Agent
   API027 POST /api/v1/assistants/visitor/messages       访客助手

  【管理】项目/活动维护
   API017 POST   /api/v1/management/projects
   API018 PATCH  /api/v1/management/projects/{id}
   API021 POST   /api/v1/management/events
   API022 PATCH  /api/v1/management/events/{id}

  【研判】
   API041 POST /api/v1/employees/leads/{id}/assessments  执行研判（ⓒ）
   API042 GET  /api/v1/employees/leads/{id}/assessment   取最近研判
   API096 POST /api/v1/employees/leads/{id}/resume-extraction  简历解析
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ 实现要求（务必遵守）：
  1. 返回用 `ok(data)`；报错抛 `app.core.errors` 里的异常类
  2. 需登录的接口加 `Depends(require_password_changed)`
  3. 查数据必须用 `build_scope(db, user, purpose)` 限制范围（M1-05）
  4. Dify 调用走 `app.integrations.dify`，不要在这里直接发 HTTP
  5. 报名要"锁行 + 查容量 + 写记录"在同一事务（M1 事务管理）
  6. AI 调用**不要放在事务里**（会长时间占锁）

📖 参考文档：docs/ 下 M1-03 / M1-04 / M1-05 / M1-事务管理 / AI编码提示词模板
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_actor, require_password_changed
from app.core.errors import NotImplementedYetError
from app.core.responses import ok
from app.db.session import get_db
from app.models.user import SysUser

router = APIRouter(tags=["M2 · 访客客服与研判"])


def _todo(api: str, who: str = "M2"):
    """占位：抛 501，提示这个接口还没实现。"""
    raise NotImplementedYetError(f"{api} 尚未实现（负责人：{who}）")


# ---------------- 公开：项目与活动 ----------------

@router.get("/api/v1/public/projects")
def list_public_projects(db: Session = Depends(get_db)):
    """API015 项目列表（仅已发布，无需登录）"""
    _todo("API015")


@router.get("/api/v1/public/projects/{project_id}")
def get_public_project(project_id: int, db: Session = Depends(get_db)):
    """API016 项目详情"""
    _todo("API016")


@router.get("/api/v1/public/events")
def list_public_events(db: Session = Depends(get_db)):
    """API019 活动列表"""
    _todo("API019")


@router.get("/api/v1/public/events/{event_id}")
def get_public_event(event_id: int, db: Session = Depends(get_db)):
    """API020 活动详情"""
    _todo("API020")


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

@router.post("/api/v1/employees/leads/{lead_id}/assessments")
def assess_lead(lead_id: int,
                user: SysUser = Depends(require_password_changed),
                db: Session = Depends(get_db)):
    """API041 执行研判

    ⚠️ 流程：
      1. build_scope 检查能否操作这条线索
      2. ⚠️ 事务外调 Dify 提取画像（别占着数据库锁）
      3. 事务内保存报告 + 更新 crm_lead.assessment_*
    """
    _todo("API041")


@router.get("/api/v1/employees/leads/{lead_id}/assessment")
def get_lead_assessment(lead_id: int,
                        user: SysUser = Depends(require_password_changed),
                        db: Session = Depends(get_db)):
    """API042 取最近一份研判报告"""
    _todo("API042")


@router.post("/api/v1/employees/leads/{lead_id}/resume-extraction")
def extract_resume(lead_id: int,
                   user: SysUser = Depends(require_password_changed),
                   db: Session = Depends(get_db)):
    """API096 简历文本/文件解析"""
    _todo("API096")
