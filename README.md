# 粤教留学服务平台

> 面向粤教服务的**智能教育服务管理平台**：访客获客 → 客户研判 → 学生服务 → 智能报告。
> 技术栈：Python/FastAPI + PostgreSQL + Dify + Vue（前端后置）

---

## 快速开始（本地）

```bash
# 1. 起数据库（建好 19 张表）
cd deploy && docker compose up -d

# 2. 配后端
cd ../backend
cp .env.example .env

# 3. 装依赖并启动
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 4. 验证
curl http://localhost:8000/api/v1/health/ready
# 返回 database:true 就说明通了
```

数据库连接：`localhost:5432` / 用户 `postgres` / 库 `education` / 密码见 `deploy/docker-compose.yml`

---

## 目录结构

```
backend/     后端代码（Python + FastAPI）
deploy/      部署物料（建表脚本、docker-compose）
docs/        文档（模块说明、公共契约、协作规范）
```

**详细说明见 [docs/项目结构说明.md](docs/项目结构说明.md)**

---

## 文档导航

| 文档 | 内容 | 读者 |
|---|---|---|
| [项目结构说明](docs/项目结构说明.md) | 目录结构、文件放哪 | **全员**（第一天必读） |
| [AI 编码提示词模板](docs/AI编码提示词模板.md) | 用 AI 写代码前必贴 | **全员** |
| [M1-01 公共契约冻结](docs/M1-01-公共契约冻结.md) | 枚举 / ID / 时间 / 错误码 | **全员** |
| [M1-02 建库验证](docs/M1-02-建库验证.md) | 19 表结构 + 必填字段 | 后端 |
| [M1-03 统一响应与 Session](docs/M1-03-统一响应与Session.md) | 接口怎么写 | 后端 |
| [M1-04 认证](docs/M1-04-认证.md) | 登录 / 鉴权怎么用 | 后端 |
| [M1-05 数据范围 Scope](docs/M1-05-数据范围Scope.md) | 数据权限怎么控 | 后端 |
| [M1 事务管理](docs/M1-事务管理.md) | 多表操作怎么写 | 后端 |
| [M1 确认令牌](docs/M1-确认令牌.md) | AI 提议确认机制 | 后端 |

---

## 分工

| 模块 | 负责内容 |
|---|---|
| **M1 架构与公共模块** | 认证、权限、响应、数据库、事务、通知、文件、定时 |
| M2 访客客服与客户研判 | 三渠道获客、客服 Agent、研判、活动 |
| M3 企业助手 | CRM、转学生、日报、员工待办 |
| M4 学生助手 | 学生页面、行政、售后、心理、教务 |
| M5 智能报告与前端 | 五类报告、前端骨架与集成 |

---

## 当前进度

- ✅ M1-01 公共契约冻结
- ✅ M1-02 建库验证
- ✅ M1-03 统一响应与 Session
- ✅ M1-04 认证
- ✅ M1-05 数据范围 Scope
- ✅ M1 事务管理（补充）
- ✅ M1 确认令牌（补充）
- ⬜ M1-06 ~ M1-10

**测试状态**：46 项自动化测试全部通过
