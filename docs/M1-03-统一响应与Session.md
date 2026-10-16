# M1-03 · 统一响应、异常与 Session

> 状态：**✅ 已完成并验证**　完成日期：2026-10-16　负责人：P1（M1）
> 读者：**M2 / M3 / M4**（所有人写接口都用它）

---

## 一、交付内容

| # | 产出 | 文件 | 一句话 |
|---|---|---|---|
| 1 | 配置读取 | `app/core/config.py` | 从 `.env` 读配置，全项目共用一份 |
| 2 | 数据库 Session | `app/db/session.py` | 统一连库/关库，业务不用管连接 |
| 3 | 统一响应 + 异常 | `app/core/responses.py` | 所有接口同一格式，request_id 贯穿 |
| 4 | 异常类型库 | `app/core/errors.py` | 13 种现成异常，抛了自动变标准响应 |
| 5 | 应用入口 | `app/main.py` | 组装应用 + 健康检查 |
| 6 | 验收测试 | `tests/test_responses.py` | 8 项测试，全通过 |

---

## 二、设计说明（必看）

### 2.1 为什么要"统一响应格式"

**问题**：如果每个人按自己喜好写返回，会变成这样——
```python
# 张三写的
return {"success": True, "result": {...}}
# 李四写的
return {"code": 0, "data": {...}}
# 王五写的
return {...}          # 直接返回对象
```
**前端要写 N 套逻辑去解析**，Dify 也一样。改起来全组返工。

**所以定死一种格式**，所有人照它来：
```json
{"code":"OK", "message":"成功", "data":{...}, "request_id":"req-xxx"}
```

### 2.2 为什么要 `request_id`

**问题**：用户说"我操作报错了"，你**不知道是哪一次请求**（日志里几百条）。

**所以每个请求发一个唯一编号**，前端报错时带上它 → 后端一搜就定位到那一次。

### 2.3 为什么异常要"统一处理"而不是每处 try/except

**问题**：如果每个接口自己写 try/except，**迟早有人漏**，结果：
- 有的返回 500 堆栈 → **泄露 SQL、密码**
- 有的返回格式不一样 → 前端又得特殊处理

**所以一处注册全局处理器**，所有异常自动变标准格式，
**未预期异常一律返回通用提示，绝不泄露内部细节**。

### 2.4 为什么业务代码不该自己 `db.commit()`

**问题**：一次业务可能改好几张表（如"转学生"要同时建账号、建档案、改线索）。
如果各改各的，**中途失败就留下一半数据**（脏数据）。

**所以事务统一由 service 层管**，要么全成功、要么全回滚（M1-06 实现）。

---

## 三、验证结果

**验收标准**：422/401/500 均同结构，且无 SQL/secret。

```
$ pytest tests/test_responses.py -v
✅ 成功响应结构
✅ 401 未登录
✅ 404 不存在
✅ 409 状态冲突
✅ 422 字段校验
✅ 500 不泄露敏感信息      ← 最关键
✅ 所有错误结构一致
✅ request_id 在响应头
========= 8 passed =========
```

### 关键验证：500 不泄露敏感信息

**测试故意在异常里塞密码和 SQL**：
```python
raise RuntimeError("数据库密码是 secret123，SQL=SELECT * FROM sys_user")
```
**断言响应里不能出现** `secret123` / `SELECT` / `Traceback` / `RuntimeError`
→ ✅ **全部拦住**，只返回：
```json
{"code":"INTERNAL_ERROR","message":"服务器内部错误"}
```

### 实测响应

```json
// 成功
{"code":"OK","message":"成功","data":{"status":"up","database":true},"request_id":"3ab75064-0587-4150-970a-ff11d1c22588"}

// 404
{"code":"NOT_FOUND","message":"Not Found","data":null,"errors":[],"request_id":"3ab75064-0587-4150-970a-ff11d1c22588"}
```

---

## 四、使用方式

### 4.1 写接口 —— 标准三步

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.responses import ok
from app.db.session import get_db

router = APIRouter(prefix="/api/v1/leads", tags=["线索"])

@router.get("")
def list_leads(db: Session = Depends(get_db)):
    return ok({"items": [...], "total": 10})   # 只写 ok()，request_id 自动带
```

### 4.2 报错 —— 抛现成的异常

```python
from app.core.errors import NotFoundError, StateConflictError

@router.post("/{id}/approve")
def approve(id: int, db: Session = Depends(get_db)):
    svc = db.get(StudentAdminService, id)
    if svc is None:
        raise NotFoundError("申请不存在")           # 自动变 404 + 标准格式
    if svc.status != "PENDING":
        raise StateConflictError("该申请已审批过")   # 自动变 409
```

**现成异常一览**（`app/core/errors.py`）：

| 异常 | HTTP | 用在哪 |
|---|---|---|
| `InvalidRequestError` | 400 | 请求无法处理 |
| `AuthRequiredError` | 401 | 未登录 |
| `TokenExpiredError` | 401 | 令牌过期 |
| `ForbiddenError` | 403 | 角色没权限 |
| `NotFoundError` | 404 | 不存在**或不在数据范围内** |
| `VersionConflictError` | 409 | 并发冲突 |
| `StateConflictError` | 409 | 状态不允许 |
| `DuplicateResourceError` | 409 | 重复（手机号已存在） |
| `EventFullError` | 409 | 名额满 |
| `ValidationError` | 422 | 字段校验 |
| `AIBadResponseError` | 502 | Dify 返回不合约定 |
| `AIUnavailableError` | 503 | Dify 不可用 |
| `AITimeoutError` | 504 | AI 超时 |

### 4.3 读配置

```python
from app.core.config import settings
settings.database_url          # postgresql+psycopg://...
settings.jwt_expire_minutes    # 120
```

### 4.4 启动

```bash
cd backend && source .venv/bin/activate
uvicorn app.main:app --reload --port 8000

curl http://localhost:8000/api/v1/health/ready
# database:true 表示数据库已连通
```

---

## 五、注意事项（必看）

| ❌ 不要 | 为什么 | ✅ 应该 |
|---|---|---|
| 自己 `return {...}` 造格式 | 破坏全组一致性，前端要写 N 套解析 | 用 `ok(data)` |
| 自己 `try/except` 吞异常 | 会漏、会不统一；漏了就泄露堆栈 | 让它抛，全局处理器兜 |
| `except: pass` | 错误被吃掉，排查时毫无线索 | 抛出来，或记日志 |
| 业务代码自己 `db.commit()` | 一次业务改多表时，中途失败留脏数据 | 事务交给 service 层（M1-06） |
| 在响应里放敏感信息 | SQL、密码、堆栈会泄露给前端 | 用现成异常，细节只写日志 |
