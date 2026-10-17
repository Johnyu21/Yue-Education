"""
智能助手 —— 员工助手 / 学生助手 / 语音转写
"""
from fastapi import APIRouter, Depends, Header, File, UploadFile
from sqlalchemy.orm import Session

from app.core.deps import require_password_changed
from app.core.responses import ok
from app.db.session import get_db
from app.models.user import SysUser
from app.schemas.assistant import AssistantRequest
from app.services import enterprise_assistant_service, student_assistant_service

router = APIRouter(tags=["智能助手"])




@router.post("/api/v1/assistants/employee/messages")
def employee_assistant(data: AssistantRequest,
                       user: SysUser = Depends(require_password_changed),
                       db: Session = Depends(get_db)):
    """API029 企业助手（意图识别 + 授权查询 + 写操作提议，不直接写库）"""
    result = enterprise_assistant_service.handle_enterprise_message(db, user, data)
    return ok(result.model_dump(mode="json"))


@router.post("/api/v1/assistants/student/messages")
def student_assistant(data: AssistantRequest,
                      user: SysUser = Depends(require_password_changed),
                      db: Session = Depends(get_db)):
    """API030 学生助手（受控查询及确认卡，不向工作流传登录令牌）"""
    result = student_assistant_service.handle_student_message(db, user, data)
    return ok(result.model_dump(mode="json"))


@router.post("/api/v1/transcriptions")
def transcribe(file: UploadFile = File(...), user: SysUser = Depends(require_password_changed),db:Session=Depends(get_db)):
    """API031 语音转写（ASR，M3）"""
    from app.services.transcription_service import transcribe as convert
    db.rollback()
    return ok(convert(file))
