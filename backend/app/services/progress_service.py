"""
M3 申请进度登记 —— API080 建内部跟踪事项 / API081 追加进度或补料说明

规则（对齐 M3 模块文档与 04 契约）：
  1. 只登记本系统内部事项，不调用校方/签证外部系统（data_source=MANUAL）。
  2. 同一 case_no 一系列事件，sequence_no 递增，previous_id 唯一防分叉。
  3. 阶段只能按序推进：SUBMITTED → PROCESSING → COMPLETED；
     完成时一次调用同时写 COMPLETED + NOTIFIED 并给学生发通知（原子）。
  4. DETAIL/ASSIGNMENT 沿用当前阶段，不改写历史。
  5. 本模块只 flush，不 commit。
"""
from app.core.idempotency import idempotent
import logging
import uuid
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.confirmation import verify_confirmation
from app.core.errors import InvalidRequestError, NotFoundError
from app.core.notification import notify
from app.models.application_progress import StudentApplicationProgress
from app.models.organization import SysDepartment
from app.models.student import StudentProfile
from app.models.user import SysUser
from app.repositories.common import require_student_visible
from app.repositories import lead as lead_repo
from app.schemas.application import ApplicationAdvanceIn, ApplicationCreateIn
from app.schemas.student import ApplicationEventDTO
from app.services import m3_canonical
from app.services.m3_errors import SequenceConflictError, StateTransitionDeniedError

logger = logging.getLogger(__name__)

_ADVISOR_ROLES = ("ADVISOR", "SENIOR_ADVISOR", "ADMIN")


def _is_head_of(db: Session, actor: SysUser, dept_id: int | None) -> bool:
    if dept_id is None:
        return False
    return db.scalar(select(SysDepartment.id).where(
        SysDepartment.id == dept_id,
        SysDepartment.head_user_id == actor.id)) is not None


def _require_case_manager(db: Session, actor: SysUser, profile: StudentProfile) -> None:
    """本人顾问 / 主管部门 / 管理员。"""
    if actor.employee_role == "ADMIN":
        return
    if profile.advisor_user_id == actor.id:
        return
    if _is_head_of(db, actor, profile.dept_id):
        return
    raise NotFoundError("资源不存在")


def _validate_assignee(db: Session, actor: SysUser, profile: StudentProfile,
                       assignee_user_id: int) -> SysUser:
    assignee = db.get(SysUser, assignee_user_id)
    if assignee is None or assignee.status != "NORMAL" or assignee.employee_role not in _ADVISOR_ROLES:
        raise InvalidRequestError("指派处理人无效")
    if (actor.employee_role != "ADMIN" and assignee.employee_role != "ADMIN"
            and assignee.dept_id != profile.dept_id):
        raise InvalidRequestError("指派处理人须与学生同部门")
    return assignee


def _event_to_dto(db: Session, e: StudentApplicationProgress) -> ApplicationEventDTO:
    assignee = db.get(SysUser, e.assignee_user_id) if e.assignee_user_id else None
    return ApplicationEventDTO(
        id=str(e.id), caseNo=str(e.case_no), studentProfileId=str(e.student_profile_id),
        sequenceNo=e.sequence_no, itemType=e.item_type, title=e.title, stage=e.stage,
        eventKind=e.event_kind, detail=e.detail,
        assigneeDisplayName=assignee.real_name if assignee else None,
        occurredAt=e.occurred_at, dataSource=e.data_source, createTime=e.create_time,
    )


def _latest_event(db: Session, case_no: UUID) -> StudentApplicationProgress | None:
    return db.scalar(
        select(StudentApplicationProgress)
        .where(StudentApplicationProgress.case_no == case_no)
        .order_by(StudentApplicationProgress.sequence_no.desc())
        .limit(1)
        .with_for_update()
    )


def _root_id(db: Session, case_no: UUID) -> int | None:
    return db.scalar(select(StudentApplicationProgress.id).where(
        StudentApplicationProgress.case_no == case_no,
        StudentApplicationProgress.sequence_no == 1))


# =============================================================
# API080 人工建立内部跟踪事项
# =============================================================
@idempotent("progress_service.create_case")
def create_case(db: Session, actor: SysUser, data: ApplicationCreateIn) -> dict:
    profile = require_student_visible(db, actor, data.student_profile_id)
    _require_case_manager(db, actor, profile)

    # 幂等：同一 request_key 直接返回既有事项
    existing = db.scalar(select(StudentApplicationProgress).where(
        StudentApplicationProgress.request_key == data.request_key))
    if existing is not None:
        return {
            "caseNo": str(existing.case_no),
            "rootId": str(existing.id),
            "sequenceNo": existing.sequence_no,
            "stage": existing.stage,
        }

    _validate_assignee(db, actor, profile, data.assignee_user_id)

    if data.enrollment_id is not None:
        from app.models.enrollment import StudentCourseEnrollment
        enrollment = db.get(StudentCourseEnrollment, data.enrollment_id)
        if enrollment is None or enrollment.student_profile_id != profile.id:
            raise InvalidRequestError("课程关联不存在")

    case_no = uuid.uuid4()
    event = StudentApplicationProgress(
        case_no=case_no,
        student_profile_id=profile.id,
        enrollment_id=data.enrollment_id,
        sequence_no=1,
        previous_id=None,
        item_type=data.item_type,
        title=data.title,
        target_country=data.target_country,
        target_school=data.target_school,
        target_program=data.target_program,
        stage="SUBMITTED",
        event_kind="STAGE",
        detail=data.detail,
        assignee_user_id=data.assignee_user_id,
        recorded_by_user_id=actor.id,
        data_source="MANUAL",
        occurred_at=data.occurred_at,
        request_key=data.request_key,
    )
    db.add(event)
    db.flush()
    return {
        "caseNo": str(case_no),
        "rootId": str(event.id),
        "sequenceNo": event.sequence_no,
        "stage": event.stage,
    }


# =============================================================
# API081 追加进度 / 补料说明
# =============================================================
@idempotent("progress_service.advance_case")
def advance_case(db: Session, actor: SysUser, case_no_str: str,
                 data: ApplicationAdvanceIn) -> dict:
    try:
        case_no = UUID(case_no_str)
    except ValueError as exc:
        raise NotFoundError("资源不存在") from exc

    # 幂等：同一 request_key 已写入 → 返回当前事项快照
    existing = db.scalar(select(StudentApplicationProgress).where(
        StudentApplicationProgress.request_key == data.request_key))
    if existing is not None and existing.case_no == case_no:
        return _case_snapshot(db, case_no, [existing])

    if data.confirmation_token:
        verify_confirmation(actor, data.confirmation_token, operation="ADVANCE_APPLICATION",
                            entity_id=None,
                            payload=m3_canonical.application_advance_payload(case_no_str, data), request_key=data.request_key)

    latest = _latest_event(db, case_no)
    if latest is None:
        raise NotFoundError("资源不存在")
    profile = db.get(StudentProfile, latest.student_profile_id)
    if profile is None:
        raise NotFoundError("资源不存在")
    _require_case_manager(db, actor, profile)

    db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key,9103))"),{"key":str(case_no)})
    db.expire_all()
    latest=_latest_event(db,case_no)
    if data.assignee_user_id is not None:_validate_assignee(db,actor,profile,data.assignee_user_id)
    if data.expected_sequence != latest.sequence_no:
        raise SequenceConflictError()

    if latest.stage == "NOTIFIED":
        raise StateTransitionDeniedError("该事项已完成，不能继续追加")

    prev = latest
    created: list[StudentApplicationProgress] = []

    def _append(*, stage: str, event_kind: str, detail: str,
                assignee_id: int, request_key) -> StudentApplicationProgress:
        nonlocal prev
        event = StudentApplicationProgress(
            case_no=case_no,
            student_profile_id=latest.student_profile_id,
            enrollment_id=latest.enrollment_id,
            sequence_no=prev.sequence_no + 1,
            previous_id=prev.id,
            item_type=latest.item_type,
            title=latest.title,
            target_country=latest.target_country,
            target_school=latest.target_school,
            target_program=latest.target_program,
            stage=stage,
            event_kind=event_kind,
            detail=detail,
            assignee_user_id=assignee_id,
            recorded_by_user_id=actor.id,
            data_source="MANUAL",
            occurred_at=data.occurred_at,
            request_key=request_key,
        )
        db.add(event)
        db.flush()
        created.append(event)
        prev = event
        return event

    if data.event_kind == "STAGE":
        if data.stage == "PROCESSING":
            if latest.stage != "SUBMITTED":
                raise StateTransitionDeniedError("只能从已提交推进到处理中")
            _append(stage="PROCESSING", event_kind="STAGE", detail=data.detail,
                    assignee_id=data.assignee_user_id or latest.assignee_user_id,
                    request_key=data.request_key)
        elif data.stage == "COMPLETED":
            if latest.stage != "PROCESSING":
                raise StateTransitionDeniedError("只能从处理中推进到已完成")
            completed = _append(
                stage="COMPLETED", event_kind="STAGE", detail=data.detail,
                assignee_id=data.assignee_user_id or latest.assignee_user_id,
                request_key=data.request_key)
            notified_key = uuid.uuid5(
                uuid.NAMESPACE_URL, f"m3:case:{case_no}:notified:{data.request_key}")
            notified = _append(
                stage="NOTIFIED", event_kind="STAGE", detail="结果已通知学生",
                assignee_id=completed.assignee_user_id,
                request_key=notified_key)
            # 通知学生（与 COMPLETED+NOTIFIED 同事务）
            root_id = _root_id(db, case_no)
            notify(db, f"application:{case_no}:notified:{notified.id}",
                   [profile.user_id], category="SYSTEM",
                   title="申请进度已更新",
                   content=f"您的「{latest.title}」已完成并通知结果，详情请查看申请时间线",
                   related_type="application_case", related_id=root_id)
        else:
            raise InvalidRequestError("STAGE 事件必须指定 PROCESSING 或 COMPLETED")
    else:
        # DETAIL / ASSIGNMENT：沿用当前阶段
        if data.event_kind == "ASSIGNMENT":
            if data.assignee_user_id is None:
                raise InvalidRequestError("转派必须指定处理人")
            _validate_assignee(db, actor, profile, data.assignee_user_id)
        _append(stage=latest.stage, event_kind=data.event_kind, detail=data.detail,
                assignee_id=data.assignee_user_id or latest.assignee_user_id,
                request_key=data.request_key)

    db.flush()
    logger.info("M3 申请进度推进 case=%s seq=%s kind=%s",
                case_no, prev.sequence_no, data.event_kind)
    return _case_snapshot(db, case_no, created)


def _case_snapshot(db: Session, case_no: UUID,
                   events: list[StudentApplicationProgress]) -> dict:
    latest = _latest_event(db, case_no)
    return {
        "caseNo": str(case_no),
        "latestSequence": latest.sequence_no if latest else None,
        "stage": latest.stage if latest else None,
        "events": [_event_to_dto(db, e).model_dump(mode="json") for e in events],
    }
