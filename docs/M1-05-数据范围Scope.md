# M1-05 · 数据范围 Scope

> 状态：**✅ 已完成并验证**　完成日期：2026-10-16　负责人：P1（M1）
> 读者：**M2 / M3 / M4**（所有查数据的接口）
> 代码：`backend/app/core/permissions.py`

---

## 一、交付内容

| # | 产出 | 一句话 |
|---|---|---|
| 1 | `build_scope(db, user, purpose)` | 算出登录人的数据范围 |
| 2 | `scope.apply(stmt, model)` | **查询时加过滤**（列表接口用） |
| 3 | `scope.get_or_404(db, model, id)` | 取详情，范围外**抛 404** |
| 4 | `scope.can_see(obj)` | 判断某条数据可不可见 |
| 5 | 敏感标志判断 | `can_see_feedback()` / `can_see_psych()` |
| 6 | 10 项验收测试 | 2 部门 / 2 顾问矩阵，全通过 |

---

## 二、设计说明

### 2.1 为什么这是 M1 最要紧的一块

**问题**：如果只在界面上"藏按钮"，**改个 URL 就能看别人的数据**。

实际事故场景：
```
顾问 A 的界面上只显示自己的线索
   ↓ 但他手动请求 GET /leads/999（别人线索的 id）
   ↓ 如果后端没过滤 → 数据就泄露了
```

**所以**：**范围必须在后端"查询阶段"过滤** —— 数据库层就不返回不该看的数据。

### 2.2 为什么"查询阶段过滤"而不是"查完再筛"

```python
# ❌ 错误做法：查全表 → Python 里 if 判断
all_leads = db.query(CrmLead).all()      # 越权数据已经出数据库了
visible = [l for l in all_leads if l.owner == me]
# 问题：① 数据已在内存里（可能被日志、异常打印泄露）
#       ② 数据量大时性能差

# ✅ 正确做法：条件写进 SQL
stmt = select(CrmLead).where(CrmLead.owner_user_id == me.id)
# 数据库层就不返回别人的
```

**这就是 `scope.apply()` 存在的原因** —— 它把范围条件拼进 SQL。

### 2.3 为什么范围外返回 404 而不是 403

| 返回 | 别人能推断出什么 |
|---|---|
| **403** | "这条数据**存在**，只是我没权限" ← **泄露了存在性** |
| **404** | "不存在" ← **什么都推断不出** |

**所以范围外一律 404** —— 攻击者无法通过 403/404 探测出"哪些 id 是有效的"。

### 2.4 为什么"主管"用部门关系推，不用 role

**问题**：如果用 `role='主管'` 存身份，会出现**两个真相源**（部门和 role 可能不一致）。

**所以**：主管 = `sys_department.head_user_id` 是我。**唯一事实源**，不会打架。

同样，班主任 = `sys_class.head_teacher_id` 是我。

### 2.5 为什么敏感权限不用角色推

**问题**：如果"管理员就能看心理数据"，那**管理员权限一泄露，心理数据全暴露**。

**所以**：心理/投诉要**额外的显式标志**（`psych_access_enabled` / `can_handle_feedback`），
**管理员也不自动获得** —— 这是最小权限原则。

---

## 三、验证结果

**验收标准（M1 原文）**：2 部门、2 班、2 顾问矩阵测试。

```
$ pytest tests/test_scope.py -v
✅ 顾问只看到自己的线索
✅ 两个顾问范围互不相交
✅ 主管看到本部门全部
✅ 主管看不到别部门            ← 不自动获得兄弟部门
✅ 管理员看全域
✅ 顾问取他人线索_404          ← 核心防越权
✅ can_see 判断
✅ 敏感标志默认关              ← 管理员也不自动有
✅ 显式授权后才能看敏感数据
✅ 没人能看别人的_兜底          ← 新人什么都看不到
========= 10 passed =========
```

### 矩阵验证（实际测出来的）

| 谁 | 能看到 | 看不到 |
|---|---|---|
| 顾问 A1 | 自己的 L1 | 同事的 L2、别部门 L3 |
| 顾问 A2 | 自己的 L2 | A1 的 L1 |
| 主管 A | L1 + L2（本部门） | **L3（B 部门）** |
| 管理员 | L1 + L2 + L3 | —（但心理/投诉仍要额外授权） |
| 新人 | **什么都看不到** | 全部 |

**A1 和 A2 的可见范围实测 `isdisjoint`（互不相交）** —— 严格隔离。

---

## 四、使用方式

### 4.1 列表查询（必须用 `apply`）

```python
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.deps import require_password_changed
from app.core.permissions import build_scope
from app.core.responses import ok
from app.db.session import get_db
from app.models.lead import CrmLead
from app.models.user import SysUser

@router.get("/api/v1/crm/leads")
def list_leads(user: SysUser = Depends(require_password_changed),
               db: Session = Depends(get_db)):
    scope = build_scope(db, user, "lead")
    stmt = scope.apply(select(CrmLead), CrmLead)     # ⭐ 自动加范围
    items = db.scalars(stmt).all()
    return ok({"items": [...], "total": len(items)})
```

### 4.2 取详情（必须用 `get_or_404`）

```python
@router.get("/api/v1/crm/leads/{lead_id}")
def get_lead(lead_id: int, user: SysUser = Depends(require_password_changed),
             db: Session = Depends(get_db)):
    scope = build_scope(db, user, "lead")
    lead = scope.get_or_404(db, CrmLead, lead_id)    # ⭐ 范围外自动 404
    return ok(lead_to_dict(lead))
```

### 4.3 判断敏感权限

```python
@router.get("/api/v1/tickets/{id}")
def get_ticket(...):
    if not scope.can_see_feedback():                 # 投诉正文
        raise ForbiddenError("需要售后处理权限")
    ...

@router.get("/api/v1/psych/profile/{student_id}")
def get_psych(...):
    if not scope.can_see_psych():                    # 心理数据
        raise ForbiddenError("需要心理数据授权")
    ...
```

### 4.4 purpose 取值

| purpose | 用在哪 | 过滤依据 |
|---|---|---|
| `"lead"` | 线索 | 负责顾问 `owner_user_id` |
| `"student"` | 学生 | 负责顾问 `advisor_user_id` |
| `"admin_service"` | 请假/考务 | 部门 `dept_id` |
| `"feedback"` | 投诉工单 | 处理人 `assignee_user_id` |
| `"daily_report"` | 日报 | 提交人 `employee_user_id` |
| `"score"` / `"schedule"` / `"progress"` / `"psych"` | 学生业务 | `student_profile_id` |

---

## 五、注意事项

| ❌ 不要 | 为什么 | ✅ 应该 |
|---|---|---|
| 先 `.all()` 再在 Python 里筛 | 越权数据已出库，可能被日志/异常泄露 | 用 `scope.apply()` 写进 SQL |
| 用 `db.get(Model, id)` 直接取详情 | **绕过范围**，能看别人数据 | 用 `scope.get_or_404()` |
| 范围外返回 403 | 泄露"这条数据存在" | 返回 **404**（`get_or_404` 已处理） |
| 让调用方传 `is_admin=true` | 等于让人自己声明权限 | 由 `build_scope` 按身份算 |
| 认为"管理员什么都能看" | 心理/投诉会被泄露 | 敏感数据要**显式标志** |
| 主管能看到子部门 | 需求明确"默认不含子部门" | 要扩展得单独批准 |
| 统计/导出/助手用另一套规则 | 会有漏洞从这些入口进来 | **所有入口用同一个 scope** |

### ⚠️ 一条最容易忘的

**统计报表、导出、AI 助手要查数据时，也必须用 scope。**
很多人只在"列表接口"加了范围，结果**从报表接口能导出全公司数据** —— 这是常见越权漏洞。
