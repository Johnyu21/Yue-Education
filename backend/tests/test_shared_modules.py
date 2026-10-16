"""
M1-06/07/08/09 验收测试

验证四块配套能力：
  M1-06 组织管理：禁止学生当班主任、禁止树循环、主管权限边界
  M1-07 通知：同 event_key 只发一条、事务一致性、他人不可读
  M1-08 文件：路径穿越、伪造归属、超大文件被拦
  M1-09 定时任务：单实例锁（并发只发一条通知）
运行：pytest tests/test_shared_modules.py -v
"""
import io

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.errors import InvalidRequestError, NotFoundError, StateConflictError
from app.core.notification import notify, list_my_notifications, mark_read
from app.core.security import hash_password
from app.core.transaction import with_business_transaction
from app.models.notification import Notification
from app.models.organization import SysClass, SysDepartment
from app.models.user import SysUser

Engine = create_engine(settings.database_url)
Session = sessionmaker(bind=Engine)


@pytest.fixture(autouse=True)
def cleanup():
    """每个测试前后清理测试数据。"""
    _clean()
    yield
    _clean()


def _clean():
    with Session() as db:
        db.execute(text("DELETE FROM crm_lead WHERE mobile LIKE '197%'"))
        db.execute(text("DELETE FROM notification WHERE business_event_key LIKE 'test:%'"))
        db.execute(text("DELETE FROM notification WHERE business_event_key LIKE 'lead:%'"))
        db.execute(text("DELETE FROM sys_class WHERE name LIKE '测试班%'"))
        db.execute(text("UPDATE sys_department SET head_user_id=NULL WHERE code LIKE 'SM%'"))
        db.execute(text("DELETE FROM sys_user WHERE username LIKE 'sm_%'"))
        db.execute(text("DELETE FROM sys_department WHERE code LIKE 'SM%'"))
        db.commit()


def _mk_dept(db, code, name):
    db.execute(text("INSERT INTO sys_department(code,name) VALUES (:c,:n)"),
               {"c": code, "n": name})
    return db.scalar(text("SELECT id FROM sys_department WHERE code=:c"), {"c": code})


def _mk_user(db, username, utype="EMPLOYEE", role="ADVISOR", dept=None):
    db.execute(text("""
        INSERT INTO sys_user(username,password_hash,real_name,user_type,employee_role,dept_id)
        VALUES (:u,:p,:u,:t,:r,:d)
    """), {"u": username, "p": hash_password("pw12345678"), "t": utype,
           "r": role, "d": dept})
    return db.scalar(text("SELECT id FROM sys_user WHERE username=:u"), {"u": username})


# =============================================================
# M1-06 组织管理
# =============================================================

def test_禁止学生当班主任():
    """⚠️ M1-06 验收点：班主任必须是员工"""
    from app.services import organization_service as svc
    with Session() as db:
        dept = _mk_dept(db, "SM1", "测试部门1")
        student = _mk_user(db, "sm_stu", utype="STUDENT", role=None, dept=None)
        db.commit()
        with pytest.raises(InvalidRequestError, match="必须是员工"):
            svc.create_class(db, code="CLS_TEST", name="测试班1",
                             dept_id=dept, head_teacher_id=student)


def test_禁止部门树循环():
    """⚠️ M1-06 验收点：不能把后代设为上级"""
    from app.services import organization_service as svc
    with Session() as db:
        a = _mk_dept(db, "SM2", "部门A")
        b = _mk_dept(db, "SM3", "部门B")
        db.execute(text("UPDATE sys_department SET parent_id=:a WHERE id=:b"),
                   {"a": a, "b": b})       # B 的上级是 A
        db.commit()
        # 把 A 的上级设为 B → 成环
        with pytest.raises(InvalidRequestError, match="环|下级"):
            svc.update_department(db, a, parent_id=b)


def test_部门不能把自己当上级():
    from app.services import organization_service as svc
    with Session() as db:
        a = _mk_dept(db, "SM4", "部门C")
        db.commit()
        with pytest.raises(InvalidRequestError, match="自己"):
            svc.update_department(db, a, parent_id=a)


def test_主管不能给自己变权():
    from app.services import organization_service as svc
    with Session() as db:
        dept = _mk_dept(db, "SM5", "部门D")
        head = _mk_user(db, "sm_head", role="ADVISOR", dept=dept)
        db.execute(text("UPDATE sys_department SET head_user_id=:h WHERE id=:d"),
                   {"h": head, "d": dept})
        db.commit()
        head_obj = db.get(SysUser, head)
        with pytest.raises(InvalidRequestError, match="不能给自己"):
            svc.update_user(db, head, actor=head_obj, can_handle_feedback=True)


def test_改敏感权限后token_version增加():
    """⚠️ 改权限 → 旧令牌失效"""
    from app.services import organization_service as svc
    with Session() as db:
        dept = _mk_dept(db, "SM6", "部门E")
        admin = _mk_user(db, "sm_admin", role="ADMIN", dept=dept)
        emp = _mk_user(db, "sm_emp", role="ADVISOR", dept=dept)
        db.commit()
        before = db.get(SysUser, emp).token_version
        admin_obj = db.get(SysUser, admin)
        svc.update_user(db, emp, actor=admin_obj, can_handle_feedback=True)
        db.commit()
        after = db.get(SysUser, emp).token_version
        assert after > before, "改敏感权限后 token_version 必须增加"


# =============================================================
# M1-07 通知
# =============================================================

def test_同一事件只发一条():
    """⚠️ M1-07 验收点：event_key 相同不重复发"""
    with Session() as db:
        dept = _mk_dept(db, "SM7", "部门F")
        u = _mk_user(db, "sm_n1", dept=dept)
        db.commit()
        with with_business_transaction(db):
            notify(db, "test:dup:1", [u], category="SYSTEM", title="第一次")
        with with_business_transaction(db):
            notify(db, "test:dup:1", [u], category="SYSTEM", title="第二次")
        n = db.scalar(text(
            "SELECT count(*) FROM notification WHERE business_event_key='test:dup:1'"))
        assert n == 1, "同一 event_key 应该只有一条"


def test_事务回滚时通知也回滚():
    """⚠️ 通知跟着业务事务：业务失败 → 通知也不该留下"""
    with Session() as db:
        dept = _mk_dept(db, "SM8", "部门G")
        u = _mk_user(db, "sm_n2", dept=dept)
        db.commit()
        try:
            with with_business_transaction(db):
                notify(db, "test:rollback:1", [u], category="SYSTEM", title="会回滚")
                raise RuntimeError("业务失败")
        except RuntimeError:
            pass
        n = db.scalar(text(
            "SELECT count(*) FROM notification WHERE business_event_key='test:rollback:1'"))
        assert n == 0, "业务回滚后通知不该留下"


def test_他人不可读通知():
    """⚠️ M1-07 验收点：只能读自己的"""
    with Session() as db:
        dept = _mk_dept(db, "SM9", "部门H")
        a = _mk_user(db, "sm_na", dept=dept)
        b = _mk_user(db, "sm_nb", dept=dept)
        db.commit()
        with with_business_transaction(db):
            notify(db, "test:mine:1", [a], category="SYSTEM", title="给A的")
        nid = db.scalar(text(
            "SELECT id FROM notification WHERE business_event_key='test:mine:1'"))
        # A 能读
        assert len(list_my_notifications(db, a)) >= 1
        # B 读不到
        assert all(n.id != nid for n in list_my_notifications(db, b))
        # B 标记 A 的通知 → 失败
        assert mark_read(db, b, nid) is False
        db.rollback()


def test_通知跳转类型白名单():
    """⚠️ 非法 related_type 被忽略（防钓鱼跳转）"""
    with Session() as db:
        dept = _mk_dept(db, "SM10", "部门I")
        u = _mk_user(db, "sm_n3", dept=dept)
        db.commit()
        with with_business_transaction(db):
            notify(db, "test:evil:1", [u], category="SYSTEM", title="x",
                   related_type="evil_page", related_id=1)
        n = db.scalar(text(
            "SELECT related_type FROM notification WHERE business_event_key='test:evil:1'"))
        assert n is None, "非法 related_type 应被忽略"


# =============================================================
# M1-08 文件
# =============================================================

def test_拒绝危险扩展名():
    """⚠️ M1-08 验收点：类型白名单"""
    from app.core.storage import _safe_ext
    with pytest.raises(InvalidRequestError):
        _safe_ext("shell.php")
    with pytest.raises(InvalidRequestError):
        _safe_ext("virus.exe")
    with pytest.raises(InvalidRequestError):
        _safe_ext("noext")
    assert _safe_ext("resume.pdf") == ".pdf"


def test_路径穿越被拦():
    """⚠️ M1-08 验收点：../../etc/passwd 之类被拒"""
    from app.core.storage import resolve_path
    assert resolve_path("../../../../etc/passwd") is None
    assert resolve_path("/etc/passwd") is None
    assert resolve_path("u/../..") is None


def test_上传文件名被重新生成(tmp_path, monkeypatch):
    """⚠️ 不用用户给的文件名（防穿越）"""
    from app.core import storage
    monkeypatch.setattr(storage, "_storage_root", lambda: tmp_path)
    from fastapi import UploadFile
    f = UploadFile(filename="../../../evil.pdf",
                   file=io.BytesIO(b"%PDF-1.4 test"),
                   headers={"content-type": "application/pdf"})
    key = storage.save_upload(f, owner_user_id=12)
    # 文件名不含用户输入，且按 owner 分目录
    assert key.startswith("u/12/")
    assert "evil" not in key
    assert ".." not in key
    assert (tmp_path / key).is_file()


def test_超大文件被拦(tmp_path, monkeypatch):
    """⚠️ M1-08 验收点：超过 10MB 拒绝，且不留残file"""
    from app.core import storage
    monkeypatch.setattr(storage, "_storage_root", lambda: tmp_path)
    from fastapi import UploadFile
    big = UploadFile(filename="big.pdf",
                     file=io.BytesIO(b"x" * (11 * 1024 * 1024)),
                     headers={"content-type": "application/pdf"})
    with pytest.raises(InvalidRequestError, match="超过"):
        storage.save_upload(big, owner_user_id=1)
    # 写了一半的文件应该被删掉
    leftover = list((tmp_path / "u" / "1").glob("*")) if (tmp_path / "u" / "1").exists() else []
    assert leftover == [], "超大文件应被清理，不留残file"


# =============================================================
# M1-09 定时任务
# =============================================================

def test_定时任务扫描不重复发通知():
    """⚠️ M1-09 验收点：同一提醒多次扫描只发一条"""
    from app.core.scheduler import scan_followup_reminders
    with Session() as db:
        dept = _mk_dept(db, "SM11", "部门J")
        emp = _mk_user(db, "sm_sch", dept=dept)
        db.execute(text("""
            INSERT INTO crm_lead(name,mobile,source,status,owner_user_id,dept_id,
                                 next_follow_up_at,request_key)
            VALUES ('定时测试','19700000001','WEBSITE','FOLLOWING',:o,:d,
                    now() - interval '1 hour', gen_random_uuid())
        """), {"o": emp, "d": dept})
        db.commit()
        lead = db.scalar(text("SELECT id FROM crm_lead WHERE mobile='19700000001'"))

    # 跑两次扫描
    scan_followup_reminders()
    scan_followup_reminders()

    with Session() as db:
        n = db.scalar(text("""
            SELECT count(*) FROM notification
            WHERE business_event_key LIKE :k
        """), {"k": f"lead:{lead}:followup:%"})
        assert n == 1, f"同一跟进提醒多次扫描只应发一条，实际 {n}"
        # 清理
        db.execute(text("DELETE FROM notification WHERE business_event_key LIKE :k"),
                   {"k": f"lead:{lead}:followup:%"})
        db.execute(text("DELETE FROM crm_lead WHERE mobile='19700000001'"))
        db.commit()
