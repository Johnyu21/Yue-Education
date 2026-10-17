"""
智能助手 —— 员工助手 / 学生助手 / 语音转写
"""
from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.core.deps import require_password_changed
from app.core.errors import NotImplementedYetError
from app.core.responses import ok
from app.db.session import get_db
from app.models.user import SysUser
from app.schemas.assistant import AssistantRequest
from app.services import enterprise_assistant_service, student_assistant_service

router = APIRouter(tags=["智能助手"])


def _todo(api: str, who: str = "M3/M4"):
    raise NotImplementedYetError(f"{api} 尚未实现（负责人：{who}）")


@router.post("/api/v1/assistants/employee/messages")
def employee_assistant(data: AssistantRequest,
                       user: SysUser = Depends(require_password_changed),
                       db: Session = Depends(get_db)):
    """API029 企业助手（意图识别 + 授权查询 + 写操作提议，不直接写库）"""
    result = enterprise_assistant_service.handle_enterprise_message(db, user, data)
    return ok(result.model_dump(mode="json"))


@router.post("/api/v1/assistants/student/messages")
def student_assistant(data: AssistantRequest,
                      authorization: str | None = Header(default=None),
                      user: SysUser = Depends(require_password_changed),
                      db: Session = Depends(get_db)):
    """API030 学生助手（Dify 工作流内 HTTP 节点直接调用后端业务接口）"""
    token = authorization[7:].strip() if authorization and authorization.startswith("Bearer ") else ""
    result = student_assistant_service.handle_student_message(db, user, data, auth_token=token)
    return ok(result.model_dump(mode="json"))


@router.post("/api/v1/transcriptions")
def transcribe(user: SysUser = Depends(require_password_changed)):
    """API031 语音转写（ASR，M3）"""
    _todo("API031", "M3")
