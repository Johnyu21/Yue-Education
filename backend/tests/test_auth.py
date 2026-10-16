"""
M1-04 认证验收测试

核心验证：**改密后旧 token 立即失效**（token_version 机制）。
运行：pytest tests/test_auth.py -v
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_token,
    hash_password,
    generate_temp_password,
    verify_password,
)

# ---------- 纯单元测试（不依赖数据库）----------

def test_密码哈希与校验():
    h = hash_password("abc12345")
    assert h != "abc12345"            # 不能是明文
    assert h.startswith("$2b$")       # bcrypt 格式
    assert verify_password("abc12345", h)
    assert not verify_password("wrong", h)


def test_临时密码是随机的():
    a, b = generate_temp_password(), generate_temp_password()
    assert a != b
    assert len(a) == 12


def test_令牌能签能解():
    t = create_access_token(user_id=42, token_version=3)
    p = decode_token(t)
    assert p["sub"] == "42"
    assert p["tv"] == 3


def test_篡改的令牌解不开():
    t = create_access_token(user_id=42, token_version=3)
    assert decode_token(t + "x") is None       # 签名被破坏
    assert decode_token("garbage") is None


# ---------- 集成测试（用真实数据库）----------

def _db():
    eng = create_engine(settings.database_url)
    return sessionmaker(bind=eng)


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app, raise_server_exceptions=False)


def _ensure_user(username: str, password: str, role: str = "ADVISOR"):
    """造一个测试账号（已存在则重置密码和 token_version）。"""
    Session = _db()
    with Session() as db:
        db.execute(text("""
            INSERT INTO sys_department(code,name) VALUES ('T','测试部')
            ON CONFLICT (code) DO NOTHING
        """))
        db.execute(text("""
            INSERT INTO sys_user(username,password_hash,real_name,user_type,employee_role,dept_id)
            VALUES (:u,:p,:u2,'EMPLOYEE',:r,(SELECT id FROM sys_department WHERE code='T'))
            ON CONFLICT (username) DO UPDATE
              SET password_hash=:p, token_version=0, must_change_password=false
        """), {"u": username, "p": hash_password(password), "u2": username, "r": role})
        db.commit()


def test_登录成功(client):
    _ensure_user("t_advisor", "pw12345678")
    r = client.post("/api/v1/auth/login",
                    json={"username": "t_advisor", "password": "pw12345678"})
    b = r.json()
    assert r.status_code == 200
    assert b["code"] == "OK"
    assert b["data"]["user"]["employeeRole"] == "ADVISOR"
    assert b["data"]["user"]["id"].isdigit()   # id 是字符串


def test_密码错_提示统一(client):
    _ensure_user("t_advisor2", "pw12345678")
    r = client.post("/api/v1/auth/login",
                    json={"username": "t_advisor2", "password": "wrong"})
    assert r.status_code == 401
    assert r.json()["message"] == "用户名或密码错误"   # 不透露是用户名错还是密码错


def test_无令牌_401(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401
    assert r.json()["code"] == "AUTH_REQUIRED"


def test_改密后旧令牌失效(client):
    """⭐ M1-04 核心验收点"""
    _ensure_user("t_pwd", "old12345678")
    # ① 登录拿旧令牌
    old = client.post("/api/v1/auth/login",
                      json={"username": "t_pwd", "password": "old12345678"}
                      ).json()["data"]["accessToken"]
    # 旧令牌此时可用
    assert client.get("/api/v1/auth/me",
                      headers={"Authorization": f"Bearer {old}"}).status_code == 200
    # ② 改密
    r = client.post("/api/v1/auth/change-password",
                    headers={"Authorization": f"Bearer {old}"},
                    json={"old_password": "old12345678", "new_password": "new12345678"})
    assert r.json()["code"] == "OK"
    # ③ 旧令牌失效（token_version 变了）
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {old}"})
    assert r.status_code == 401
    assert r.json()["code"] == "TOKEN_EXPIRED"
    # ④ 新密码能登录
    assert client.post("/api/v1/auth/login",
                       json={"username": "t_pwd", "password": "new12345678"}
                       ).json()["code"] == "OK"


def test_原密码错不能改(client):
    _ensure_user("t_pwd2", "right12345678")
    tok = client.post("/api/v1/auth/login",
                      json={"username": "t_pwd2", "password": "right12345678"}
                      ).json()["data"]["accessToken"]
    r = client.post("/api/v1/auth/change-password",
                    headers={"Authorization": f"Bearer {tok}"},
                    json={"old_password": "WRONG", "new_password": "new12345678"})
    assert r.status_code == 400


def test_新密码太短被拦(client):
    _ensure_user("t_pwd3", "good12345678")
    tok = client.post("/api/v1/auth/login",
                      json={"username": "t_pwd3", "password": "good12345678"}
                      ).json()["data"]["accessToken"]
    r = client.post("/api/v1/auth/change-password",
                    headers={"Authorization": f"Bearer {tok}"},
                    json={"old_password": "good12345678", "new_password": "短"})
    assert r.status_code == 422


def test_禁用账号登录被拒(client):
    _ensure_user("t_disabled", "pw12345678")
    Session = _db()
    with Session() as db:
        db.execute(text("UPDATE sys_user SET status='DISABLED' WHERE username='t_disabled'"))
        db.commit()
    r = client.post("/api/v1/auth/login",
                    json={"username": "t_disabled", "password": "pw12345678"})
    assert r.status_code == 403
    # 清理
    with Session() as db:
        db.execute(text("DELETE FROM sys_user WHERE username='t_disabled'"))
        db.commit()
