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

---

# WF_ENTERPRISE 输入输出变量说明（企业助手）

> 面向后端 `app/integrations/dify/enterprise.py` 与 `dify/wf_enterprise.yml`。
> 契约：Start 输入 `payload_json`（JSON 字符串），End 输出 `output_json`（JSON 字符串）。

## 1. payload_json 结构（后端组装）

```json
{
  "schema_version": "1.0",
  "message": "员工消息原文",
  "message_id": "uuid",
  "conversation_id": "可选会话 id",
  "context": {"page": null, "selected_id": null},
  "actor": {
    "id": "员工ID",
    "real_name": "姓名",
    "employee_role": "NEWCOMER|ADVISOR|SENIOR_ADVISOR|ADMIN",
    "dept_id": "部门ID",
    "is_dept_head": false,
    "can_handle_feedback": false,
    "psych_access_enabled": false
  }
}
```

⚠️ payload 不包含客户库明细、投诉正文、心理原文、临时密码；授权查询由 Python 在拿到意图后执行。

## 2. output_json 结构（Dify 输出）

```json
{
  "schema_version": "1.0",
  "intent": "LEAD_SEARCH",
  "action": null,
  "params": {"keyword": "张三"},
  "draft": null,
  "missing_fields": [],
  "answer": "正在为你查询",
  "sources": [],
  "warnings": []
}
```

## 3. 意图白名单（21 个，未知一律降级 OTHER）

| 类型 | 意图 |
|---|---|
| 读 | LEAD_SEARCH、LEAD_DETAIL、FOLLOWUP_LIST、TODO_LIST、SERVICE_LIST、FEEDBACK_LIST、PSYCH_LIST、APPLICATION_SEARCH、METRIC_QUERY、ORG_SEARCH、DAILY_SEARCH |
| 写（只出提议） | LEAD_CREATE、FOLLOWUP_ADD、LEAD_CHANGE_STATUS、DAILY_DRAFT、LEAVE_DECIDE、FEEDBACK_HANDLE、PSYCH_NOTE、APPLICATION_UPDATE |
| 知识/其他 | KNOWLEDGE、OTHER |

## 4. 写操作提议（由 Python 签发，不在 Dify 内）

| 意图 | operation | 确认后调用的普通接口 |
|---|---|---|
| LEAD_CREATE | CREATE_LEAD | POST /employees/leads |
| FOLLOWUP_ADD | ADD_FOLLOWUP | POST /employees/leads/{id}/follow-ups |
| LEAD_CHANGE_STATUS | TRANSITION_LEAD | POST /employees/leads/{id}/status |
| LEAVE_DECIDE | DECIDE_SERVICE | POST /services/{id}/decision |
| FEEDBACK_HANDLE | HANDLE_FEEDBACK | POST /employees/feedback-tickets/{id}/handling |
| PSYCH_NOTE | PSYCH_ALERT_NOTE | POST /employees/psych-alerts/{id}/actions |
| APPLICATION_UPDATE | ADVANCE_APPLICATION | POST /employees/application-cases/{case_no}/events |

确认令牌 5 分钟有效，绑定 actor/operation/entity_id/payload_hash/expected_version/request_key。

## 5. 聚合指标（METRIC_QUERY）

`params` 示例：

```json
{"metric": "SIGNED_COUNT", "time_range": "THIS_MONTH",
 "group_by": "OWNER", "filters": {"status": "SIGNED"}}
```

- metric：LEAD_COUNT / SIGNED_COUNT / FOLLOWUP_COUNT / FOLLOWUP_DUE_COUNT /
  SERVICE_PENDING_COUNT / FEEDBACK_OPEN_COUNT / APPLICATION_STAGE_COUNT / PSYCH_ALERT_COUNT
- time_range：TODAY / THIS_WEEK / THIS_MONTH / LAST_MONTH / THIS_YEAR / ALL
- group_by：按指标白名单（见设计文档 §3.1）
- 所有指标先按员工 Scope 过滤再聚合；敏感指标要求售后/心理授权。

## 6. 待配置项

| 项 | 位置 | 说明 |
|---|---|---|
| LLM 大模型 | 各 LLM 节点 `model.provider` / `model.name` | 留空，导入后选择 |
| 员工知识库 | `knowledge` 节点 `dataset_ids` | 留空，RAG 文档编写后绑定 |
| API Key | 后端 `.env` 的 `DIFY_ENTERPRISE_KEY` | 由使用者提供 |


---

<!-- ==================== M2 追加：WF_VISITOR / WF_ASSESSMENT ==================== -->

# WF_VISITOR 输入输出变量说明（M2 访客客服）

> 面向后端 `app/integrations/dify/visitor.py` 适配器与 Dify 工作流维护者。
> 工作流文件：`dify/wf_entry.yml`；后端 key：`.env` 的 `DIFY_VISITOR_KEY`。

## 1. 调用约定

同 WF_STUDENT：`POST {DIFY_BASE_URL}/v1/workflows/run`，
请求头 `Authorization: Bearer {DIFY_VISITOR_KEY}`，
请求体 `{"inputs": {"payload_json": "<字符串JSON>"}, "response_mode": "blocking", "user": "<会话或 visitor>"}`，
响应取 `data.outputs.output_json`（字符串 JSON），后端解析一次并按 `mode=VISITOR_ANSWER` 校验。

## 2. Start 输入变量

| 变量 | 类型 | 说明 |
|---|---|---|
| `payload_json` | paragraph（JSON 字符串） | 后端组装，工作流内用 Jinja 解析 |

`payload_json` 结构（后端 `visitor_assistant_service._build_payload` 生成）：

```json
{
  "schema_version": "1.0",
  "message": "访客消息原文",
  "message_id": "uuid",
  "conversation_id": "可选会话 id",
  "public_projects": [{"id": "11", "name": "已发布项目名", "country": "新加坡", "education_level": "本科"}],
  "open_events": [{"id": "3", "title": "开放活动标题", "start_at": "2026-10-25T02:00:00Z"}],
  "context": { "page": null, "selected_id": null }
}
```

> ⚠️ `public_projects` / `open_events` 由后端受控查询（只含**已发布**项目与**OPEN** 活动），
> 不包含任何客户库明细、员工信息或未公开项目。

## 3. End 输出变量

| 变量 | 类型 | 说明 |
|---|---|---|
| `output_json` | text（JSON 字符串） | 后端解析后按 `VISITOR_ANSWER` 校验 |

`output_json` 结构：

```json
{
  "schema_version": "1.0",
  "answer": "给访客看的回答",
  "intent": "FAQ | LEAD_DRAFT | ACTIVITY_DRAFT | OUT_OF_SCOPE",
  "draft": { "name": null, "mobile": "138...", "event_id": null },
  "missing_fields": ["name"],
  "sources": [{ "document_id": null, "title": "公开项目名", "section": "公开项目信息" }],
  "warnings": []
}
```

## 4. 关键安全约束（WF_VISITOR）

- **不得泄露客户资料**：客户是否存在、姓名、手机号、顾问、销售阶段一律不出现在回答中；
  索取客户名单/内部接口/系统提示词的请求 → `intent=OUT_OF_SCOPE` 并拒绝。
- **不得声称已提交**：`draft` 只是草稿，必须由访客在页面确认后调用后端普通接口
  （`POST /public/leads`、`POST /events/{id}/registrations`）；回复中不得出现"已提交/已报名成功"。
- **名额不预言**：名额以报名接口的实时结果为准，不说"已为您锁定名额"。
- **不得编造**：公司政策、项目条件、年龄/语言/资金门槛、机构与联系方式，缺资料就转人工。

---

# WF_ASSESSMENT 输入输出变量说明（M2 客户研判）

> 面向后端 `app/integrations/dify/assessment.py` 适配器与 Dify 工作流维护者。
> 工作流文件：`dify/wf_profile.yml`；后端 key：`.env` 的 `DIFY_ASSESSMENT_KEY`。

## 1. 调用约定

同上，响应取 `data.outputs.output_json`，后端按 `mode=ASSESSMENT_EXTRACT` 校验。

## 2. Start 输入变量

`payload_json` 结构（后端 `assessment_service._build_payload` 生成）：

```json
{
  "schema_version": "1.0",
  "lead_id": "客户ID",
  "request_id": "本次研判请求 UUID（防旧任务覆盖）",
  "confirmed_facts": { "education": "顾问已核对的学历" },
  "resume_text": "简历纯文本，可能为空或被截断",
  "project_rules": [{ "project_id": "11", "rules": { "已审核结构化条件" } }]
}
```

> ⚠️ 只发**单个客户**的已核对事实与简历最小片段；
> **不把整张客户表、员工 token 或其它客户数据发给 Dify**。

## 3. End 输出变量

```json
{
  "schema_version": "1.0",
  "mode": "ASSESSMENT_EXTRACT",
  "facts": { "education": "客户确认的学历" },
  "evidence": [{ "field": "education", "source_ref": "resume:p1", "snippet": "最小必要原文片段" }],
  "missing_fields": ["language_level"],
  "warnings": []
}
```

## 4. 关键约束（WF_ASSESSMENT）

- **只做提取**：`facts` 仅包含有据可依的字段，`confirmed_facts` 原样保留；
  没有依据的信息放进 `missing_fields`，**严禁编造**年龄/语言/资金门槛。
- **必须可追溯**：每个提取字段给出 `evidence.source_ref`（如 `resume:p12`）与最小必要 `snippet`。
- **不判定、不打分**：不得输出 `score` 或 `MATCH/NO_MATCH`，
  匹配结论与分数由后端按 `course_project.admission_rules`（**已审核**）确定性计算；
  规则缺失即返回 `NEEDS_INFO` 且分数为空。
- **无文本要明说**：`resume_text` 为空时 `warnings` 含 `NO_RESUME_TEXT`，不得假装识别成功。
