"""
M4 测试共享 fixture（学生 + 顾问 + 班主任 + 部门 + 班级）
"""
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.security import hash_password
from app.models.user import SysUser

Engine = create_engine(settings.database_url)
Session = sessionmaker(bind=Engine)

_P = hash_password("pw12345678")


def _cleanup(db):
    db.execute(text("DELETE FROM notification WHERE recipient_user_id IN (SELECT id FROM sys_user WHERE username LIKE 'm4_%')"))
    db.execute(text("DELETE FROM student_psych_alert WHERE student_profile_id IN (SELECT id FROM student_profile WHERE user_id IN (SELECT id FROM sys_user WHERE username LIKE 'm4_%'))"))
    db.execute(text("DELETE FROM student_psych_profile WHERE student_profile_id IN (SELECT id FROM student_profile WHERE user_id IN (SELECT id FROM sys_user WHERE username LIKE 'm4_%'))"))
    db.execute(text("DELETE FROM student_feedback_ticket WHERE student_profile_id IN (SELECT id FROM student_profile WHERE user_id IN (SELECT id FROM sys_user WHERE username LIKE 'm4_%'))"))
    db.execute(text("DELETE FROM student_admin_service WHERE student_profile_id IN (SELECT id FROM student_profile WHERE user_id IN (SELECT id FROM sys_user WHERE username LIKE 'm4_%'))"))
    db.execute(text("DELETE FROM student_application_progress WHERE student_profile_id IN (SELECT id FROM student_profile WHERE user_id IN (SELECT id FROM sys_user WHERE username LIKE 'm4_%'))"))
    db.execute(text("DELETE FROM student_score WHERE student_profile_id IN (SELECT id FROM student_profile WHERE user_id IN (SELECT id FROM sys_user WHERE username LIKE 'm4_%'))"))
    db.execute(text("DELETE FROM student_academic_schedule WHERE student_profile_id IN (SELECT id FROM student_profile WHERE user_id IN (SELECT id FROM sys_user WHERE username LIKE 'm4_%'))"))
    db.execute(text("DELETE FROM student_course_enrollment WHERE student_profile_id IN (SELECT id FROM student_profile WHERE user_id IN (SELECT id FROM sys_user WHERE username LIKE 'm4_%'))"))
    db.execute(text("DELETE FROM student_profile WHERE user_id IN (SELECT id FROM sys_user WHERE username LIKE 'm4_%')"))
    db.execute(text("DELETE FROM sys_class WHERE code LIKE 'M4%'"))
    db.execute(text("DELETE FROM sys_user WHERE username LIKE 'm4_%'"))
    db.execute(text("DELETE FROM sys_department WHERE code LIKE 'M4%'"))


@pytest.fixture
def m4_db():
    s = Session()
    yield s
    s.close()


@pytest.fixture
def m4_env(m4_db):
    db = m4_db
    _cleanup(db)

    db.execute(text("INSERT INTO sys_department(code,name) VALUES ('M4D','M4测试部')"))
    dept = db.scalar(text("SELECT id FROM sys_department WHERE code='M4D'"))

    db.execute(text("INSERT INTO sys_user(username,password_hash,real_name,user_type,employee_role,dept_id) "
                    "VALUES ('m4_advisor',:p,'顾问甲','EMPLOYEE','ADVISOR',:d)"), {"p": _P, "d": dept})
    advisor = db.scalar(text("SELECT id FROM sys_user WHERE username='m4_advisor'"))

    db.execute(text("INSERT INTO sys_class(code,name,dept_id,head_teacher_id) VALUES ('M4C','M4测试班',:d,:a)"),
               {"d": dept, "a": advisor})
    cls = db.scalar(text("SELECT id FROM sys_class WHERE code='M4C'"))

    db.execute(text("INSERT INTO sys_user(username,password_hash,real_name,user_type) "
                    "VALUES ('m4_stu',:p,'学生甲','STUDENT')"), {"p": _P})
    stu = db.scalar(text("SELECT id FROM sys_user WHERE username='m4_stu'"))

    db.execute(text("INSERT INTO student_profile(user_id,advisor_user_id,dept_id,class_id) "
                    "VALUES (:u,:a,:d,:c)"), {"u": stu, "a": advisor, "d": dept, "c": cls})
    prof = db.scalar(text("SELECT id FROM student_profile WHERE user_id=:u"), {"u": stu})
    db.commit()

    yield {"dept": dept, "advisor": advisor, "cls": cls, "student_user": stu, "profile": prof}

    _cleanup(db)
    db.commit()


@pytest.fixture
def student(m4_db, m4_env):
    return m4_db.get(SysUser, m4_env["student_user"])


@pytest.fixture
def advisor(m4_db, m4_env):
    return m4_db.get(SysUser, m4_env["advisor"])
