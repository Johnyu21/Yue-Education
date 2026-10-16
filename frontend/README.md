# 前端（Vue 3 + TypeScript + Vite）

## 快速开始

```bash
npm install
npm run dev          # http://localhost:5173（自动代理 /api 到后端 8000）
```

**前提**：后端已在 8000 端口运行（见 `docs/M1-10-集成基线.md`）。

## 目录（按规范 02 文档）

```
src/
├── api/            # ⭐ 唯一的 HTTP 客户端（统一响应/令牌/401）
│   └── client.ts
├── types/          # 类型 + 枚举中英对照
│   └── enums.ts
├── layouts/        # 访客/学生/员工布局、消息铃铛、助手浮窗
├── views/
│   ├── public/     # M2 业务页面
│   ├── employee/   # M3 业务页面
│   ├── student/    # M4 业务页面
│   └── reports/    # M5 报告页面
├── components/     # 表单、确认卡、状态标签、分页
├── stores/         # Pinia 状态
└── router/         # 路由 + 守卫
```

## 谁写哪块

| 目录 | 负责人 |
|---|---|
| `api/` `layouts/` `router/` `stores/` `types/` | **M5**（骨架） |
| `views/public/` | M2 |
| `views/employee/` | M3 |
| `views/student/` | M4 |
| `views/reports/` | M5 |
| 登录/组织管理页 | M1 |

## ⚠️ 三条规矩

1. **只有一个 HTTP 客户端** —— 所有请求走 `@/api/client`，**不要自己 new axios**
2. **枚举显示要查表** —— 后端返回 `NEW`，前端查 `LEAD_STATUS` 显示"新增意向"
3. **令牌自动带** —— client 已处理，页面不用管

## 和后端的对应关系

| 前端 | 后端 |
|---|---|
| `api/client.ts` 的 `ApiResponse` | `app/core/responses.py` 的 `ok()` |
| `ApiError` | `app/core/errors.py` 的 AppError |
| `types/enums.ts` | `docs/M1-01-公共契约冻结.md` 的枚举表 |
