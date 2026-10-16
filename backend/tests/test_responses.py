"""
M1-03 验收测试

验证：422 / 401 / 404 / 500 都是同一结构，且不泄露 SQL/密钥/堆栈。
运行：pytest tests/test_responses.py -v
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import AuthRequiredError, StateConflictError
from app.core.responses import setup_exception_handlers, setup_request_id, ok

# 造一个只用于测试的 app，挂上公共能力
app = FastAPI()
setup_request_id(app)
setup_exception_handlers(app)


@app.get("/ok")
def _ok():
    return ok({"x": 1})


@app.get("/boom")
def _boom():
    raise RuntimeError("数据库密码是 secret123，SQL=SELECT * FROM sys_user")  # 故意泄露，看会不会被兜住


@app.get("/need-auth")
def _need_auth():
    raise AuthRequiredError()


@app.get("/conflict")
def _conflict():
    raise StateConflictError("该申请已审批过")


@app.get("/need-int")
def _need_int(n: int):   # 传非整数会触发 422
    return ok({"n": n})


client = TestClient(app, raise_server_exceptions=False)


def test_成功响应结构():
    r = client.get("/ok")
    body = r.json()
    assert r.status_code == 200
    assert body["code"] == "OK"
    assert body["message"] == "成功"
    assert body["data"] == {"x": 1}
    assert body["request_id"].startswith("req-")


def test_401_未登录():
    r = client.get("/need-auth")
    body = r.json()
    assert r.status_code == 401
    assert body["code"] == "AUTH_REQUIRED"
    assert body["data"] is None


def test_404_不存在():
    r = client.get("/no-such-route")
    body = r.json()
    assert r.status_code == 404
    assert body["code"] == "NOT_FOUND"


def test_409_状态冲突():
    r = client.get("/conflict")
    body = r.json()
    assert r.status_code == 409
    assert body["code"] == "STATE_CONFLICT"


def test_422_字段校验():
    r = client.get("/need-int", params={"n": "abc"})
    body = r.json()
    assert r.status_code == 422
    assert body["code"] == "VALIDATION_ERROR"
    assert body["errors"][0]["field"] == "n"


def test_500_不泄露敏感信息():
    """最关键：500 不能把 SQL、密码、堆栈返回给前端"""
    r = client.get("/boom")
    body = r.json()
    raw = r.text
    assert r.status_code == 500
    assert body["code"] == "INTERNAL_ERROR"
    # 绝不能出现这些东西
    assert "secret123" not in raw, "泄露了密码！"
    assert "SELECT" not in raw, "泄露了 SQL！"
    assert "Traceback" not in raw, "泄露了堆栈！"
    assert "RuntimeError" not in raw, "泄露了异常类型！"


def test_所有错误结构一致():
    """422/401/404/500 都含同样的字段"""
    for path, params in [("/need-auth", {}), ("/no-such", {}),
                         ("/need-int", {"n": "x"}), ("/boom", {})]:
        body = client.get(path, params=params).json()
        assert set(body.keys()) >= {"code", "message", "data", "request_id"}


def test_request_id_在响应头():
    r = client.get("/ok")
    assert "x-request-id" in {k.lower() for k in r.headers}
