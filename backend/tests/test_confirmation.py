"""
确认令牌验收测试（M1 补充）

核心验证：**令牌被篡改/过期/张冠李戴时，一律拒绝**。
运行：pytest tests/test_confirmation.py -v
"""
import time

import jwt
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.confirmation import (
    CONFIRM_TTL_MINUTES,
    new_request_key,
    sign_confirmation,
    verify_confirmation,
)
from app.core.errors import InvalidRequestError
from app.core.security import hash_password
from app.models.user import SysUser

Engine = create_engine(settings.database_url)
Session = sessionmaker(bind=Engine)


@pytest.fixture(scope="module")
def users():
    """两个测试用户，用来测"拿别人的令牌"场景。"""
    with Session() as db:
        db.execute(text("DELETE FROM sys_user WHERE username LIKE 'cf_%'"))
        db.execute(text("INSERT INTO sys_department(code,name) VALUES ('CFD','确认测试部') ON CONFLICT (code) DO NOTHING"))
        dept = db.scalar(text("SELECT id FROM sys_department WHERE code='CFD'"))
        for name in ("cf_a", "cf_b"):
            db.execute(text("""
                INSERT INTO sys_user(username,password_hash,real_name,user_type,employee_role,dept_id)
                VALUES (:u,:p,:u,'EMPLOYEE','ADVISOR',:d)
            """), {"u": name, "p": hash_password("pw12345678"), "d": dept})
        db.commit()
        a = db.get(SysUser, db.scalar(text("SELECT id FROM sys_user WHERE username='cf_a'")))
        b = db.get(SysUser, db.scalar(text("SELECT id FROM sys_user WHERE username='cf_b'")))
    yield {"a": a, "b": b}
    with Session() as db:
        db.execute(text("DELETE FROM sys_user WHERE username LIKE 'cf_%'"))
        db.commit()


PAYLOAD = {"service_type": "LEAVE", "title": "请假", "start_at": "2026-10-20T09:00:00+08:00"}


def _mktoken(actor, *, op="SUBMIT_SERVICE", eid=None, payload=PAYLOAD, ev=None, rk=None):
    return sign_confirmation(actor, op, entity_id=eid, payload=payload,
                             expected_version=ev, request_key=rk or new_request_key())


# ==================== 正例 ====================

def test_正常确认通过(users):
    tok = _mktoken(users["a"])
    claims = verify_confirmation(users["a"], tok, operation="SUBMIT_SERVICE",
                                 entity_id=None, payload=PAYLOAD)
    assert claims["op"] == "SUBMIT_SERVICE"
    assert claims["sub"] == str(users["a"].id)


def test_带版本的确认通过(users):
    tok = _mktoken(users["a"], op="APPROVE_SERVICE", eid=301, ev=2)
    claims = verify_confirmation(users["a"], tok, operation="APPROVE_SERVICE",
                                 entity_id=301, payload=PAYLOAD, expected_version=2)
    assert claims["ev"] == 2


# ==================== 攻击场景（必须拒绝）====================

def test_没有令牌_拒绝(users):
    with pytest.raises(InvalidRequestError):
        verify_confirmation(users["a"], None, operation="SUBMIT_SERVICE",
                            entity_id=None, payload=PAYLOAD)


def test_拿别人的令牌_拒绝(users):
    """⚠️ 用户 B 的令牌，用户 A 用不了"""
    tok_b = _mktoken(users["b"])
    with pytest.raises(InvalidRequestError) as e:
        verify_confirmation(users["a"], tok_b, operation="SUBMIT_SERVICE",
                            entity_id=None, payload=PAYLOAD)
    assert "不符" in str(e.value)


def test_确认后偷改内容_拒绝(users):
    """⚠️ 核心：确认了"请假3天"，实际提交"请假30天" → 必须拒绝"""
    tok = _mktoken(users["a"], payload={"days": 3})
    tampered = {"days": 30}
    with pytest.raises(InvalidRequestError) as e:
        verify_confirmation(users["a"], tok, operation="SUBMIT_SERVICE",
                            entity_id=None, payload=tampered)
    assert "内容已变更" in str(e.value)


def test_换操作类型_拒绝(users):
    """⚠️ 拿"确认请假"的令牌去"确认转学生" → 拒绝"""
    tok = _mktoken(users["a"], op="SUBMIT_SERVICE")
    with pytest.raises(InvalidRequestError) as e:
        verify_confirmation(users["a"], tok, operation="CONVERT_LEAD",
                            entity_id=None, payload=PAYLOAD)
    assert "操作" in str(e.value)


def test_换对象_拒绝(users):
    """⚠️ 确认的是 301 号申请，却拿去操作 999 号 → 拒绝"""
    tok = _mktoken(users["a"], op="APPROVE_SERVICE", eid=301, ev=1)
    with pytest.raises(InvalidRequestError):
        verify_confirmation(users["a"], tok, operation="APPROVE_SERVICE",
                            entity_id=999, payload=PAYLOAD, expected_version=1)


def test_版本不符_拒绝(users):
    """⚠️ 确认时版本=2，实际已变=3（有人改过）→ 拒绝"""
    tok = _mktoken(users["a"], op="APPROVE_SERVICE", eid=301, ev=2)
    with pytest.raises(InvalidRequestError) as e:
        verify_confirmation(users["a"], tok, operation="APPROVE_SERVICE",
                            entity_id=301, payload=PAYLOAD, expected_version=3)
    assert "版本" in str(e.value)


def test_篡改签名_拒绝(users):
    tok = _mktoken(users["a"])
    with pytest.raises(InvalidRequestError):
        verify_confirmation(users["a"], tok + "x", operation="SUBMIT_SERVICE",
                            entity_id=None, payload=PAYLOAD)


def test_过期令牌_拒绝(users):
    """⚠️ 5 分钟后失效。这里直接构造一个已过期的令牌。"""
    from datetime import datetime, timedelta, timezone
    expired = jwt.encode(
        {"sub": str(users["a"].id), "op": "SUBMIT_SERVICE", "eid": None,
         "ph": "", "ev": None, "rk": "x", "iss": "confirm",
         "iat": datetime.now(timezone.utc) - timedelta(minutes=10),
         "exp": datetime.now(timezone.utc) - timedelta(minutes=5)},
        settings.jwt_secret, algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(InvalidRequestError) as e:
        verify_confirmation(users["a"], expired, operation="SUBMIT_SERVICE",
                            entity_id=None, payload=PAYLOAD)
    assert "过期" in str(e.value)


def test_登录令牌不能当确认令牌(users):
    """⚠️ 两种令牌不能混用（issuer 不同）"""
    from app.core.security import create_access_token
    login_tok = create_access_token(users["a"].id, 0)
    with pytest.raises(InvalidRequestError):
        verify_confirmation(users["a"], login_tok, operation="SUBMIT_SERVICE",
                            entity_id=None, payload=PAYLOAD)


def test_有效期是5分钟(users):
    assert CONFIRM_TTL_MINUTES == 5


def test_followup_omitted_plan_cannot_be_changed_to_clear(users):
    from uuid import uuid4
    from app.schemas.lead import FollowUpIn
    from app.services.m3_canonical import follow_up_payload
    key=uuid4()
    keep=FollowUpIn(content='Synthetic followup',expected_version=1,request_key=key)
    clear=FollowUpIn(content='Synthetic followup',expected_version=1,request_key=key,next_follow_up_at=None)
    token=sign_confirmation(users['a'],'ADD_FOLLOWUP',entity_id=1,payload=follow_up_payload(keep),expected_version=1,request_key=str(key))
    with pytest.raises(InvalidRequestError):verify_confirmation(users['a'],token,operation='ADD_FOLLOWUP',entity_id=1,payload=follow_up_payload(clear),expected_version=1,request_key=key)
