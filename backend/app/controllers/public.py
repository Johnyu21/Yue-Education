"""
公开门户 —— 项目 / 活动 / 报名 / 访客留资 / 访客助手

⚠️ 实现要求：
  1. 统一响应：return ok(data)；报错抛 app.core.errors（及 M2 专用 m2_errors）里的异常类
  2. 需登录：Depends(require_password_changed)
  3. 查数据：用 build_scope(db, user, purpose) 限制范围（M1-05）
  4. 多表写：用 with_business_transaction（M1-S1）
  5. AI 调用**放事务外**（M1-S1）
  6. 每个接口下有 API 编号注释

路由层保持"薄"：只做入参解析、取身份、调 service、包统一响应。
"""
from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.orm import Session

from app.core.deps import get_actor, require_password_changed
from app.core.errors import NotImplementedYetError
from app.core.responses import ok
from app.db.session import get_db
from app.models.user import SysUser
from app.schemas.assistant import AssistantRequest
from app.schemas.common import clamp_page, paged
from app.schemas.event import (
    EventCreateIn,
    EventUpdateIn,
    RegistrationCancelIn,
    RegistrationIn,
)
from app.schemas.lead import LeadCaptureIn
from app.schemas.project import ProjectCreateIn, ProjectUpdateIn
from app.services import (
    lead_service,
    public_service,
    rate_limit,
    registration_service,
    visitor_assistant_service,
)

router = APIRouter(tags=["公开门户"])


def _todo(api: str, who: str = "M2"):
    raise NotImplementedYetError(f"{api} 尚未实现（负责人：{who}）")


def optional_actor(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> SysUser | None:
    """公开接口的"可选登录"依赖：报名/取消对访客与已登录学生共用一个入口。

    ⚠️ 没有 Authorization 头 → 按访客处理；
       带了无效/过期令牌 → **照常 401**（绝不静默降级为访客，避免绕过身份绑定）。
    """
    if not authorization:
        return None
    return get_actor(authorization=authorization, db=db)


# ---------------- 项目 ----------------

@router.get("/api/v1/public/projects")
def list_public_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    country: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """API015 公开项目列表（仅已发布，无需登录）"""
    page, page_size = clamp_page(page, page_size)
    items, total = public_service.list_public_projects(
        db, page=page, page_size=page_size, country=country, keyword=keyword)
    return ok(paged(items, page, page_size, total))


@router.get("/api/v1/public/projects/{project_id}")
def get_public_project(project_id: int, db: Session = Depends(get_db)):
    """API016 公开项目详情（未发布 → 404，不暴露草稿存在性）"""
    return ok(public_service.get_public_project(db, project_id))


@router.post("/api/v1/management/projects", status_code=201)
def create_project(data: ProjectCreateIn,
                   user: SysUser = Depends(require_password_changed),
                   db: Session = Depends(get_db)):
    """API017 新增项目草稿（管理员/主管；初始 DRAFT 未发布）"""
    return ok(public_service.create_project(db, user, data))


@router.patch("/api/v1/management/projects/{project_id}")
def update_project(project_id: int,
                   data: ProjectUpdateIn,
                   user: SysUser = Depends(require_password_changed),
                   db: Session = Depends(get_db)):
    """API018 修改项目/发布/审核准入规则（ⓥ 乐观锁 version）"""
    return ok(public_service.update_project(db, user, project_id, data))


# ---------------- 活动 ----------------

@router.get("/api/v1/public/events")
def list_public_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = Query(default="OPEN"),
    db: Session = Depends(get_db),
):
    """API019 公开活动列表（默认只列 OPEN）"""
    page, page_size = clamp_page(page, page_size)
    items, total = public_service.list_public_events(
        db, page=page, page_size=page_size, status=status)
    return ok(paged(items, page, page_size, total))


@router.get("/api/v1/public/events/{event_id}")
def get_public_event(event_id: int, db: Session = Depends(get_db)):
    """API020 公开活动详情（含实时 remainingCapacity，非名额预占承诺）"""
    return ok(public_service.get_public_event(db, event_id))


@router.post("/api/v1/management/events", status_code=201)
def create_event(data: EventCreateIn,
                 user: SysUser = Depends(require_password_changed),
                 db: Session = Depends(get_db)):
    """API021 新增活动草稿（主办部门主管/管理员）"""
    return ok(public_service.create_event(db, user, data))


@router.patch("/api/v1/management/events/{event_id}")
def update_event(event_id: int,
                 data: EventUpdateIn,
                 user: SysUser = Depends(require_password_changed),
                 db: Session = Depends(get_db)):
    """API022 修改/开放/取消活动（ⓥ 乐观锁；取消通知已登录报名人）"""
    return ok(public_service.update_event(db, user, event_id, data))


# ---------------- 留资 ----------------

@router.post("/api/v1/public/leads", status_code=201)
def capture_lead(data: LeadCaptureIn,
                 request: Request,
                 db: Session = Depends(get_db)):
    """API023 访客留资（三渠道统一入口，公开限流）

    - 字段最小集：姓名 + 手机号；表单渠道必须再给性别/城市/学历
    - request_key 必填（幂等）；confirmed=true 表示用户已确认提交
    - 回执**不体现**客户是否存在，防匿名探测
    """
    rate_limit.enforce(request, "lead")
    return ok(lead_service.capture_lead(db, data))


# ---------------- 活动报名 ----------------

@router.post("/api/v1/events/{event_id}/registrations", status_code=201)
def register_event(event_id: int,
                   data: RegistrationIn,
                   request: Request,
                   user: SysUser | None = Depends(optional_actor),
                   db: Session = Depends(get_db)):
    """API024 活动报名（锁活动行 + 锁内复查名额 + 写记录，同一事务）

    - 学生登录：姓名/手机号取自本人账号，不接受客户端指定他人
    - 访客：必须填写姓名 + 手机号，并绑定（复用或新建）线索
    - 访客首次成功会返回一次性 cancelToken；同 request_key 重试可重建同一凭据
    """
    return ok(registration_service.register_event(
        db, event_id, data, user=user,
        client_key=rate_limit.client_key(request, "registration")))


@router.post("/api/v1/registrations/{registration_id}/cancel")
def cancel_registration(registration_id: int,
                        data: RegistrationCancelIn,
                        user: SysUser | None = Depends(optional_actor),
                        db: Session = Depends(get_db)):
    """API025 取消报名（学生本人 或 持有效访客凭据；凭据走 body 不放 URL）"""
    return ok(registration_service.cancel_registration(
        db, registration_id, data, user=user))


@router.get("/api/v1/me/registrations")
def my_registrations(page: int = Query(1, ge=1),
                     page_size: int = Query(20, ge=1, le=100),
                     user: SysUser = Depends(require_password_changed),
                     db: Session = Depends(get_db)):
    """API026 我的报名（学生；不含 cancel_token_hash）"""
    page, page_size = clamp_page(page, page_size)
    items, total = registration_service.list_my_registrations(
        db, user, page=page, page_size=page_size)
    return ok(paged(items, page, page_size, total))


# ---------------- 助手：客服 Agent ----------------

@router.post("/api/v1/assistants/visitor/messages")
def visitor_assistant(data: AssistantRequest,
                      request: Request,
                      db: Session = Depends(get_db)):
    """API027 访客客服助手（公开限流）

    注意：AI 只生成"提议/草稿"，**不直接写库**；
          访客在页面确认后调用普通业务接口
          （POST /public/leads 或 POST /events/{id}/registrations）。
    """
    result = visitor_assistant_service.handle_visitor_message(
        db, data, client_key=rate_limit.client_key(request, "visitor"))
    return ok(result.model_dump(mode="json"))
