"""
学生管理 —— 档案 / 课程关联 / 成绩 / 日程 / 申请进度

M4：学生自助（档案/成绩/日程/进度查询/升学意向）
M3：员工学生管理（列表/详情/关系/升学项目/进度登记/员工查日程）
"""
from pydantic import AwareDatetime as datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import require_password_changed
from app.core.responses import ok
from app.core.transaction import with_business_transaction
from app.db.session import get_db
from app.models.user import SysUser
from app.schemas.application import ApplicationAdvanceIn, ApplicationCreateIn
from app.schemas.common import paged
from app.schemas.student import (
    EnrollmentCreateIn,
    EnrollmentUpdateIn,
    RelationshipUpdateIn,
    ReminderRequest,
    UpgradeInterestRequest,
)
from app.services import (
    academic_service,
    employee_student_service,
    progress_service,
    student_service,
)

router = APIRouter(tags=["学生管理"])


# =============================================================
# M3：升学项目关联 / 员工学生管理
# =============================================================
@router.post("/api/v1/employees/students/{student_id}/enrollments", status_code=201)
def add_enrollment(student_id: int, data: EnrollmentCreateIn,
                   user: SysUser = Depends(require_password_changed),
                   db: Session = Depends(get_db)):
    """API044 添加/恢复升学项目关联（同时写 UPSELL_INTEREST 跟进）"""
    with with_business_transaction(db):
        result = employee_student_service.add_enrollment(db, user, student_id, data)
    return ok(result)


@router.patch("/api/v1/employees/students/{student_id}/enrollments/{enrollment_id}")
def update_enrollment(student_id: int, enrollment_id: int, data: EnrollmentUpdateIn,
                      user: SysUser = Depends(require_password_changed),
                      db: Session = Depends(get_db)):
    """API045 结束/恢复项目关联（乐观锁）"""
    with with_business_transaction(db):
        result = employee_student_service.update_enrollment(
            db, user, student_id, enrollment_id, data)
    return ok(result)


# =============================================================
# M4：学生本人档案
# =============================================================
@router.get("/api/v1/me/student-profile")
def my_profile(user: SysUser = Depends(require_password_changed),
               db: Session = Depends(get_db)):
    """API046 我的档案"""
    dto = student_service.get_self_overview(db, user)
    return ok(dto.model_dump(mode="json"))


# =============================================================
# M3：员工学生列表 / 详情 / 调班换顾问
# =============================================================
@router.get("/api/v1/employees/students")
def list_students(user: SysUser = Depends(require_password_changed),
                  db: Session = Depends(get_db),
                  page: int = Query(1, ge=1),
                  page_size: int = Query(20, ge=1, le=100),
                  class_id: int | None = Query(None),
                  keyword: str | None = Query(None, max_length=80)):
    """API047 员工学生列表（班主任本班/顾问本人/主管部门/管理员）"""
    items, total = employee_student_service.list_students(
        db, user, class_id=class_id, keyword=keyword,
        page=page, page_size=page_size)
    return ok(paged([i.model_dump(mode="json") for i in items], page, page_size, total))


@router.get("/api/v1/employees/students/{student_id}")
def get_student(student_id: int,
                user: SysUser = Depends(require_password_changed),
                db: Session = Depends(get_db)):
    """API048 员工学生基础详情（不含投诉/心理内容）"""
    dto = employee_student_service.get_student(db, user, student_id)
    return ok(dto.model_dump(mode="json"))


@router.patch("/api/v1/employees/students/{student_id}/relationships")
def update_student_relationship(student_id: int, data: RelationshipUpdateIn,
                                user: SysUser = Depends(require_password_changed),
                                db: Session = Depends(get_db)):
    """API049 调班/换顾问/学籍状态（主管/管理员；有未审单须先转派）"""
    with with_business_transaction(db):
        result = employee_student_service.update_relationship(db, user, student_id, data)
    return ok(result)


# =============================================================
# M4：成绩 / 日程 / 进度
# =============================================================
@router.get("/api/v1/me/scores")
def my_scores(user: SysUser = Depends(require_password_changed),
              db: Session = Depends(get_db),
              page: int = Query(1, ge=1),
              page_size: int = Query(20, ge=1, le=100),
              enrollment_id: int | None = Query(None),
              subject: str | None = Query(None)):
    """API073 我的成绩（只读）"""
    items, total = academic_service.list_scores(
        db, user, enrollment_id=enrollment_id, subject=subject, page=page, page_size=page_size)
    return ok({"items": [i.model_dump(mode="json") for i in items],
               "page": page, "pageSize": page_size, "total": total})


@router.get("/api/v1/employees/students/{student_id}/scores")
def student_scores(student_id: int,
                   user: SysUser = Depends(require_password_changed),
                   db: Session = Depends(get_db),
                   page: int = Query(1, ge=1),
                   page_size: int = Query(20, ge=1, le=100),
                   enrollment_id: int | None = Query(None)):
    """API074 员工查看某学生成绩（按范围限制）"""
    items, total = academic_service.list_scores(
        db, user, student_id=student_id, enrollment_id=enrollment_id,
        page=page, page_size=page_size)
    return ok({"items": [i.model_dump(mode="json") for i in items],
               "page": page, "pageSize": page_size, "total": total})


@router.get("/api/v1/me/schedules")
def my_schedules(user: SysUser = Depends(require_password_changed),
                 db: Session = Depends(get_db),
                 page: int = Query(1, ge=1),
                 page_size: int = Query(20, ge=1, le=100),
                 start_at: datetime | None = Query(None),
                 end_at: datetime | None = Query(None),
                 schedule_type: str | None = Query(None)):
    """API076 我的日程（DDL / 考试）"""
    items, total = academic_service.list_schedules(
        db, user, start_at=start_at, end_at=end_at, schedule_type=schedule_type,
        page=page, page_size=page_size)
    return ok({"items": [i.model_dump(mode="json") for i in items],
               "page": page, "pageSize": page_size, "total": total})


@router.put("/api/v1/me/schedules/{schedule_id}/reminder")
def set_reminder(schedule_id: int, data: ReminderRequest,
                 user: SysUser = Depends(require_password_changed),
                 db: Session = Depends(get_db)):
    """API077 设置提醒（remind_at，不能晚于日程本身）"""
    with with_business_transaction(db):
        result = academic_service.set_reminder(db, user, schedule_id, data)
    return ok(result)


@router.get("/api/v1/application-cases")
def my_application_cases(user: SysUser = Depends(require_password_changed),
                         db: Session = Depends(get_db),
                         page: int = Query(1, ge=1),
                         page_size: int = Query(20, ge=1, le=100),
                         item_type: str | None = Query(None),
                         stage: str | None = Query(None)):
    """API078 我的申请进度"""
    items, total = academic_service.list_application_cases(
        db, user, item_type=item_type, stage=stage, page=page, page_size=page_size)
    return ok({"items": [i.model_dump(mode="json") for i in items],
               "page": page, "pageSize": page_size, "total": total})


@router.get("/api/v1/application-cases/{case_no}/timeline")
def application_timeline(case_no: str,
                         user: SysUser = Depends(require_password_changed),
                         db: Session = Depends(get_db),
                         page: int = Query(1, ge=1),
                         page_size: int = Query(20, ge=1, le=100)):
    """API079 进度时间线（按 sequence_no 排）"""
    items, total = academic_service.case_timeline(
        db, user, case_no, page=page, page_size=page_size)
    return ok({"items": [i.model_dump(mode="json") for i in items],
               "page": page, "pageSize": page_size, "total": total})


# =============================================================
# M3：申请进度登记（员工）
# =============================================================
@router.post("/api/v1/employees/application-cases", status_code=201)
def create_application_case(data: ApplicationCreateIn,
                            user: SysUser = Depends(require_password_changed),
                            db: Session = Depends(get_db)):
    """API080 人工建立内部跟踪事项（文书/院校/签证）"""
    with with_business_transaction(db):
        result = progress_service.create_case(db, user, data)
    return ok(result)


@router.post("/api/v1/employees/application-cases/{case_no}/events")
def append_application_event(case_no: str, data: ApplicationAdvanceIn,
                             user: SysUser = Depends(require_password_changed),
                             db: Session = Depends(get_db)):
    """API081 追加进度/补料说明（序号乐观锁；完成时双事件+通知）"""
    with with_business_transaction(db):
        result = progress_service.advance_case(db, user, case_no, data)
    return ok(result)


# =============================================================
# M4：签约前评估 / 升学意向
# =============================================================
@router.get("/api/v1/me/initial-assessment")
def my_initial_assessment(user: SysUser = Depends(require_password_changed),
                          db: Session = Depends(get_db)):
    """API093 签约前项目评估的学生可见摘要"""
    return ok(academic_service.get_initial_assessment(db, user))


# =============================================================
# M3：员工授权查询学生日程
# =============================================================
@router.get("/api/v1/employees/students/{student_id}/schedules")
def student_schedules(student_id: int,
                      user: SysUser = Depends(require_password_changed),
                      db: Session = Depends(get_db),
                      page: int = Query(1, ge=1),
                      page_size: int = Query(20, ge=1, le=100),
                      start_at: datetime | None = Query(None),
                      end_at: datetime | None = Query(None),
                      schedule_type: str | None = Query(None)):
    """API094 员工授权查询学生教务日程"""
    items, total = employee_student_service.list_student_schedules(
        db, user, student_id, start_at=start_at, end_at=end_at,
        schedule_type=schedule_type, page=page, page_size=page_size)
    return ok(paged([i.model_dump(mode="json") for i in items], page, page_size, total))


@router.post("/api/v1/me/upgrade-interests", status_code=201)
def create_upgrade_interest(data: UpgradeInterestRequest,
                            user: SysUser = Depends(require_password_changed),
                            db: Session = Depends(get_db)):
    """API095 升学意向（增值转化线索）"""
    with with_business_transaction(db):
        result = academic_service.create_upgrade_interest(db, user, data)
    return ok(result)
