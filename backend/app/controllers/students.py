"""
学生管理 —— 档案 / 课程关联 / 成绩 / 日程 / 申请进度

⚠️ 实现要求：
  1. 统一响应：return ok(data)；报错抛 app.core.errors 里的异常类
  2. 需登录：Depends(require_password_changed)
  3. 查数据：用 build_scope(db, user, purpose) 限制范围（M1-05）
  4. 多表写：用 with_business_transaction（M1-S1）
  5. AI 调用**放事务外**（M1-S1）
  6. 每个接口下有 API 编号注释
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_password_changed
from app.core.errors import NotImplementedYetError
from app.core.responses import ok
from app.db.session import get_db
from app.models.user import SysUser

router = APIRouter(tags=["学生管理"])


def _todo(api: str, who: str = "M3/M4"):
    raise NotImplementedYetError(f"{api} 尚未实现（负责人：{who}）")


@router.post("/api/v1/employees/students/{student_id}/enrollments")
def add_enrollment(student_id: int, user: SysUser = Depends(require_password_changed),
                   db: Session = Depends(get_db)):
    """API044 添加课程关联"""
    _todo("API044")


@router.patch("/api/v1/employees/students/{student_id}/enrollments/{enrollment_id}")
def update_enrollment(student_id: int, enrollment_id: int,
                      user: SysUser = Depends(require_password_changed),
                      db: Session = Depends(get_db)):
    """API045 修改课程关联"""
    _todo("API045")


@router.get("/api/v1/me/student-profile")
def my_profile(user: SysUser = Depends(require_password_changed),
               db: Session = Depends(get_db)):
    """API046 我的档案"""
    _todo("API046")


@router.get("/api/v1/employees/students")
def list_students(user: SysUser = Depends(require_password_changed),
                  db: Session = Depends(get_db)):
    """API047 学生列表（员工用）

    ⚠️ 本条在任务卡里没有负责人，需团队确认归属
    """
    _todo("API047", "未认领")


@router.get("/api/v1/employees/students/{student_id}")
def get_student(student_id: int,
                user: SysUser = Depends(require_password_changed),
                db: Session = Depends(get_db)):
    """API048 学生详情（员工用）

    ⚠️ 本条在任务卡里没有负责人，需团队确认归属
    """
    _todo("API048", "未认领")


@router.patch("/api/v1/employees/students/{student_id}/relationships")
def update_student_relationship(student_id: int,
                                user: SysUser = Depends(require_password_changed),
                                db: Session = Depends(get_db)):
    """API049 修改学生关系（顾问/班级）"""
    _todo("API049")


# ---------------- 员工助手 / 语音 ----------------


@router.get("/api/v1/me/scores")
def my_scores(user: SysUser = Depends(require_password_changed),
              db: Session = Depends(get_db)):
    """API073 我的成绩（只读）"""
    _todo("API073")


@router.get("/api/v1/employees/students/{student_id}/scores")
def student_scores(student_id: int,
                   user: SysUser = Depends(require_password_changed),
                   db: Session = Depends(get_db)):
    """API074 员工查看某学生成绩（⚠️ 按 scope 限制范围）"""
    _todo("API074", "M4")


@router.get("/api/v1/me/schedules")
def my_schedules(user: SysUser = Depends(require_password_changed),
                 db: Session = Depends(get_db)):
    """API076 我的日程（DDL / 考试）"""
    _todo("API076")


@router.put("/api/v1/me/schedules/{schedule_id}/reminder")
def set_reminder(schedule_id: int,
                 user: SysUser = Depends(require_password_changed),
                 db: Session = Depends(get_db)):
    """API077 设置提醒（写 remind_at，不能晚于日程本身）"""
    _todo("API077")


@router.get("/api/v1/application-cases")
def my_application_cases(user: SysUser = Depends(require_password_changed),
                         db: Session = Depends(get_db)):
    """API078 我的申请进度"""
    _todo("API078")


@router.get("/api/v1/application-cases/{case_no}/timeline")
def application_timeline(case_no: str,
                         user: SysUser = Depends(require_password_changed),
                         db: Session = Depends(get_db)):
    """API079 进度时间线（按 sequence_no 排）"""
    _todo("API079")


@router.post("/api/v1/employees/application-cases")
def create_application_case(user: SysUser = Depends(require_password_changed),
                            db: Session = Depends(get_db)):
    """API080 创建申请单"""
    _todo("API080")


@router.post("/api/v1/employees/application-cases/{case_no}/events")
def append_application_event(case_no: str,
                             user: SysUser = Depends(require_password_changed),
                             db: Session = Depends(get_db)):
    """API081 追加申请进度（sequence_no 递增，不覆盖历史）"""
    _todo("API081")


# ---------------- 员工日报 ----------------


@router.get("/api/v1/me/initial-assessment")
def my_initial_assessment(user: SysUser = Depends(require_password_changed),
                          db: Session = Depends(get_db)):
    """API093 入学评估"""
    _todo("API093")


@router.get("/api/v1/employees/students/{student_id}/schedules")
def student_schedules(student_id: int,
                      user: SysUser = Depends(require_password_changed),
                      db: Session = Depends(get_db)):
    """API094 员工查看某学生日程（⚠️ 按 scope 限制范围）

    ⚠️ 本条在任务卡里没有负责人，需团队确认归属
    """
    _todo("API094", "未认领")


@router.post("/api/v1/me/upgrade-interests")
def create_upgrade_interest(user: SysUser = Depends(require_password_changed),
                            db: Session = Depends(get_db)):
    """API095 升学意向（增值转化线索）"""
    _todo("API095")


# ---------------- 心理（⚠️ 最敏感）----------------

