"""
心理关怀 —— 授权 / 观测 / 预警处置（⚠️ 敏感）
"""
from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.confirmation import verify_confirmation
from app.core.deps import require_password_changed
from app.core.responses import ok
from app.core.transaction import with_business_transaction
from app.db.session import get_db
from app.models.user import SysUser
from app.schemas.psych import PsychActionRequest, PsychConsentRequest, PsychCorrectionRequest
from app.services import m3_canonical, psych_guard, psych_service

router = APIRouter(tags=["心理关怀"])


@router.put("/api/v1/me/psych-consent")
def set_psych_consent(data: PsychConsentRequest,
                      user: SysUser = Depends(require_password_changed),
                      db: Session = Depends(get_db)):
    """API066 心理授权同意 / 撤回"""
    with with_business_transaction(db):
        result = psych_service.set_consent(db, user, data)
    return ok(result)


@router.get("/api/v1/employees/psych/students")
def list_psych_students(user: SysUser = Depends(require_password_changed),
                        db: Session = Depends(get_db),
                        page: int = Query(1, ge=1),
                        page_size: int = Query(20, ge=1, le=100),
                        class_id: int | None = Query(None),
                        keyword: str | None = Query(None),
                        assessment_date: date | None = Query(None, alias="date")):
    """API067 按班级/姓名查日状态（需 can_see_psych）"""
    items, total = psych_service.list_psych_students(
        db, user, date=assessment_date, class_id=class_id, keyword=keyword,
        page=page, page_size=page_size)
    return ok({"items": [i.model_dump(mode="json") for i in items],
               "page": page, "pageSize": page_size, "total": total})


@router.get("/api/v1/employees/students/{student_id}/psych-observations")
def psych_observations(student_id: int,
                       user: SysUser = Depends(require_password_changed),
                       db: Session = Depends(get_db),
                       page: int = Query(1, ge=1),
                       page_size: int = Query(20, ge=1, le=100),
                       start_date: date | None = Query(None),
                       end_date: date | None = Query(None)):
    """API068 心理观测（需 can_see_psych + 范围）"""
    items, total = psych_service.list_observations(
        db, user, student_id, start_date=start_date, end_date=end_date,
        page=page, page_size=page_size)
    return ok({"items": [i.model_dump(mode="json") for i in items],
               "page": page, "pageSize": page_size, "total": total})


@router.post("/api/v1/employees/students/{student_id}/psych-corrections")
def psych_correction(student_id: int, data: PsychCorrectionRequest,
                     user: SysUser = Depends(require_password_changed),
                     db: Session = Depends(get_db)):
    """API069 人工修正情绪标签（仅主管/管理员 + 心理授权）"""
    with with_business_transaction(db):
        result = psych_service.correct_observation(db, user, student_id, data)
    return ok(result)


@router.get("/api/v1/employees/psych-alerts")
def list_psych_alerts(user: SysUser = Depends(require_password_changed),
                      db: Session = Depends(get_db),
                      page: int = Query(1, ge=1),
                      page_size: int = Query(20, ge=1, le=100),
                      status_: str | None = Query(None, alias="status"),
                      severity: str | None = Query(None),
                      class_id: int | None = Query(None)):
    """API070 预警列表（需 can_see_psych）"""
    items, total = psych_service.list_alerts(
        db, user, status=status_, severity=severity, class_id=class_id,
        page=page, page_size=page_size)
    return ok({"items": [i.model_dump(mode="json") for i in items],
               "page": page, "pageSize": page_size, "total": total})


@router.get("/api/v1/employees/psych-alerts/{alert_id}")
def get_psych_alert(alert_id: int,
                    user: SysUser = Depends(require_password_changed),
                    db: Session = Depends(get_db)):
    """API071 预警详情"""
    dto = psych_service.get_alert(db, user, alert_id)
    return ok(dto.model_dump(mode="json"))


@router.post("/api/v1/employees/psych-alerts/{alert_id}/actions")
def psych_alert_action(alert_id: int, data: PsychActionRequest,
                       user: SysUser = Depends(require_password_changed),
                       db: Session = Depends(get_db)):
    """API072 预警处置（NOTE 由 M4 校验；复核/终结要求主管+心理授权）"""
    if data.confirmation_token:
        verify_confirmation(user, data.confirmation_token, operation="PSYCH_ALERT_NOTE",
                            entity_id=alert_id,
                            payload=m3_canonical.psych_note_payload(data),
                            expected_version=data.expected_version, request_key=data.request_key)
    # M3 兜底：堵 M4 用 employee_role 判断主管的越权缺口
    psych_guard.guard_alert_action(db, user, alert_id, data.action)
    with with_business_transaction(db):
        dto = psych_service.review_alert(db, user, alert_id, data)
    return ok(dto.model_dump(mode="json"))
