"""
成绩 / 日程提醒 / 申请进度 / 签约前评估摘要 / 升学意向 业务
"""
from app.core.idempotency import idempotent
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.confirmation import verify_confirmation
from app.core.errors import InvalidRequestError, NotFoundError, StateConflictError, VersionConflictError
from app.core.notification import notify
from app.models.follow_up import CrmFollowUp
from app.models.lead import CrmLead
from app.models.user import SysUser
from app.repositories import academic_repo, student_repo
from app.repositories.common import my_profile_id, require_student_visible
from app.schemas.student import (
    ApplicationCaseDTO,
    ApplicationEventDTO,
    ReminderRequest,
    ScheduleDTO,
    ScoreDTO,
    UpgradeInterestRequest,
)

logger = logging.getLogger(__name__)


def _own_profile_id(db: Session, user: SysUser) -> int:
    pid = my_profile_id(db, user)
    if pid <= 0:
        raise NotFoundError("学生档案不存在")
    return pid


def _resolve_profile_id(db: Session, user: SysUser, student_id: int | None) -> int:
    if user.is_student:
        return _own_profile_id(db, user)
    if student_id is None:
        raise InvalidRequestError("缺少学生标识")
    require_student_visible(db, user, student_id)
    return student_id


# ---- 成绩（只读）----
def _score_to_dto(s) -> ScoreDTO:
    return ScoreDTO(
        id=str(s.id), version=s.version, subject=s.subject, scoreType=s.score_type, scoreText=s.score_text,
        scoreNumeric=str(s.score_numeric) if s.score_numeric is not None else None,
        maxScore=str(s.max_score) if s.max_score is not None else None,
        gradedAt=s.graded_at,
        enrollmentId=str(s.enrollment_id) if s.enrollment_id else None,
        scheduleId=str(s.schedule_id) if s.schedule_id else None,
        remark=s.remark, dataSource=s.data_source,
    )


def list_scores(db: Session, user: SysUser, *, student_id: int | None = None,
                enrollment_id: int | None = None, subject: str | None = None,
                page: int = 1, page_size: int = 20):
    profile_id = _resolve_profile_id(db, user, student_id)
    items, total = academic_repo.list_scores(
        db, profile_id, enrollment_id=enrollment_id, subject=subject,
        page=page, page_size=page_size)
    return [_score_to_dto(s) for s in items], total


# ---- 日程 ----
def _schedule_to_dto(s) -> ScheduleDTO:
    return ScheduleDTO(
        id=str(s.id), scheduleType=s.schedule_type, title=s.title, description=s.description,
        startAt=s.start_at, endAt=s.end_at, location=s.location, remindAt=s.remind_at,
        status=s.status, dataSource=s.data_source, reminderRevision=s.reminder_revision,
        version=s.version,
    )


def list_schedules(db: Session, user: SysUser, *, start_at=None, end_at=None,
                   schedule_type: str | None = None, page: int = 1, page_size: int = 20):
    profile_id = _own_profile_id(db, user)
    items, total = academic_repo.list_schedules(
        db, profile_id, start_at=start_at, end_at=end_at,
        schedule_type=schedule_type, page=page, page_size=page_size)
    return [_schedule_to_dto(s) for s in items], total


@idempotent("academic_service.set_reminder")
def set_reminder(db: Session, user: SysUser, schedule_id: int, req: ReminderRequest) -> dict:
    profile_id = _own_profile_id(db, user)
    sched = academic_repo.get_schedule(db, schedule_id)
    if sched is None or sched.student_profile_id != profile_id:
        raise NotFoundError("资源不存在")
    if sched.version != req.expected_version:
        raise VersionConflictError(sched.version)

    if req.remind_at is not None:
        if req.remind_at <= datetime.now(timezone.utc):
            raise InvalidRequestError("提醒时间必须在未来")
        if req.remind_at > sched.start_at:
            raise InvalidRequestError("提醒时间不能晚于节点开始时间")

    sched.remind_at = req.remind_at
    sched.reminder_revision += 1        # 变更提醒版本，防止旧任务发送
    sched.version += 1
    db.flush()
    return {"id": str(sched.id), "remindAt": req.remind_at,
            "reminderRevision": sched.reminder_revision, "version": sched.version}


# ---- 申请进度 ----
def _event_to_dto(db: Session, e) -> ApplicationEventDTO:
    assignee = db.get(SysUser, e.assignee_user_id) if e.assignee_user_id else None
    return ApplicationEventDTO(
        id=str(e.id), caseNo=str(e.case_no), studentProfileId=str(e.student_profile_id),
        sequenceNo=e.sequence_no, itemType=e.item_type, title=e.title, stage=e.stage,
        eventKind=e.event_kind, detail=e.detail,
        assigneeDisplayName=assignee.real_name if assignee else None,
        occurredAt=e.occurred_at, dataSource=e.data_source, createTime=e.create_time,
    )


def list_application_cases(db: Session, user: SysUser, *, student_id: int | None = None,
                           item_type: str | None = None, stage: str | None = None,
                           page: int = 1, page_size: int = 20):
    profile_id = _resolve_profile_id(db, user, student_id)
    items, total = academic_repo.list_application_cases(
        db, profile_id, item_type=item_type, stage=stage, page=page, page_size=page_size)
    result = []
    for e in items:
        dto = _event_to_dto(db, e)
        result.append(ApplicationCaseDTO(
            caseNo=dto.caseNo, rootId=str(e.id), studentProfileId=dto.studentProfileId,
            itemType=dto.itemType, title=dto.title, targetSchool=e.target_school,
            targetCountry=e.target_country, targetProgram=e.target_program,
            stage=dto.stage, latestSequence=dto.sequenceNo,
            assigneeDisplayName=dto.assigneeDisplayName, occurredAt=dto.occurredAt,
            dataSource=dto.dataSource,
        ))
    return result, total


def case_timeline(db: Session, user: SysUser, case_no: str, *, page: int = 1, page_size: int = 20):
    from uuid import UUID as _UUID

    try:
        cno = _UUID(case_no)
    except ValueError:
        raise NotFoundError("资源不存在")

    if user.is_student:
        pid = _own_profile_id(db, user)
    else:
        # 员工：先找该 case 的任一事件确定学生，再校验可见性
        from app.models.application_progress import StudentApplicationProgress
        any_ev = db.scalar(select(StudentApplicationProgress).where(
            StudentApplicationProgress.case_no == cno))
        if any_ev is None:
            raise NotFoundError("资源不存在")
        require_student_visible(db, user, any_ev.student_profile_id)
        pid = any_ev.student_profile_id

    items, total = academic_repo.get_case_timeline(db, pid, cno, page=page, page_size=page_size)
    return [_event_to_dto(db, e) for e in items], total


# ---- 签约前评估可见摘要（API093）----
def get_initial_assessment(db: Session, user: SysUser) -> dict:
    profile = student_repo.get_profile_by_user(db, user.id)
    if profile is None or not profile.converted_lead_id:
        return {"available": False, "assessedAt": None, "projectMatches": [], "warnings": []}

    lead = db.get(CrmLead, profile.converted_lead_id)
    if lead is None or not lead.assessment_report:
        return {"available": False, "assessedAt": None, "projectMatches": [], "warnings": []}

    report = lead.assessment_report or {}
    matches = [
        {"projectId": str(p.get("projectId") or p.get("project_id")) if (p.get("projectId") or p.get("project_id")) else None,
         "decision": p.get("decision")}
        for p in (report.get("projects") or [])
    ]
    return {"available": True, "assessedAt": lead.assessed_at,
            "projectMatches": matches, "warnings": []}


# ---- 升学意向（API095）----
@idempotent("academic_service.create_upgrade_interest")
def create_upgrade_interest(db: Session, user: SysUser, req: UpgradeInterestRequest) -> dict:
    if not req.confirmed:
        raise InvalidRequestError("请确认后再提交")
    profile = student_repo.get_profile_by_user(db, user.id)
    if profile is None:
        raise NotFoundError("学生档案不存在")
    if not profile.converted_lead_id:
        raise StateConflictError("来源客户缺失，请联系顾问补齐")

    lead = db.get(CrmLead, profile.converted_lead_id)
    if lead is None:
        raise NotFoundError("来源客户不存在")
    if not profile.advisor_user_id:
        raise StateConflictError("暂无个人顾问，请联系管理员")

    if req.confirmation_token:
        verify_confirmation(user, req.confirmation_token, operation="UPGRADE_INTEREST",
                            entity_id=None, payload={"course_project_id": req.course_project_id, "note": req.note}, request_key=req.request_key)

    # 幂等
    existing = db.scalar(select(CrmFollowUp.id).where(
        CrmFollowUp.request_key == req.request_key))
    if existing:
        return {"accepted": True, "followUpId": str(existing),
                "advisorDisplayName": None}

    project = student_repo.get_project(db, req.course_project_id)
    if project is None or not project.is_published:
        raise InvalidRequestError("项目不存在或未发布")

    advisor = db.get(SysUser, profile.advisor_user_id)
    if not advisor or not advisor.is_employee or advisor.status!="NORMAL":raise StateConflictError("个人顾问不可用，请联系管理员")
    content = req.note or f"学生对项目「{project.name}」表达联系意向"
    fu = CrmFollowUp(
        lead_id=lead.id, actor_user_id=user.id, follow_up_type="UPSELL_INTEREST",
        content=content, request_key=req.request_key,
        details={"course_project_id": req.course_project_id},
    )
    db.add(fu)
    db.flush()

    notify(db, f"lead:{lead.id}:upgrade:{fu.id}", [advisor.id],
           category="SYSTEM", title="学生升学意向",
           content=f"学生「{user.real_name}」对项目「{project.name}」表达联系意向",
           related_type="lead", related_id=lead.id)

    return {"accepted": True, "followUpId": str(fu.id),
            "advisorDisplayName": advisor.real_name if advisor else None}
