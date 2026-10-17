"""
M3 员工学生管理 —— 学生列表/详情、调班换顾问、升学项目关联、员工查日程

权限基线：
  - 列表/详情：班主任本班 ∪ 顾问本人 ∪ 主管本部门 ∪ 管理员（visible_student_ids）
  - 调班换顾问/学籍：主管部门/管理员
  - 升学项目关联：本人顾问/主管部门/管理员
  - 范围外一律 404（不暴露存在性）
"""
from app.core.idempotency import idempotent
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import InvalidRequestError, NotFoundError, VersionConflictError
from app.models.admin_service import StudentAdminService
from app.models.course_project import CourseProject
from app.models.enrollment import StudentCourseEnrollment
from app.models.follow_up import CrmFollowUp
from app.models.lead import CrmLead
from app.models.organization import SysClass, SysDepartment
from app.models.student import StudentProfile
from app.models.user import SysUser
from app.repositories import academic_repo, employee as employee_repo, lead as lead_repo
from app.repositories import student_repo
from app.repositories.common import require_student_visible, visible_student_ids
from app.schemas.student import (
    EnrollmentCreateIn,
    EnrollmentUpdateIn,
    RelationshipUpdateIn,
    ScheduleDTO,
    StudentAdvisorBrief,
    StudentClassBrief,
    StudentEnrollmentItem,
    StudentStaffOut,
    StudentStaffSummaryOut,
)
from app.services.m3_errors import (
    DepartmentMismatchError,
    EnrollmentStatusConflictError,
    PendingRequestsRequireReassignError,
)

logger = logging.getLogger(__name__)

_ADVISOR_ROLES = ("ADVISOR", "SENIOR_ADVISOR")
_ADMIN_ROLES = (*_ADVISOR_ROLES, "ADMIN")


# =============================================================
# 范围辅助
# =============================================================
def _is_head_of(db: Session, actor: SysUser, dept_id: int | None) -> bool:
    if dept_id is None:
        return False
    return db.scalar(select(SysDepartment.id).where(
        SysDepartment.id == dept_id,
        SysDepartment.head_user_id == actor.id)) is not None


def _require_student_manager(db: Session, actor: SysUser, profile: StudentProfile) -> None:
    """本人顾问 / 主管部门 / 管理员；其余 404。"""
    if actor.employee_role == "ADMIN":
        return
    if profile.advisor_user_id == actor.id:
        return
    if _is_head_of(db, actor, profile.dept_id):
        return
    raise NotFoundError("资源不存在")


def _class_brief(db: Session, class_id: int | None) -> StudentClassBrief | None:
    if class_id is None:
        return None
    cls = db.get(SysClass, class_id)
    if cls is None:
        return None
    head = db.get(SysUser, cls.head_teacher_id) if cls.head_teacher_id else None
    return StudentClassBrief(
        id=str(cls.id), code=cls.code, name=cls.name, courseType=cls.course_type,
        deptId=str(cls.dept_id),
        headTeacher={"id": str(head.id), "realName": head.real_name} if head else None,
        isActive=True, version=1,
    )


# =============================================================
# API047 员工学生列表
# =============================================================
def list_students(db: Session, actor: SysUser, *, class_id: int | None = None,
                  keyword: str | None = None, page: int = 1, page_size: int = 20):
    if actor.employee_role not in _ADMIN_ROLES:
        raise NotFoundError("资源不存在")
    ids = visible_student_ids(db, actor)
    items, total = employee_repo.list_students(
        db, ids, class_id=class_id, keyword=keyword, page=page, page_size=page_size)

    class_ids = [p.class_id for p in items if p.class_id]
    classes = {c.id: c for c in db.scalars(select(SysClass).where(
        SysClass.id.in_(class_ids))).all()} if class_ids else {}

    result = []
    for p in items:
        user = db.get(SysUser, p.user_id)
        cls = classes.get(p.class_id)
        result.append(StudentStaffSummaryOut(
            id=str(p.id),
            realName=user.real_name if user else "",
            classId=str(p.class_id) if p.class_id else None,
            className=cls.name if cls else None,
            advisorUserId=str(p.advisor_user_id) if p.advisor_user_id else None,
            status=p.status,
            version=p.version,
        ))
    return result, total


# =============================================================
# API048 员工学生基础详情
# =============================================================
def get_student(db: Session, actor: SysUser, student_id: int) -> StudentStaffOut:
    if actor.employee_role not in _ADMIN_ROLES:
        raise NotFoundError("资源不存在")
    profile = require_student_visible(db, actor, student_id)
    user = db.get(SysUser, profile.user_id)
    advisor = db.get(SysUser, profile.advisor_user_id) if profile.advisor_user_id else None

    enrollments = student_repo.list_enrollments(db, profile.id)
    names = student_repo.get_project_names(db, [e.course_project_id for e in enrollments])

    return StudentStaffOut(
        id=str(profile.id),
        userId=str(profile.user_id),
        realName=user.real_name if user else "",
        mobile=user.username if user else "",
        gender=profile.gender,
        city=profile.city,
        education=profile.education,
        dateOfBirth=profile.date_of_birth,
        enrollmentDate=profile.enrollment_date,
        status=profile.status,
        classInfo=_class_brief(db, profile.class_id),
        advisor=StudentAdvisorBrief(
            id=str(advisor.id), realName=advisor.real_name,
            contactInfo=advisor.contact_info) if advisor else None,
        enrollments=[StudentEnrollmentItem(
            id=str(e.id), courseProjectId=str(e.course_project_id),
            projectName=names.get(e.course_project_id, ""), status=e.status, version=e.version,
        ) for e in enrollments],
        version=profile.version,
    )


# =============================================================
# API049 调班/换顾问/学籍状态
# =============================================================
@idempotent("employee_student_service.update_relationship")
def update_relationship(db: Session, actor: SysUser, student_id: int,
                        data: RelationshipUpdateIn) -> dict:
    profile = require_student_visible(db, actor, student_id)
    if actor.employee_role != "ADMIN" and not _is_head_of(db, actor, profile.dept_id):
        raise NotFoundError("资源不存在")
    if profile.version != data.expected_version:
        raise VersionConflictError(profile.version)

    # Only pending work still owned by a relationship being replaced blocks handover.
    old_handlers=set()
    if data.class_id is not None and data.class_id!=profile.class_id and profile.class_id:
        old_class=db.get(SysClass,profile.class_id)
        if old_class and old_class.head_teacher_id:old_handlers.add(old_class.head_teacher_id)
    if data.advisor_user_id is not None and data.advisor_user_id!=profile.advisor_user_id and profile.advisor_user_id:old_handlers.add(profile.advisor_user_id)
    if old_handlers and db.scalar(select(StudentAdminService.id).where(StudentAdminService.student_profile_id==profile.id,StudentAdminService.status=="PENDING",StudentAdminService.assignee_user_id.in_(old_handlers)).limit(1)) is not None:
        raise PendingRequestsRequireReassignError()

    if data.class_id is not None:
        cls = db.get(SysClass, data.class_id)
        if cls is None:
            raise InvalidRequestError("班级不存在")
        if cls.dept_id != profile.dept_id:
            raise DepartmentMismatchError("目标班级与学生所属部门不一致")
        profile.class_id = cls.id

    if data.advisor_user_id is not None:
        advisor = db.get(SysUser, data.advisor_user_id)
        if (advisor is None or advisor.status != "NORMAL"
                or advisor.employee_role not in _ADMIN_ROLES):
            raise InvalidRequestError("个人顾问无效")
        if advisor.employee_role != "ADMIN" and advisor.dept_id != profile.dept_id:
            raise DepartmentMismatchError("顾问与学生所属部门不一致")
        profile.advisor_user_id = advisor.id

    if data.status is not None:
        profile.status = data.status

    profile.version += 1
    db.flush()
    logger.info("M3 学生关系调整 profile=%s actor=%s reason=%s",
                profile.id, actor.id, data.reason)
    return {
        "id": str(profile.id),
        "classId": str(profile.class_id) if profile.class_id else None,
        "advisorUserId": str(profile.advisor_user_id) if profile.advisor_user_id else None,
        "status": profile.status,
        "version": profile.version,
    }


# =============================================================
# API044 新增升学项目关联
# =============================================================
@idempotent("employee_student_service.add_enrollment")
def add_enrollment(db: Session, actor: SysUser, student_id: int,
                   data: EnrollmentCreateIn) -> dict:
    profile = require_student_visible(db, actor, student_id)
    _require_student_manager(db, actor, profile)
    if profile.version != data.expected_student_version:
        raise VersionConflictError(profile.version)

    project = db.get(CourseProject, data.course_project_id)
    if project is None:
        raise InvalidRequestError("课程项目不存在")

    # 幂等：同一 request_key 已写 UPSELL_INTEREST → 返回既有
    existing_fu = lead_repo.get_follow_up_by_request_key(db, data.request_key)
    if existing_fu is not None and existing_fu.follow_up_type == "UPSELL_INTEREST":
        enrollment = db.scalar(select(StudentCourseEnrollment).where(
            StudentCourseEnrollment.student_profile_id == profile.id,
            StudentCourseEnrollment.course_project_id == project.id))
        return {
            "enrollment_id": str(enrollment.id) if enrollment else None,
            "status": enrollment.status if enrollment else None,
            "student_version": profile.version,
        }

    enrollment = db.scalar(select(StudentCourseEnrollment).where(
        StudentCourseEnrollment.student_profile_id == profile.id,
        StudentCourseEnrollment.course_project_id == project.id))

    if enrollment is not None:
        if enrollment.status != "WITHDRAWN":
            raise EnrollmentStatusConflictError("该学生已关联此项目")
        enrollment.status = "ENROLLED"
        enrollment.ended_at = None
        enrollment.version += 1
    else:
        enrollment = StudentCourseEnrollment(
            student_profile_id=profile.id,
            course_project_id=project.id,
            status="ENROLLED",
            enrolled_at=data.enrolled_at or datetime.now(timezone.utc),
            version=1,
        )
        db.add(enrollment)
    db.flush()

    # 同时写 UPSELL_INTEREST 跟进（来源客户存在时）
    if profile.converted_lead_id:
        lead = db.get(CrmLead, profile.converted_lead_id)
        if lead is not None:
            db.add(CrmFollowUp(
                lead_id=lead.id,
                actor_user_id=actor.id,
                follow_up_type="UPSELL_INTEREST",
                content=f"为学生新增升学项目：{project.name}",
                request_key=data.request_key,
                details={"course_project_id": project.id,
                         "student_profile_id": profile.id},
            ))

    profile.version += 1
    db.flush()
    return {
        "enrollment_id": str(enrollment.id),
        "status": enrollment.status,
        "student_version": profile.version,
    }


# =============================================================
# API045 结束/恢复项目关联
# =============================================================
@idempotent("employee_student_service.update_enrollment")
def update_enrollment(db: Session, actor: SysUser, student_id: int, enrollment_id: int,
                      data: EnrollmentUpdateIn) -> dict:
    profile = require_student_visible(db, actor, student_id)
    _require_student_manager(db, actor, profile)

    enrollment = db.get(StudentCourseEnrollment, enrollment_id)
    if enrollment is None or enrollment.student_profile_id != profile.id:
        raise NotFoundError("资源不存在")
    if enrollment.version != data.expected_version:
        raise VersionConflictError(enrollment.version)

    if data.status == "ENROLLED":
        if enrollment.status != "WITHDRAWN":
            raise EnrollmentStatusConflictError("仅已退出的关联可恢复")
        enrollment.ended_at = None
    else:
        enrollment.ended_at = data.ended_at or datetime.now(timezone.utc)

    enrollment.status = data.status
    enrollment.version += 1
    db.flush()
    logger.info("M3 课程关联变更 enrollment=%s actor=%s status=%s reason=%s",
                enrollment.id, actor.id, data.status, data.reason)
    return {"id": str(enrollment.id), "status": enrollment.status,
            "version": enrollment.version}


# =============================================================
# API094 员工授权查询教务日程
# =============================================================
def _schedule_to_dto(s) -> ScheduleDTO:
    return ScheduleDTO(
        id=str(s.id), scheduleType=s.schedule_type, title=s.title,
        description=s.description, startAt=s.start_at, endAt=s.end_at,
        location=s.location, remindAt=s.remind_at, status=s.status,
        dataSource=s.data_source, reminderRevision=s.reminder_revision,
        version=s.version,
    )


def list_student_schedules(db: Session, actor: SysUser, student_id: int, *,
                           start_at=None, end_at=None, schedule_type: str | None = None,
                           page: int = 1, page_size: int = 20):
    if actor.employee_role not in _ADMIN_ROLES:
        raise NotFoundError("资源不存在")
    profile = require_student_visible(db, actor, student_id)
    items, total = academic_repo.list_schedules(
        db, profile.id, start_at=start_at, end_at=end_at,
        schedule_type=schedule_type, page=page, page_size=page_size)
    return [_schedule_to_dto(s) for s in items], total
