"""
心理关怀业务（⚠️ 敏感，读取需 psych_access_enabled）

含导出的 M3 Interface：review_alert；以及观察流程 observe_emotion 供学生助手/表单调用。
情绪观测规则：授权有效才观测；先 Python 直接风险词命中落 RULE 观测 + HIGH 告警，
再在事务外调 Dify 分析；source_event_key 去重；同日多版本取最后有效；风险只升不降。
"""
import logging
import uuid
from datetime import datetime, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import (
    AIBadResponseError,
    AITimeoutError,
    AIUnavailableError,
    ForbiddenError,
    InvalidRequestError,
    NotFoundError,
    StateConflictError,
    VersionConflictError,
)
from app.core.notification import notify
from app.core.transaction import with_business_transaction
from app.models.organization import SysClass, SysDepartment
from app.models.psych import StudentPsychAlert, StudentPsychProfile
from app.models.student import StudentProfile
from app.models.user import SysUser
from app.repositories import psych_repo, student_repo
from app.repositories.common import my_profile_id, paginate, require_student_visible, visible_student_ids
from app.schemas.psych import (
    ActiveAlertBrief,
    PsychActionRequest,
    PsychAlertDTO,
    PsychConsentRequest,
    PsychCorrectionRequest,
    PsychObservationDTO,
    PsychStudentSummary,
)

logger = logging.getLogger(__name__)

# 直接风险特殊词（来源材料：想死 / 不想活 / 自杀 等）
DIRECT_RISK_WORDS = ("想死", "不想活", "自杀", "轻生", "自残", "自伤", "结束生命", "活不下去", "不想活了")

_PSYCH_NAMESPACE = uuid.UUID("e6d9c5b0-4a1e-4f0a-8b3e-2c9f6a7d1b0e")
_SEV_ORDER = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}


def _sub_key(message_id: str, sub: str) -> UUID:
    """消息 id 派生的确定性子事件键（直接词 / 情绪分别去重）。"""
    return uuid.uuid5(_PSYCH_NAMESPACE, f"{message_id}:{sub}")


def detect_direct_word(text: str) -> str | None:
    for w in DIRECT_RISK_WORDS:
        if w in (text or ""):
            return w
    return None


def evaluate_risk(finals: list[dict], direct_signal: bool = False) -> tuple[str, str] | None:
    """按规则顺序（先高再中再低）判定风险，返回 (signal_code, severity) 或 None。

    finals 为最近 N 个相邻自然日的最终状态（旧→新），emotion_state 缺失为 None。
    """
    if direct_signal:
        return "H_DIRECT", "HIGH"

    states = [f.get("emotion_state") for f in finals]
    last2 = states[-2:] if len(states) >= 2 else []
    last4 = states[-4:] if len(states) >= 4 else []

    if len(last4) == 4 and all(s == "NEGATIVE" for s in last4):
        return "H_4N", "HIGH"
    if len(last2) == 2 and all(s == "VERY_NEGATIVE" for s in last2):
        return "H_2V", "HIGH"
    if len(last2) == 2 and set(last2) == {"VERY_NEGATIVE", "NEGATIVE"}:
        return "M_MIX", "MEDIUM"
    if states and states[-1] == "VERY_NEGATIVE":
        return "L_1V", "LOW"
    if len(last2) == 2 and all(s == "NEGATIVE" for s in last2):
        return "L_2N", "LOW"
    return None


# =============================================================
# 授权
# =============================================================
def set_consent(db: Session, user: SysUser, req: PsychConsentRequest) -> dict:
    profile = student_repo.get_profile_by_user(db, user.id)
    if profile is None:
        raise NotFoundError("学生档案不存在")
    if profile.version != req.expected_version:
        raise VersionConflictError(profile.version)

    now = datetime.now(timezone.utc)
    if req.granted:
        profile.psych_consent_status = "GRANTED"
        profile.psych_consent_at = now
        profile.psych_consent_version = req.consent_version
        profile.psych_withdrawn_at = None
    else:
        profile.psych_consent_status = "WITHDRAWN"
        profile.psych_withdrawn_at = now
    profile.version += 1
    db.flush()
    return {"status": profile.psych_consent_status, "consentedAt": profile.psych_consent_at,
            "withdrawnAt": profile.psych_withdrawn_at, "studentVersion": profile.version}


# =============================================================
# 观测（授权、多版本、日状态、风险）
# =============================================================
def _record_observation(db: Session, profile: StudentProfile, *, source_event_key: UUID,
                        received_at: datetime, assessment_source: str, emotion_state: str,
                        assessment_data: dict, summary: str | None, is_valid: bool,
                        created_by_user_id: int | None = None) -> StudentPsychProfile | None:
    """追加一条观测版本（调用方需在事务内）。返回 None 表示已去重或授权失效。"""
    if db.scalar(select(StudentPsychProfile.id).where(
            StudentPsychProfile.source_event_key == source_event_key)):
        return None

    profile = db.get(StudentProfile, profile.id, with_for_update=True)
    if profile.psych_consent_status != "GRANTED":
        return None

    tz = ZoneInfo(settings.business_timezone)
    obs = StudentPsychProfile(
        student_profile_id=profile.id,
        version_no=psych_repo.get_latest_version_no(db, profile.id) + 1,
        assessment_date=received_at.astimezone(tz).date(),
        business_timezone=settings.business_timezone,
        observed_at=received_at,
        source_event_key=source_event_key,
        assessment_source=assessment_source,
        emotion_state=emotion_state,
        assessment_data=assessment_data,
        summary=summary,
        consent_at=profile.psych_consent_at or received_at,
        status="AUTO_RECORDED",
        is_valid=is_valid,
        created_by_user_id=created_by_user_id,
    )
    db.add(obs)
    db.flush()
    return obs


def _resolve_follow_up(db: Session, profile: StudentProfile) -> tuple[int | None, list[int]]:
    teacher_id = None
    if profile.class_id:
        cls = db.get(SysClass, profile.class_id)
        teacher_id = cls.head_teacher_id if cls else None
    dept = db.get(SysDepartment, profile.dept_id)
    head_id = dept.head_user_id if dept else None
    follow_up = teacher_id or profile.advisor_user_id or head_id
    recipients = [x for x in (teacher_id, profile.advisor_user_id, head_id) if x]
    return follow_up, recipients


def _notify_alert(db: Session, alert: StudentPsychAlert, recipients: list[int]) -> None:
    for rid in dict.fromkeys(recipients):
        notify(db, f"psych:{alert.id}:alert:{alert.severity}", [rid],
               category="PSYCH_ALERT", title="有待复核的关怀事项",
               content="系统识别到需关注的关怀事项，请及时查看并处理",
               related_type="psych_alert", related_id=alert.id)


def _upsert_alert(db: Session, profile: StudentProfile, obs: StudentPsychProfile,
                  severity: str, signal_code: str, summary: str) -> None:
    now = datetime.now(timezone.utc)
    follow_up, recipients = _resolve_follow_up(db, profile)
    open_alert = psych_repo.get_open_alert(db, profile.id)

    if open_alert is None:
        alert = StudentPsychAlert(
            student_profile_id=profile.id, psych_profile_id=obs.id, severity=severity,
            signal_code=signal_code, trigger_summary=summary, status="PENDING_REVIEW",
            follow_up_user_id=follow_up, handling_history=[], trigger_key=uuid.uuid4().hex,
            repeat_count=1, last_triggered_at=now, version=1,
        )
        db.add(alert)
        db.flush()
        _notify_alert(db, alert, recipients)
    else:
        if _SEV_ORDER[severity] > _SEV_ORDER[open_alert.severity]:
            open_alert.severity = severity
            open_alert.signal_code = signal_code
            open_alert.trigger_summary = summary
            _notify_alert(db, open_alert, recipients)
        open_alert.repeat_count += 1
        open_alert.last_triggered_at = now
        open_alert.psych_profile_id = obs.id
        open_alert.version += 1


def record_direct_risk(db: Session, profile: StudentProfile, *, source_event_key: UUID,
                       received_at: datetime, matched_word: str) -> None:
    """直接风险词命中：立即落 RULE 观测（UNKNOWN/无效）+ HIGH 告警，不等待 Dify。"""
    obs = _record_observation(
        db, profile, source_event_key=source_event_key, received_at=received_at,
        assessment_source="RULE", emotion_state="UNKNOWN",
        assessment_data={"direct_word": matched_word, "rule": "H_DIRECT"},
        summary=f"直接风险词命中：{matched_word}", is_valid=False)
    if obs is not None:
        _upsert_alert(db, profile, obs, "HIGH", "H_DIRECT", "直接风险词命中（待人工复核）")


def record_dify_observation(db: Session, profile: StudentProfile, *, source_event_key: UUID,
                            received_at: datetime, emotion_state: str, confidence: float) -> None:
    """保存 Dify 情绪观测，并重算风险。检测失败时调用方不调用本函数。"""
    if emotion_state not in ("HEALTHY", "NEGATIVE", "VERY_NEGATIVE"):
        emotion_state = "UNKNOWN"
    is_valid = emotion_state != "UNKNOWN"

    obs = _record_observation(
        db, profile, source_event_key=source_event_key, received_at=received_at,
        assessment_source="DIFY", emotion_state=emotion_state,
        assessment_data={"confidence": round(confidence, 3)}, summary=None, is_valid=is_valid)
    if obs is None or not is_valid:
        return

    finals = psych_repo.get_daily_final_states(db, profile.id, 4)
    risk = evaluate_risk(finals, direct_signal=False)
    if risk:
        _upsert_alert(db, profile, obs, risk[1], risk[0], f"情绪规则触发 {risk[0]}")


def observe_emotion(db: Session, profile: StudentProfile, *, message_id: str, text: str,
                    received_at: datetime | None = None, detect_fn) -> None:
    """学生消息情绪观测（供学生助手调用）。detect_fn(text) -> {"emotion_state","confidence"}。

    直接词先行落库并立即通知，不因 Dify 超时阻断；Dify 在事务外调用。
    """
    if profile.psych_consent_status != "GRANTED":
        return
    received_at = received_at or datetime.now(timezone.utc)

    matched = detect_direct_word(text)
    if matched:
        with with_business_transaction(db):
            record_direct_risk(db, profile, source_event_key=_sub_key(message_id, "direct"),
                               received_at=received_at, matched_word=matched)

    try:
        emo = detect_fn(text)
    except (AIUnavailableError, AITimeoutError, AIBadResponseError) as exc:
        logger.info("情绪检测不可用（%s），保留已产生告警", exc.__class__.__name__)
        return
    if not emo or "emotion_state" not in emo:
        return

    with with_business_transaction(db):
        record_dify_observation(db, profile, source_event_key=_sub_key(message_id, "emotion"),
                                received_at=received_at,
                                emotion_state=emo.get("emotion_state", "UNKNOWN"),
                                confidence=float(emo.get("confidence", 0.0) or 0.0))


def get_daily_final_states(db: Session, profile_id: int, days: int) -> list[dict]:
    return psych_repo.get_daily_final_states(db, profile_id, days)


# =============================================================
# 查询（需 psych_access_enabled）
# =============================================================
def _require_psych_access(user: SysUser) -> None:
    if not user.psych_access_enabled:
        raise ForbiddenError("需要心理数据授权")


def _obs_to_dto(o: StudentPsychProfile) -> PsychObservationDTO:
    return PsychObservationDTO(
        id=str(o.id), versionNo=o.version_no, assessmentDate=o.assessment_date,
        observedAt=o.observed_at, emotionState=o.emotion_state, assessmentSource=o.assessment_source,
        status=o.status, isValid=o.is_valid, summary=o.summary, verifiedAt=o.verified_at,
    )


def _alert_to_dto(db: Session, a: StudentPsychAlert) -> PsychAlertDTO:
    profile = db.get(StudentProfile, a.student_profile_id)
    user = db.get(SysUser, profile.user_id) if profile else None
    return PsychAlertDTO(
        id=str(a.id), studentProfileId=str(a.student_profile_id),
        studentDisplayName=user.real_name if user else "",
        classId=str(profile.class_id) if profile and profile.class_id else None,
        severity=a.severity, signalCode=a.signal_code, triggerSummary=a.trigger_summary,
        status=a.status, followUpUserId=str(a.follow_up_user_id) if a.follow_up_user_id else None,
        repeatCount=a.repeat_count, lastTriggeredAt=a.last_triggered_at,
        reviewedAt=a.reviewed_at, actionNote=a.action_note,
        handlingHistory=a.handling_history or [], version=a.version,
    )


def list_psych_students(db: Session, user: SysUser, *, date=None, class_id: int | None = None,
                        keyword: str | None = None, page: int = 1, page_size: int = 20):
    """API067 按班级/姓名查日状态。"""
    _require_psych_access(user)
    from datetime import date as _date
    d = date or datetime.now(ZoneInfo(settings.business_timezone)).date()

    ids = visible_student_ids(db, user)
    stmt = select(StudentProfile).join(SysUser, StudentProfile.user_id == SysUser.id)
    if ids is not None:
        stmt = stmt.where(StudentProfile.id.in_(ids))
    if class_id:
        stmt = stmt.where(StudentProfile.class_id == class_id)
    if keyword:
        stmt = stmt.where(SysUser.real_name.ilike(f"%{keyword}%"))
    stmt = stmt.order_by(StudentProfile.id)

    items, total = paginate(db, stmt, page, page_size)
    result = []
    for p in items:
        u = db.get(SysUser, p.user_id)
        emotion = psych_repo.get_daily_final_states(db, p.id, 1)
        state = emotion[-1]["emotion_state"] if emotion else None
        open_alert = psych_repo.get_open_alert(db, p.id)
        result.append(PsychStudentSummary(
            studentProfileId=str(p.id), realName=u.real_name if u else "",
            classId=str(p.class_id) if p.class_id else None,
            assessmentDate=d, emotionState=state or "UNKNOWN",
            latestObservedAt=None,
            activeAlert=ActiveAlertBrief(id=str(open_alert.id), severity=open_alert.severity,
                                         status=open_alert.status) if open_alert else None,
        ))
    return result, total


def list_observations(db: Session, user: SysUser, student_id: int, *, start_date=None,
                      end_date=None, page: int = 1, page_size: int = 20):
    """API068 受限观测历史。"""
    _require_psych_access(user)
    require_student_visible(db, user, student_id)
    items, total = psych_repo.list_observations(
        db, student_id, start_date=start_date, end_date=end_date, page=page, page_size=page_size)
    return [_obs_to_dto(o) for o in items], total


def correct_observation(db: Session, actor: SysUser, student_id: int,
                        req: PsychCorrectionRequest) -> dict:
    """API069 主管人工修正观测（追加版本，不删旧行）。"""
    _require_psych_access(actor)
    if actor.employee_role not in ("ADVISOR", "SENIOR_ADVISOR", "ADMIN"):
        raise ForbiddenError("仅主管或管理员可人工修正")
    require_student_visible(db, actor, student_id)

    original = psych_repo.get_observation(db, req.replaces_profile_id)
    if original is None or original.student_profile_id != student_id:
        raise NotFoundError("资源不存在")
    if original.version_no != req.expected_latest_version:
        raise StateConflictError("观测已变更，请刷新后处理")

    now = datetime.now(timezone.utc)
    new_obs = StudentPsychProfile(
        student_profile_id=student_id,
        version_no=original.version_no + 1,
        assessment_date=original.assessment_date,
        business_timezone=original.business_timezone,
        observed_at=now,
        source_event_key=req.request_key,
        assessment_source="MANUAL",
        emotion_state=req.emotion_state,
        assessment_data={"reason": req.reason, "corrects": str(original.id)},
        summary=req.reason,
        consent_at=original.consent_at,
        status="CORRECTED",
        is_valid=(req.emotion_state != "UNKNOWN"),
        invalidated_reason=req.reason if req.emotion_state == "UNKNOWN" else None,
        replaces_profile_id=original.id,
        created_by_user_id=actor.id,
    )
    db.add(new_obs)
    # 标记原观测失效，使日状态取修正后的版本
    original.is_valid = False
    original.invalidated_reason = f"被人工修正（版本 #{new_obs.version_no}）"
    db.flush()
    return {"profileId": str(new_obs.id), "versionNo": new_obs.version_no,
            "assessmentDate": new_obs.assessment_date, "emotionState": new_obs.emotion_state}


def list_alerts(db: Session, user: SysUser, *, status: str | None = None,
                severity: str | None = None, class_id: int | None = None,
                page: int = 1, page_size: int = 20):
    """API070 受限预警列表。"""
    _require_psych_access(user)
    ids = visible_student_ids(db, user)
    if ids is not None and class_id:
        ids = list(db.scalars(select(StudentProfile.id).where(
            StudentProfile.id.in_(ids), StudentProfile.class_id == class_id)).all())
    items, total = psych_repo.list_alerts(
        db, profile_ids=ids, status=status, severity=severity, page=page, page_size=page_size)
    return [_alert_to_dto(db, a) for a in items], total


def get_alert(db: Session, user: SysUser, alert_id: int) -> PsychAlertDTO:
    """API071 受限预警详情。"""
    _require_psych_access(user)
    a = psych_repo.get_alert(db, alert_id)
    if a is None:
        raise NotFoundError("资源不存在")
    require_student_visible(db, user, a.student_profile_id)
    return _alert_to_dto(db, a)


# =============================================================
# 预警处置（M3 控制器复用 review_alert）
# =============================================================
def _can_note_alert(db: Session, actor: SysUser, a: StudentPsychAlert) -> bool:
    if a.follow_up_user_id == actor.id:
        return True
    profile = db.get(StudentProfile, a.student_profile_id)
    if profile is None:
        return False
    if profile.advisor_user_id == actor.id:
        return True
    if profile.class_id:
        cls = db.get(SysClass, profile.class_id)
        if cls and cls.head_teacher_id == actor.id:
            return True
    return False


def review_alert(db: Session, actor: SysUser, alert_id: int,
                 req: PsychActionRequest) -> PsychAlertDTO:
    """API072 人工复核/跟进/终结（M3 控制器复用）。"""
    a = psych_repo.get_alert(db, alert_id)
    if a is None:
        raise NotFoundError("资源不存在")
    if a.version != req.expected_version:
        raise VersionConflictError(a.version)

    if req.action == "NOTE":
        if not _can_note_alert(db, actor, a):
            raise ForbiddenError("无权处理该预警")
    else:
        _require_psych_access(actor)
        if actor.employee_role not in ("ADVISOR", "SENIOR_ADVISOR", "ADMIN"):
            raise ForbiddenError("仅主管或管理员可复核/终结预警")

    now = datetime.now(timezone.utc)
    history = list(a.handling_history or [])
    history.append({"action": req.action, "actor": str(actor.id), "at": now.isoformat(),
                    "note": req.note})

    if req.action == "CONFIRM":
        a.status = "CONFIRMED"
    elif req.action == "START_HANDLING":
        a.status = "HANDLING"
    elif req.action == "DISMISS":
        a.status = "DISMISSED"
        a.closed_at = now
    elif req.action == "CLOSE":
        a.status = "CLOSED"
        a.closed_at = now
    # NOTE 不改变状态

    if req.action != "NOTE":
        a.reviewed_by_user_id = actor.id
        a.reviewed_at = now
    a.action_note = req.note
    a.handling_history = history
    a.version += 1
    db.flush()
    return _alert_to_dto(db, a)
