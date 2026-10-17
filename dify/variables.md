# WF_STUDENT 输入输出变量说明

> 面向后端 `app/integrations/dify` 适配器与 Dify 工作流维护者。

## 1. 调用约定（Dify 1.12.1 Workflow 应用）

- 端点：`POST {DIFY_BASE_URL}/v1/workflows/run`
- 请求头：`Authorization: Bearer {DIFY_STUDENT_KEY}`
- 请求体：

```json
{
  "inputs": {
    "payload_json": "<字符串化的 JSON>"
  },
  "response_mode": "blocking",
  "user": "<user_id 字符串>"
}
```

- 响应取：`data.outputs.output_json`（字符串 JSON），后端解析一次并按 `WfStudentOutput` Schema 校验。

## 2. Start 输入变量

| 变量 | 类型 | 说明 |
|---|---|---|
| `payload_json` | paragraph（JSON 字符串） | 后端组装，工作流内用代码节点解析 |

`payload_json` 结构（后端 `student_assistant_service._build_payload` 生成）：

```json
{
  "schema_version": "1.0",
  "auth_token": "学生登录 JWT（供 HTTP 节点鉴权调后端接口）",
  "student_user_id": "学生账号 id（占位，JWT 已识别身份）",
  "message": "学生消息原文",
  "message_id": "uuid",
  "conversation_id": "可选会话 id",
  "input_kind": "CHAT | CHECK_IN",
  "observe_emotion": true,
  "context": { "page": null, "selected_id": null }
}
```

## 3. 架构：Dify 工作流内 HTTP 节点【直接调用后端接口】

学生助手不再由后端预查数据，而是工作流内按意图调用后端业务接口：

| 意图 | HTTP 方法 + 接口 | 说明 |
|---|---|---|
| PROFILE_QUERY | GET `/me/student-profile` | 查概览 |
| SCORE_QUERY | GET `/me/scores` | 查成绩 |
| SCHEDULE_QUERY | GET `/me/schedules` | 查日程 |
| CASE_QUERY | GET `/application-cases` | 查进度 |
| ASSESSMENT_QUERY | GET `/me/initial-assessment` | 查评估 |
| FAQ | 知识库检索（RAG） | 生活问答 |
| SERVICE_DRAFT | POST `/services` | 提交请假/考务/信息修改 |
| FEEDBACK_DRAFT | POST `/me/feedback-tickets` | 提交投诉/建议/咨询 |
| UPGRADE_INTEREST | POST `/me/upgrade-interests` | 提交升学意向 |
| OTHER | — | 兜底回答 |

**鉴权**：所有 HTTP 节点请求头带 `Authorization: Bearer {{#3.auth_token#}}`，后端标准鉴权识别学生身份、杜绝越权。

**后端地址**：工作流环境变量 `backend_base_url`（默认 `http://192.168.88.1:8000/api/v1`），部署时改成后端能被 Dify 访问到的实际地址。

## 4. End 输出变量

| 变量 | 类型 | 说明 |
|---|---|---|
| `output_json` | text（JSON 字符串） | 后端解析后校验 |

`output_json` 结构（`WfStudentOutput`）：

```json
{
  "schema_version": "1.0",
  "answer": "给学生看的回答（查询结果整理 / 写操作提交回执）",
  "intent": "意图枚举",
  "draft": null,
  "missing_fields": [],
  "sources": [],
  "warnings": [],
  "observation": {
    "emotion_state": "HEALTHY | NEGATIVE | VERY_NEGATIVE | UNKNOWN",
    "direct_signal": false,
    "confidence": 0.0
  }
}
```

## 5. 关键安全约束

- `observation` 只在 `observe_emotion=true` 时有效，且后端返回给学生前会**删除**该字段（不回显情绪/风险）。
- 写操作由 Dify 直接调用后端接口落单（后端业务层仍做权限/状态/幂等校验），返回真实业务回执。
- HTTP 节点持学生 JWT 只调学生本人接口，后端按 token 识别身份，改 URL 也读不到他人数据。
- FAQ 分支才走知识检索，其余分支不触发 RAG。

## 6. 待配置项

| 项 | 位置 | 说明 |
|---|---|---|
| 后端地址 | 环境变量 `backend_base_url` | 默认 `http://192.168.88.1:8000/api/v1`，部署时改 |
| LLM 大模型 | 各 LLM 节点 | 已填 deepseek-flash |
| 学生知识库 | `knowledge` 节点的 `dataset_ids` | 留空，RAG 文档编写后绑定 |
| 工作流 API Key | 后端 `.env` 的 `DIFY_STUDENT_KEY` | 待提供 |
