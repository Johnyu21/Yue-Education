"""
M1-05 数据范围 Scope 验收测试

验收标准（M1 原文）：**2 部门、2 班、2 顾问矩阵测试**

测试场景：
  部门 A： 顾问A1（带线索 L1）、顾问A2（带线索 L2）、主管 HeadA
  部门 B： 顾问B1（带线索 L3）、主管 HeadB
  管理员： Admin（全域）
  学生：   Stu1（学生）、Stu2（同班/异班）

核心验证：**越权拿不到数据**（不是"前端藏起来"，是后端查不到）
运行：pytest tests/test_scope.py -v
"""
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.permissions import build_scope
from app.core.errors import NotFoundError
from app.core.security import hash_password
from app.models.lead import CrmLead
from app.models.user import SysUser


Engine = create_engine(settings.database_url)
Session = sessionmaker(bind=Engine)


@pytest.fixture(scope="module")
def fixture_data():
    """建一套测试数据：2 部门 / 2 顾问 / 2 线索 / 主管 / 管理员。"""
    with Session() as db:
        # 清理旧的测试数据（顺序：先解引用，再删）
        db.execute(text("DELETE FROM crm_lead WHERE mobile LIKE '199%'"))
        db.execute(text("UPDATE sys_department SET head_user_id=NULL WHERE code LIKE 'SC%'"))
        db.execute(text("DELETE FROM sys_user WHERE username LIKE 'sc_%'"))
        db.execute(text("DELETE FROM sys_department WHERE code LIKE 'SC%'"))
        db.commit()

        # 2 个部门
        db.execute(text("INSERT INTO sys_department(code,name) VALUES ('SCA','测试部门A'),('SCB','测试部门B')"))
        dept_a = db.scalar(text("SELECT id FROM sys_department WHERE code='SCA'"))
        dept_b = db.scalar(text("SELECT id FROM sys_department WHERE code='SCB'"))

        # 账号：4 员工 + 1 管理员 + 1 学生
        def mk_user(username, role, dept):
            db.execute(text("""
                INSERT INTO sys_user(username,password_hash,real_name,user_type,employee_role,dept_id)
                VALUES (:u,:p,:u,'EMPLOYEE',:r,:d)
            """), {"u": username, "p": hash_password("pw12345678"), "r": role, "d": dept})
            return db.scalar(text("SELECT id FROM sys_user WHERE username=:u"), {"u": username})

        a1 = mk_user("sc_a1", "ADVISOR", dept_a)
        a2 = mk_user("sc_a2", "ADVISOR", dept_a)
        b1 = mk_user("sc_b1", "ADVISOR", dept_b)
        head_a = mk_user("sc_heada", "ADVISOR", dept_a)   # 主管仍是顾问
        admin = mk_user("sc_admin", "ADMIN", dept_a)

        # 指定 A 部门主管（唯一事实源）
        db.execute(text("UPDATE sys_department SET head_user_id=:h WHERE id=:d"),
                   {"h": head_a, "d": dept_a})

        # 每人才一条线索
        def mk_lead(name, mobile, owner, dept):
            db.execute(text("""
                INSERT INTO crm_lead(name,mobile,source,status,owner_user_id,dept_id,request_key)
                VALUES (:n,:m,'WEBSITE','NEW',:o,:d,gen_random_uuid())
            """), {"n": name, "m": mobile, "o": owner, "d": dept})
            return db.scalar(text("SELECT id FROM crm_lead WHERE mobile=:m"), {"m": mobile})

        l1 = mk_lead("线索A1", "19900000001", a1, dept_a)
        l2 = mk_lead("线索A2", "19900000002", a2, dept_a)
        l3 = mk_lead("线索B1", "19900000003", b1, dept_b)

        db.commit()

    yield {"a1": a1, "a2": a2, "b1": b1, "head_a": head_a, "admin": admin,
           "l1": l1, "l2": l2, "l3": l3, "dept_a": dept_a, "dept_b": dept_b}

    # 清理
    with Session() as db:
        db.execute(text("DELETE FROM crm_lead WHERE mobile LIKE '199%'"))
        # 先解除"部门主管"引用，否则删用户会撞外键
        db.execute(text("UPDATE sys_department SET head_user_id=NULL WHERE code LIKE 'SC%'"))
        db.execute(text("DELETE FROM sys_user WHERE username LIKE 'sc_%'"))
        db.execute(text("DELETE FROM sys_department WHERE code LIKE 'SC%'"))
        db.commit()


def _scope(db, uid, purpose="lead"):
    user = db.get(SysUser, uid)
    return build_scope(db, user, purpose)


def _lead_ids(db, scope):
    stmt = scope.apply(select(CrmLead), CrmLead)
    return {x.id for x in db.scalars(stmt)}


# ==================== 测试 ====================

def test_顾问只看到自己的线索(fixture_data):
    """顾问A1 只能看 L1，看不到 L2（同事）、L3（别部门）"""
    with Session() as db:
        ids = _lead_ids(db, _scope(db, fixture_data["a1"]))
    assert fixture_data["l1"] in ids          # 自己的 ✅
    assert fixture_data["l2"] not in ids      # 同事的 ❌
    assert fixture_data["l3"] not in ids      # 别部门 ❌


def test_两个顾问范围互不相交(fixture_data):
    """A1 和 A2 同部门，但各自只看自己的"""
    with Session() as db:
        ids_a1 = _lead_ids(db, _scope(db, fixture_data["a1"]))
        ids_a2 = _lead_ids(db, _scope(db, fixture_data["a2"]))
    assert ids_a1.isdisjoint(ids_a2), "两个顾问的可见范围不该重叠"


def test_主管看到本部门全部(fixture_data):
    """主管A 看得到本部门的 L1、L2，但看不到 B 部门的 L3"""
    with Session() as db:
        ids = _lead_ids(db, _scope(db, fixture_data["head_a"]))
    assert fixture_data["l1"] in ids
    assert fixture_data["l2"] in ids          # 同事的，主管能看到 ✅
    assert fixture_data["l3"] not in ids      # 别部门 ❌


def test_主管看不到别部门(fixture_data):
    """⚠️ 主管不自动获得兄弟部门数据"""
    with Session() as db:
        ids = _lead_ids(db, _scope(db, fixture_data["head_a"]))
    assert fixture_data["l3"] not in ids


def test_管理员看全域(fixture_data):
    with Session() as db:
        ids = _lead_ids(db, _scope(db, fixture_data["admin"]))
    assert fixture_data["l1"] in ids
    assert fixture_data["l2"] in ids
    assert fixture_data["l3"] in ids          # 跨部门也能看 ✅


def test_顾问取他人线索_404(fixture_data):
    """⭐ 核心防越权：按 id 取别人的线索 → 404（不是 403）"""
    with Session() as db:
        scope = _scope(db, fixture_data["a1"])
        # 自己的：能取
        assert scope.get_or_404(db, CrmLead, fixture_data["l1"]).id == fixture_data["l1"]
        # 别人的：404
        with pytest.raises(NotFoundError):
            scope.get_or_404(db, CrmLead, fixture_data["l2"])
        # 别部门的：404
        with pytest.raises(NotFoundError):
            scope.get_or_404(db, CrmLead, fixture_data["l3"])


def test_can_see_判断(fixture_data):
    with Session() as db:
        scope = _scope(db, fixture_data["a1"])
        l1 = db.get(CrmLead, fixture_data["l1"])
        l2 = db.get(CrmLead, fixture_data["l2"])
        assert scope.can_see(l1) is True
        assert scope.can_see(l2) is False


def test_敏感标志默认关(fixture_data):
    """⚠️ 管理员也不自动获得心理/投诉权限"""
    with Session() as db:
        admin_scope = _scope(db, fixture_data["admin"])
    assert admin_scope.can_see_feedback() is False
    assert admin_scope.can_see_psych() is False


def test_显式授权后才能看敏感数据(fixture_data):
    with Session() as db:
        db.execute(text("UPDATE sys_user SET can_handle_feedback=true, psych_access_enabled=true WHERE id=:u"),
                   {"u": fixture_data["a1"]})
        db.commit()
        scope = _scope(db, fixture_data["a1"])
        assert scope.can_see_feedback() is True
        assert scope.can_see_psych() is True
        # 还原
        db.execute(text("UPDATE sys_user SET can_handle_feedback=false, psych_access_enabled=false WHERE id=:u"),
                   {"u": fixture_data["a1"]})
        db.commit()


def test_没人能看别人的_兜底(fixture_data):
    """没有 range 的员工（比如新人）→ 什么都看不到，不会放开"""
    with Session() as db:
        db.execute(text("""
            INSERT INTO sys_user(username,password_hash,real_name,user_type,employee_role,dept_id)
            VALUES ('sc_newbie',:p,'新人','EMPLOYEE','NEWCOMER',:d)
        """), {"p": hash_password("pw12345678"), "d": fixture_data["dept_a"]})
        db.commit()
        newbie = db.scalar(text("SELECT id FROM sys_user WHERE username='sc_newbie'"))
        ids = _lead_ids(db, _scope(db, newbie))
    assert len(ids) == 0, "新人默认不该看到任何线索"
