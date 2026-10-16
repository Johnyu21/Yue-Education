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


# =============================================================
# M2（访客客服与客户研判）测试基座
#
# ⚠️ 安全护栏：M2 测试会**破坏性**清理 m2/13700 前缀的数据，
#    必须先确认当前库不是 Dify 自身库或系统库，否则直接失败（不是跳过）。
# =============================================================

_M2_MOBILE_PREFIX = "13700"          # M2 测试客户手机号前缀（11 位）
_M2_MOBILE_LIKE = "13700%"


@pytest.fixture(scope="session", autouse=True)
def m2_database_guard():
    """禁止在 dify/postgres 等库上运行任何测试（防误伤 Dify 数据）。"""
    name = (settings.postgres_db or "").strip().lower()
    if name in {"dify", "dify_plugin", "postgres", "template0", "template1"}:
        pytest.fail(
            f"拒绝在库 {name!r} 上运行测试：该库是 Dify 自身/系统库，"
            "请把 POSTGRES_DB 指向独立业务库（如 education）")


def _m2_cleanup(db):
    """清理 M2 测试数据（按**精确前缀**，顺序必须满足外键依赖）。

    ⚠️ 前缀务必与 `scripts/seed_m2.py` 的种子数据区分：
       种子项目 code = `M2_SEED_*`、活动 title = `M2开放日*`，
       若这里用宽泛的 `LIKE 'M2%'` 会把种子数据一起删掉。
       测试约定：项目 `M2P*` / 活动 `M2活动*` / 部门 `M2D*` / 班级 `M2C*` / 账号 `m2_*`。

    依赖链：event_lecture/course_project/sys_class 都引用 sys_user，
    因此必须先删业务表、再删用户，最后删部门（部门还被 head_user_id 引用）。
    """
    users = "SELECT id FROM sys_user WHERE username LIKE 'm2\\_%' ESCAPE '\\'"
    profiles = f"SELECT id FROM student_profile WHERE user_id IN ({users})"
    leads = f"SELECT id FROM crm_lead WHERE mobile LIKE '{_M2_MOBILE_LIKE}'"
    events = "SELECT id FROM event_lecture WHERE title LIKE 'M2活动%'"

    # ① 引用方（报名 → 通知 → 跟进 → 客户）
    db.execute(text(
        f"DELETE FROM event_registration WHERE student_profile_id IN ({profiles}) "
        f"OR lead_id IN ({leads}) OR event_id IN ({events})"))
    db.execute(text(f"DELETE FROM notification WHERE recipient_user_id IN ({users})"))
    db.execute(text(f"DELETE FROM crm_follow_up WHERE lead_id IN ({leads})"))
    db.execute(text(f"DELETE FROM crm_lead WHERE id IN ({leads})"))

    # ② 学生业务表 → 学生档案
    for table in ("student_psych_alert", "student_psych_profile",
                  "student_feedback_ticket", "student_admin_service",
                  "student_application_progress", "student_score",
                  "student_academic_schedule", "student_course_enrollment"):
        db.execute(text(f"DELETE FROM {table} WHERE student_profile_id IN ({profiles})"))
    db.execute(text(f"DELETE FROM student_profile WHERE user_id IN ({users})"))

    # ③ 引用 sys_user 的业务表（必须在删用户之前）
    db.execute(text(f"DELETE FROM event_lecture WHERE id IN ({events})"))
    db.execute(text("DELETE FROM course_project WHERE code LIKE 'M2P%'"))
    db.execute(text("UPDATE sys_department SET head_user_id=NULL WHERE code LIKE 'M2D%'"))
    db.execute(text("DELETE FROM sys_class WHERE code LIKE 'M2C%'"))

    # ④ 最后才是账号与部门
    db.execute(text(f"DELETE FROM sys_user WHERE id IN ({users})"))
    db.execute(text("DELETE FROM sys_department WHERE code LIKE 'M2D%'"))


_M2_RULES_APPROVED = (
    '{"criteria":[{"field":"education","op":"IN","values":["本科","硕士"],'
    '"label":"学历要求"}],'
    '"scoring":[{"field":"education","weights":{"大专":20,"本科":30,"硕士":40}}]}'
)


def _m2_make_user(db, username, role, dept):
    db.execute(text(
        "INSERT INTO sys_user(username,password_hash,real_name,user_type,employee_role,dept_id)"
        " VALUES (:u,:p,:u,'EMPLOYEE',:r,:d)"),
        {"u": username, "p": _P, "r": role, "d": dept})
    return db.scalar(text("SELECT id FROM sys_user WHERE username=:u"), {"u": username})


@pytest.fixture
def m2_db():
    s = Session()
    yield s
    s.close()


@pytest.fixture
def m2_env(m2_db):
    """M2 环境：部门 + 主管/顾问 + 3 个项目（已审规则 / 未审规则 / 无默认部门）+ 1 个开放活动。"""
    db = m2_db
    _m2_cleanup(db)
    db.commit()

    db.execute(text("INSERT INTO sys_department(code,name) VALUES ('M2D','M2测试部')"))
    dept = db.scalar(text("SELECT id FROM sys_department WHERE code='M2D'"))

    advisor = _m2_make_user(db, "m2_advisor", "ADVISOR", dept)
    head = _m2_make_user(db, "m2_head", "SENIOR_ADVISOR", dept)
    db.execute(text("UPDATE sys_department SET head_user_id=:h WHERE id=:d"),
               {"h": head, "d": dept})

    db.execute(text("""
        INSERT INTO course_project(code,name,description,is_published,default_dept_id,
                                   admission_rules,rule_version,rule_approved_at,
                                   rule_approved_by,version)
        VALUES ('M2P_OK','M2项目-已审规则','冒烟',true,:d,CAST(:r AS jsonb),'v1',now(),:by,1)
    """), {"d": dept, "r": _M2_RULES_APPROVED, "by": head})
    db.execute(text("""
        INSERT INTO course_project(code,name,description,is_published,default_dept_id,
                                   admission_rules,rule_version,version)
        VALUES ('M2P_RAW','M2项目-未审规则','冒烟',true,:d,CAST(:r AS jsonb),'v1',1)
    """), {"d": dept, "r": _M2_RULES_APPROVED})
    db.execute(text("""
        INSERT INTO course_project(code,name,description,is_published,default_dept_id,version)
        VALUES ('M2P_NODEPT','M2项目-无默认部门','冒烟',true,NULL,1)
    """))
    db.execute(text("""
        INSERT INTO course_project(code,name,description,is_published,default_dept_id,version)
        VALUES ('M2P_DRAFT','M2项目-未发布草稿','冒烟',false,:d,1)
    """), {"d": dept})

    db.execute(text("""
        INSERT INTO event_lecture(title,organizer_user_id,host_department_id,description,
                                  start_at,end_at,signup_deadline,capacity,status,version)
        VALUES ('M2活动-容量2',:o,:d,'冒烟',now()+interval '5 day',
                now()+interval '5 day 2 hour',now()+interval '4 day',2,'OPEN',1)
    """), {"o": advisor, "d": dept})
    db.execute(text("""
        INSERT INTO event_lecture(title,organizer_user_id,host_department_id,description,
                                  start_at,end_at,signup_deadline,capacity,status,version)
        VALUES ('M2活动-容量1',:o,:d,'冒烟',now()+interval '5 day',
                now()+interval '5 day 2 hour',now()+interval '4 day',1,'OPEN',1)
    """), {"o": advisor, "d": dept})
    db.commit()

    ids = {}
    for code in ("M2P_OK", "M2P_RAW", "M2P_NODEPT", "M2P_DRAFT"):
        ids[code] = db.scalar(text("SELECT id FROM course_project WHERE code=:c"), {"c": code})
    ids["event2"] = db.scalar(text("SELECT id FROM event_lecture WHERE title='M2活动-容量2'"))
    ids["event1"] = db.scalar(text("SELECT id FROM event_lecture WHERE title='M2活动-容量1'"))
    ids.update({"dept": dept, "advisor": advisor, "head": head})

    yield ids

    _m2_cleanup(db)
    db.commit()


@pytest.fixture
def m2_student(m2_db, m2_env):
    """M2 学生账号 + 档案（用于报名/取消的身份绑定用例）。"""
    db = m2_db
    db.execute(text(
        "INSERT INTO sys_user(username,password_hash,real_name,user_type)"
        " VALUES ('m2_student',:p,'M2学生','STUDENT')"), {"p": _P})
    user_id = db.scalar(text("SELECT id FROM sys_user WHERE username='m2_student'"))
    db.execute(text(
        "INSERT INTO student_profile(user_id,advisor_user_id,dept_id) VALUES (:u,:a,:d)"),
        {"u": user_id, "a": m2_env["advisor"], "d": m2_env["dept"]})
    profile_id = db.scalar(text("SELECT id FROM student_profile WHERE user_id=:u"), {"u": user_id})
    db.commit()
    return {"user": db.get(SysUser, user_id), "user_id": user_id, "profile_id": profile_id}


def m2_mobile(n: int) -> str:
    """生成 M2 测试手机号（13700 + 6 位），保证可被清理。"""
    return f"{_M2_MOBILE_PREFIX}{n:06d}"
