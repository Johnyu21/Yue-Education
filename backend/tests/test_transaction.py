"""
事务验收测试（M1 补充）

核心验证：**多表操作中途失败，前面的改动全部回滚**（不留脏数据）。
用"签约转学生"这个真实场景测试。
运行：pytest tests/test_transaction.py -v
"""
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.errors import DuplicateResourceError, StateConflictError
from app.core.security import hash_password
from app.core.transaction import with_business_transaction
from app.models.student import StudentProfile
from app.models.user import SysUser
from app.models.lead import CrmLead

Engine = create_engine(settings.database_url)
Session = sessionmaker(bind=Engine)


@pytest.fixture
def db():
    s = Session()
    yield s
    s.close()


@pytest.fixture
def setup_lead(db):
    """造一条待转化的线索 + 一个项目。"""
    # 清理顺序：先删引用方，再删被引用方
    db.execute(text("""
        DELETE FROM student_course_enrollment WHERE student_profile_id IN (
            SELECT id FROM student_profile WHERE user_id IN (
                SELECT id FROM sys_user WHERE username LIKE 'tx_%'))
    """))
    db.execute(text("DELETE FROM student_profile WHERE user_id IN (SELECT id FROM sys_user WHERE username LIKE 'tx_%')"))
    db.execute(text("DELETE FROM sys_user WHERE username LIKE 'tx_%'"))
    db.execute(text("DELETE FROM crm_lead WHERE mobile LIKE '198%'"))
    db.execute(text("DELETE FROM course_project WHERE code='TX_PROJ'"))
    db.execute(text("INSERT INTO sys_department(code,name) VALUES ('TXD','事务测试部') ON CONFLICT (code) DO NOTHING"))
    dept = db.scalar(text("SELECT id FROM sys_department WHERE code='TXD'"))
    db.execute(text("""
        INSERT INTO course_project(code,name,description) VALUES ('TX_PROJ','测试项目','xx')
    """))
    proj = db.scalar(text("SELECT id FROM course_project WHERE code='TX_PROJ'"))
    db.execute(text("""
        INSERT INTO crm_lead(name,mobile,source,status,dept_id,request_key)
        VALUES ('待转化','19800000001','WEBSITE','FOLLOWING',:d,gen_random_uuid())
    """), {"d": dept})
    lead_id = db.scalar(text("SELECT id FROM crm_lead WHERE mobile='19800000001'"))
    db.commit()
    return {"dept": dept, "proj": proj, "lead_id": lead_id}


def _count_users(db, like="tx_%"):
    return db.scalar(text("SELECT count(*) FROM sys_user WHERE username LIKE :l"), {"l": like})


# ==================== 测试 ====================

def test_成功时全部提交(db, setup_lead):
    """转学生成功：账号 + 档案 + 线索状态 + 跟进记录 全部落库"""
    with with_business_transaction(db):
        # 建账号（学生不能带 dept_id）
        db.execute(text("""
            INSERT INTO sys_user(username,password_hash,real_name,user_type)
            VALUES ('tx_stu1',:p,'学生1','STUDENT')
        """), {"p": hash_password("pw12345678")})
        uid = db.scalar(text("SELECT id FROM sys_user WHERE username='tx_stu1'"))
        # 建档案
        db.execute(text("""
            INSERT INTO student_profile(user_id,converted_lead_id,advisor_user_id,dept_id)
            VALUES (:u,:l,NULL,:d)
        """), {"u": uid, "l": setup_lead["lead_id"], "d": setup_lead["dept"]})
        # 建课程关联
        pid = db.scalar(text("SELECT id FROM student_profile WHERE user_id=:u"), {"u": uid})
        db.execute(text("""
            INSERT INTO student_course_enrollment(student_profile_id,course_project_id)
            VALUES (:p,:c)
        """), {"p": pid, "c": setup_lead["proj"]})
        # 改线索状态
        db.execute(text("UPDATE crm_lead SET status='SIGNED', signed_at=now() WHERE id=:i"),
                   {"i": setup_lead["lead_id"]})

    # 全部落库 ✅
    assert _count_users(db, "tx_stu1") == 1
    assert db.scalar(text("SELECT count(*) FROM student_profile WHERE user_id IN (SELECT id FROM sys_user WHERE username='tx_stu1')")) == 1
    assert db.scalar(text("SELECT status FROM crm_lead WHERE id=:i"), {"i": setup_lead["lead_id"]}) == "SIGNED"


def test_中途失败全部回滚(db, setup_lead):
    """⭐ 核心：第 3 步失败 → 前 2 步也撤销，一行不留"""
    before_users = _count_users(db, "tx_%")

    with pytest.raises(Exception):
        with with_business_transaction(db):
            # ① 建账号（成功）
            db.execute(text("""
                INSERT INTO sys_user(username,password_hash,real_name,user_type)
                VALUES ('tx_stu2',:p,'学生2','STUDENT')
            """), {"p": hash_password("pw12345678")})
            uid = db.scalar(text("SELECT id FROM sys_user WHERE username='tx_stu2'"))
            # ② 建档案（成功）
            db.execute(text("""
                INSERT INTO student_profile(user_id,converted_lead_id,dept_id)
                VALUES (:u,:l,:d)
            """), {"u": uid, "l": setup_lead["lead_id"], "d": setup_lead["dept"]})
            # ③ 故意制造失败（引用不存在的项目 → 外键错误）
            pid = db.scalar(text("SELECT id FROM student_profile WHERE user_id=:u"), {"u": uid})
            db.execute(text("""
                INSERT INTO student_course_enrollment(student_profile_id,course_project_id)
                VALUES (:p, 999999)
            """), {"p": pid})

    # ①② 应该被回滚 → 账号数没变
    assert _count_users(db, "tx_%") == before_users, "失败后不该留下账号！"
    assert _count_users(db, "tx_stu2") == 0, "失败后不该留下 tx_stu2！"


def test_唯一冲突翻译成业务异常(db, setup_lead):
    """重复手机号 → 抛 DuplicateResourceError（不是 500）"""
    db.execute(text("""
        INSERT INTO sys_user(username,password_hash,real_name,user_type)
        VALUES ('tx_dup',:p,'重复','STUDENT')
    """), {"p": hash_password("pw12345678")})
    db.commit()

    with pytest.raises(DuplicateResourceError):
        with with_business_transaction(db):
            db.execute(text("""
                INSERT INTO sys_user(username,password_hash,real_name,user_type)
                VALUES ('tx_dup',:p,'重复2','STUDENT')
            """), {"p": hash_password("pw12345678")})


def test_业务规则冲突翻译(db, setup_lead):
    """违反 CHECK 约束（如学生带员工角色）→ StateConflictError"""
    with pytest.raises(StateConflictError):
        with with_business_transaction(db):
            db.execute(text("""
                INSERT INTO sys_user(username,password_hash,real_name,user_type,employee_role)
                VALUES ('tx_bad',:p,'错的','STUDENT','ADVISOR')
            """), {"p": hash_password("pw12345678")})


def test_回滚后session还能继续用(db, setup_lead):
    """回滚不会让 Session 变成废的，之后还能正常操作"""
    with pytest.raises(Exception):
        with with_business_transaction(db):
            db.execute(text("INSERT INTO sys_user(username,password_hash,real_name,user_type) VALUES ('tx_x',:p,'x','STUDENT')"),
                       {"p": hash_password("pw12345678")})
            db.execute(text("INSERT INTO sys_user(username,password_hash,real_name,user_type) VALUES ('tx_x',:p,'x','STUDENT')"),
                       {"p": hash_password("pw12345678")})   # 重复 → 失败

    # Session 仍可用
    assert _count_users(db, "tx_x") == 0
    with with_business_transaction(db):
        db.execute(text("INSERT INTO sys_user(username,password_hash,real_name,user_type) VALUES ('tx_ok',:p,'ok','STUDENT')"),
                   {"p": hash_password("pw12345678")})
    assert _count_users(db, "tx_ok") == 1
