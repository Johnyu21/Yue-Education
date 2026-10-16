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
| `payload_json` | paragraph（JSON 字符串） | 后端组装，工作流内用 Jinja 解析 |

`payload_json` 结构（后端 `student_assistant_service._build_payload` 生成）：

```json
{
  "schema_version": "1.0",
  "message": "学生消息原文",
  "message_id": "uuid",
  "conversation_id": "可选会话 id",
  "input_kind": "CHAT | CHECK_IN",
  "observe_emotion": true,
  "student": {
    "id": "档案id",
    "real_name": "姓名",
    "class_name": "班级名",
    "advisor_name": "顾问名",
    "projects": ["项目名", "..."]
  },
  "context": { "page": null, "selected_id": null }
}
```

## 3. End 输出变量

| 变量 | 类型 | 说明 |
|---|---|---|
| `output_json` | text（JSON 字符串） | 后端解析后校验 |

`output_json` 结构（`WfStudentOutput`）：

```json
{
  "schema_version": "1.0",
  "answer": "给学生看的回答",
  "intent": "QUERY | FAQ | SERVICE_DRAFT | FEEDBACK_DRAFT | UPGRADE_INTEREST | OTHER",
  "draft": { "...": "写意图的草稿字段" },
  "missing_fields": ["start_at"],
  "sources": [{ "document_id": null, "title": "标题", "section": "段落" }],
  "warnings": [],
  "observation": {
    "emotion_state": "HEALTHY | NEGATIVE | VERY_NEGATIVE | UNKNOWN",
    "direct_signal": false,
    "confidence": 0.0
  }
}
```

## 4. 关键安全约束

- `observation` 只在 `observe_emotion=true` 时返回，且后端返回给学生前会**删除**该字段（不回显情绪/风险）。
- 写意图（SERVICE_DRAFT / FEEDBACK_DRAFT / UPGRADE_INTEREST）后端只生成**提议卡片 + confirmation_token**，不直接写库；LLM 文本"已提交"不算业务回执。
- 学务查询的事实由后端放入 `payload_json.student`，Dify 只总结，不得改变学生 ID、不得查库。

## 5. 待配置项

| 项 | 位置 | 说明 |
|---|---|---|
| LLM 大模型 | 节点 `llm` 的 `model.provider`/`model.name` | 留空，导入后选择 |
| 学生知识库 | 节点 `knowledge` 的 `dataset_ids` | 留空，RAG 文档编写后绑定 |
| 工作流 API Key | 后端 `.env` 的 `DIFY_STUDENT_KEY` | 待提供 |
