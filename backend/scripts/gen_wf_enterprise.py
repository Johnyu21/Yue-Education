"""
生成 dify/wf_enterprise.yml（企业助手 WF_ENTERPRISE）

用法：cd backend && python -m scripts.gen_wf_enterprise
⚠️ 模型 provider/name 与知识库 dataset_ids 故意留空，导入 Dify 后由使用者配置。
"""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "dify" / "wf_enterprise.yml"

CLASSES = [
    ("c_lead", "意向客户（录入/查询/详情）"),
    ("c_follow", "跟进记录（写跟进/查历史）"),
    ("c_status", "客户状态（流失/恢复）"),
    ("c_daily", "员工日报（草稿/查询）"),
    ("c_org", "组织架构与通讯录"),
    ("c_service", "学生审批（请假/考务/信息修改）"),
    ("c_feedback", "售后工单（清单/解决/跟进）"),
    ("c_psych", "心理关怀（待复核/记录说明）"),
    ("c_progress", "申请进度（查询/推进）"),
    ("c_todo", "统一待办"),
    ("c_knowledge", "新人指引/制度/闲聊"),
]

PROMPTS = {
    "c_lead": """你是"意向客户"参数提取助手。只输出一个 JSON 对象，不要解释、不要 markdown 代码块。
输出格式：
{"intent":"LEAD_CREATE|LEAD_SEARCH|LEAD_DETAIL","params":{"keyword":null,"lead_id":null,"status":null},
 "draft":{"name":null,"mobile":null,"gender":null,"city":null,"education":null,
          "intended_project_id":null,"study_purpose":null,"interest_level":null,"content":null},
 "missing_fields":[]}
规则：
1. "新增/录入/新建客户"→LEAD_CREATE，draft 填姓名/手机号等；
2. "查/找/有哪些客户"→LEAD_SEARCH，条件放 params.keyword/status；
3. "某客户详情"→LEAD_DETAIL，尽量给 keyword 或 lead_id；
4. 未提到的字段保持 null，禁止编造；"已签约"不在此意图内，提醒走转化流程。
用户输入：{{#parse.message#}}""",
    "c_follow": """你是"跟进记录"参数提取助手。只输出一个 JSON 对象，不要解释、不要 markdown。
输出格式：
{"intent":"FOLLOWUP_ADD|FOLLOWUP_LIST","params":{"lead_id":null,"keyword":null},
 "draft":{"content":null},"missing_fields":[]}
规则：
1. "记跟进/写跟进/跟进一下"→FOLLOWUP_ADD，content 为员工描述的跟进内容；
2. "查跟进记录/跟进历史"→FOLLOWUP_LIST；
3. 客户用姓名（keyword）或编号（lead_id）定位；禁止编造。
用户输入：{{#parse.message#}}""",
    "c_status": """你是"客户状态"参数提取助手。只输出一个 JSON 对象，不要解释、不要 markdown。
输出格式：
{"intent":"LEAD_CHANGE_STATUS","params":{"lead_id":null,"keyword":null,
 "target_status":"LOST|FOLLOWING","reason":null},"missing_fields":[]}
规则：
1. "流失/放弃"→LOST，必须提取原因 reason；
2. "恢复跟进/重新联系"→FOLLOWING，reason 为恢复说明；
3. "已签约"不在此意图，回答提示走"签约转学生"流程。
用户输入：{{#parse.message#}}""",
    "c_daily": """你是"员工日报"参数提取助手。只输出一个 JSON 对象，不要解释、不要 markdown。
输出格式：
{"intent":"DAILY_DRAFT|DAILY_SEARCH","params":{},"draft":{"original_text":null},"missing_fields":[]}
规则：口述工作内容→DAILY_DRAFT，original_text 为员工原话；查询日报→DAILY_SEARCH。
用户输入：{{#parse.message#}}""",
    "c_org": """你是"组织架构"参数提取助手。只输出一个 JSON 对象，不要解释、不要 markdown。
输出格式：{"intent":"ORG_SEARCH","params":{"keyword":null},"missing_fields":[]}
规则：查询部门/同事/联系方式→ORG_SEARCH；keyword 为部门名或姓名。
用户输入：{{#parse.message#}}""",
    "c_service": """你是"学生审批"参数提取助手。只输出一个 JSON 对象，不要解释、不要 markdown。
输出格式：
{"intent":"LEAVE_DECIDE|SERVICE_LIST","params":{"service_id":null,
 "decision":"APPROVE|REJECT","note":null,"status":null},"missing_fields":[]}
规则：
1. "批准/同意/驳回某个申请"→LEAVE_DECIDE，必须提取 service_id（编号）；
2. "待审/申请列表"→SERVICE_LIST，status 默认 PENDING；
3. 未给编号时 missing_fields 填 service_id，不要猜。
用户输入：{{#parse.message#}}""",
    "c_feedback": """你是"售后工单"参数提取助手。只输出一个 JSON 对象，不要解释、不要 markdown。
输出格式：
{"intent":"FEEDBACK_LIST|FEEDBACK_HANDLE","params":{"ticket_id":null,
 "action":"NOTE|RESOLVE|ASSIGN","note":null,"resolution":null,
 "assignee_user_id":null},"missing_fields":[]}
规则：
1. "售后/投诉/工单列表"→FEEDBACK_LIST；
2. "解决/处理工单"→FEEDBACK_HANDLE，RESOLVE 必须提取 resolution；
3. 未给编号时 missing_fields 填 ticket_id。
用户输入：{{#parse.message#}}""",
    "c_psych": """你是"心理关怀"参数提取助手。只输出一个 JSON 对象，不要解释、不要 markdown。
输出格式：
{"intent":"PSYCH_LIST|PSYCH_NOTE","params":{"alert_id":null,"note":null},"missing_fields":[]}
规则：
1. "待复核/预警列表"→PSYCH_LIST；
2. "记录关怀/跟进说明"→PSYCH_NOTE，只记录 NOTE，不做确认/关闭；
3. 严禁输出学生情绪原话或风险结论。
用户输入：{{#parse.message#}}""",
    "c_progress": """你是"申请进度"参数提取助手。只输出一个 JSON 对象，不要解释、不要 markdown。
输出格式：
{"intent":"APPLICATION_SEARCH|APPLICATION_UPDATE","params":{"student_name":null,
 "case_no":null,"event_kind":"STAGE|DETAIL|ASSIGNMENT",
 "stage":"PROCESSING|COMPLETED","detail":null},"missing_fields":[]}
规则：
1. "查进度/文书/签证/院校"→APPLICATION_SEARCH；
2. "推进/更新进度"→APPLICATION_UPDATE，detail 必填；
3. STAGE 只能 PROCESSING 或 COMPLETED，不能跳阶。
用户输入：{{#parse.message#}}""",
    "c_todo": """你是"待办"参数提取助手。只输出一个 JSON 对象，不要解释、不要 markdown。
输出格式：{"intent":"TODO_LIST","params":{},"missing_fields":[]}
用户输入：{{#parse.message#}}""",
    "c_knowledge": """你是"知识库/闲聊"参数提取助手。只输出一个 JSON 对象，不要解释、不要 markdown。
输出格式：{"intent":"KNOWLEDGE|OTHER","params":{},"answer":null,"missing_fields":[]}
规则：问制度/入职/流程/公司信息→KNOWLEDGE；打招呼或无关→OTHER；不知道就如实说资料不足。
用户输入：{{#parse.message#}}""",
}

PARSE_CODE = """import json


def main(payload_json: str) -> dict:
    try:
        data = json.loads(payload_json or "{}")
    except Exception:
        data = {}
    return {
        "message": str(data.get("message") or ""),
        "actor_json": json.dumps(data.get("actor") or {}, ensure_ascii=False),
    }
"""

VALIDATE_CODE = """import json

ALLOWED = {
    "LEAD_CREATE", "LEAD_SEARCH", "LEAD_DETAIL", "FOLLOWUP_ADD", "FOLLOWUP_LIST",
    "LEAD_CHANGE_STATUS", "DAILY_DRAFT", "DAILY_SEARCH", "ORG_SEARCH",
    "SERVICE_LIST", "LEAVE_DECIDE", "FEEDBACK_LIST", "FEEDBACK_HANDLE",
    "PSYCH_LIST", "PSYCH_NOTE", "APPLICATION_SEARCH", "APPLICATION_UPDATE",
    "TODO_LIST", "METRIC_QUERY", "KNOWLEDGE", "OTHER",
}


def main(raw: str) -> dict:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text[:4].lower() == "json":
            text = text[4:]
    try:
        data = json.loads(text)
    except Exception:
        data = {}
    intent = str(data.get("intent") or "OTHER").upper()
    if intent not in ALLOWED:
        intent = "OTHER"
    return {
        "intent": intent,
        "action": str(data.get("action") or ""),
        "params_json": json.dumps(data.get("params") or {}, ensure_ascii=False),
        "draft_json": json.dumps(data.get("draft") or {}, ensure_ascii=False),
        "missing_json": json.dumps(data.get("missing_fields") or [], ensure_ascii=False),
    }
"""

ASSEMBLE_CODE = """import json


def main(intent: str, action: str, params_json: str, draft_json: str,
         missing_json: str, answer: str) -> dict:
    def load(value, default):
        try:
            return json.loads(value) if value else default
        except Exception:
            return default

    draft = load(draft_json, {}) or None
    data = {
        "schema_version": "1.0",
        "intent": intent or "OTHER",
        "action": action or None,
        "params": load(params_json, {}),
        "draft": draft,
        "missing_fields": load(missing_json, []),
        "answer": answer or "",
        "sources": [],
        "warnings": [],
    }
    return {"output_json": json.dumps(data, ensure_ascii=False)}
"""

ANSWER_PROMPT = """你是粤教留学的企业智能助手。当前消息与已识别的意图如下：
- 员工消息：{{#parse.message#}}
- 识别意图：{{#validate.intent#}}
- 参数：{{#validate.params_json#}}
- 知识库检索结果：{{#context#}}

要求：
1. 只依据给定信息回答，不编造客户、学生、数字或制度；
2. 业务意图（客户/跟进/审批/售后/心理/进度/待办）只输出一句简洁提示，例如"正在为你查询"或"请确认后执行"，**不要说已提交/已办理**；
3. 知识类问题依据检索结果回答，检索不到就明确"资料不足"；
4. 不要输出 JSON，不要输出 markdown，控制在 120 字以内。"""


def node(node_id: str, data: dict, x: int, y: int, *, h=90, w=244) -> dict:
    return {
        "data": data,
        "height": h,
        "id": node_id,
        "position": {"x": x, "y": y},
        "positionAbsolute": {"x": x, "y": y},
        "selected": False,
        "sourcePosition": "right",
        "targetPosition": "left",
        "type": "custom",
        "width": w,
    }


def edge(source: str, target: str, source_type: str, target_type: str,
         source_handle: str = "source") -> dict:
    return {
        "data": {
            "isInIteration": False,
            "isInLoop": False,
            "sourceType": source_type,
            "targetType": target_type,
        },
        "id": f"edge-{source}-{source_handle}-{target}",
        "source": source,
        "sourceHandle": source_handle,
        "target": target,
        "targetHandle": "target",
        "type": "custom",
        "zIndex": 0,
    }


def build() -> dict:
    nodes = []
    edges = []

    nodes.append(node("start", {
        "desc": "", "selected": False, "title": "开始", "type": "start",
        "variables": [{
            "label": "payload_json", "max_length": 20000, "options": [],
            "required": True, "type": "paragraph", "variable": "payload_json",
        }],
    }, 60, 420, h=116))

    nodes.append(node("parse", {
        "code": PARSE_CODE, "code_language": "python3",
        "outputs": {"message": {"children": None, "type": "string"},
                    "actor_json": {"children": None, "type": "string"}},
        "selected": False, "title": "解析入参", "type": "code",
        "variables": [{
            "value_selector": ["start", "payload_json"],
            "value_type": "string", "variable": "payload_json",
        }],
    }, 360, 420, h=120))
    edges.append(edge("start", "parse", "start", "code"))

    nodes.append(node("classifier", {
        "classes": [{"id": cid, "name": name} for cid, name in CLASSES],
        "instruction": "", "instructions": "",
        "model": {"completion_params": {"temperature": 0.1},
                  "mode": "chat", "name": "", "provider": ""},
        "query_variable_selector": ["parse", "message"],
        "selected": False, "title": "问题分类器", "type": "question-classifier",
        "vision": {"enabled": False},
    }, 680, 420, h=360))
    edges.append(edge("parse", "classifier", "code", "question-classifier"))

    for index, (class_id, _name) in enumerate(CLASSES):
        llm_id = f"llm_{class_id}"
        y = 40 + index * 120
        nodes.append(node(llm_id, {
            "context": {"enabled": False, "variable_selector": []},
            "model": {"completion_params": {"temperature": 0.2},
                      "mode": "chat", "name": "", "provider": ""},
            "prompt_template": [
                {"id": f"sys-{class_id}", "role": "system", "text": PROMPTS[class_id]},
                {"id": f"user-{class_id}", "role": "user", "text": "{{#parse.message#}}"},
            ],
            "reasoning_format": "separated",
            "selected": False,
            "structured_output_enabled": False,
            "title": dict(CLASSES)[class_id],
            "type": "llm",
            "vision": {"enabled": False},
        }, 1040, y, h=110))
        edges.append(edge("classifier", llm_id, "question-classifier", "llm",
                          source_handle=class_id))

    nodes.append(node("aggregate", {
        "output_type": "string", "selected": False, "title": "参数聚合",
        "type": "variable-aggregator",
        "variables": [[f"llm_{cid}", "text"] for cid, _ in CLASSES],
    }, 1420, 420, h=260))
    for class_id, _ in CLASSES:
        edges.append(edge(f"llm_{class_id}", "aggregate", "llm", "variable-aggregator"))

    nodes.append(node("validate", {
        "code": VALIDATE_CODE, "code_language": "python3",
        "outputs": {
            "intent": {"children": None, "type": "string"},
            "action": {"children": None, "type": "string"},
            "params_json": {"children": None, "type": "string"},
            "draft_json": {"children": None, "type": "string"},
            "missing_json": {"children": None, "type": "string"},
        },
        "selected": False, "title": "白名单校验", "type": "code",
        "variables": [{
            "value_selector": ["aggregate", "output"],
            "value_type": "string", "variable": "raw",
        }],
    }, 1760, 420, h=180))
    edges.append(edge("aggregate", "validate", "variable-aggregator", "code"))

    nodes.append(node("knowledge", {
        "dataset_ids": [],
        "multiple_retrieval_config": {
            "reranking_enable": False,
            "reranking_model": {"reranking_model_name": "", "reranking_provider_name": ""},
            "score_threshold": None, "score_threshold_enabled": False, "top_k": 4,
        },
        "query_variable_selector": ["parse", "message"],
        "retrieval_mode": "multiple",
        "selected": False, "title": "员工知识库检索",
        "type": "knowledge-retrieval",
    }, 2080, 420, h=120))
    edges.append(edge("validate", "knowledge", "code", "knowledge-retrieval"))

    nodes.append(node("answer_llm", {
        "context": {"enabled": True, "variable_selector": ["knowledge", "result"]},
        "model": {"completion_params": {"temperature": 0.3},
                  "mode": "chat", "name": "", "provider": ""},
        "prompt_template": [
            {"id": "sys-answer", "role": "system", "text": ANSWER_PROMPT},
            {"id": "user-answer", "role": "user", "text": "{{#parse.message#}}"},
        ],
        "reasoning_format": "separated",
        "selected": False,
        "structured_output_enabled": False,
        "title": "结果整理",
        "type": "llm",
        "vision": {"enabled": False},
    }, 2400, 420, h=140))
    edges.append(edge("knowledge", "answer_llm", "knowledge-retrieval", "llm"))

    nodes.append(node("assemble", {
        "code": ASSEMBLE_CODE, "code_language": "python3",
        "outputs": {"output_json": {"children": None, "type": "string"}},
        "selected": False, "title": "输出组装", "type": "code",
        "variables": [
            {"value_selector": ["validate", "intent"], "value_type": "string", "variable": "intent"},
            {"value_selector": ["validate", "action"], "value_type": "string", "variable": "action"},
            {"value_selector": ["validate", "params_json"], "value_type": "string", "variable": "params_json"},
            {"value_selector": ["validate", "draft_json"], "value_type": "string", "variable": "draft_json"},
            {"value_selector": ["validate", "missing_json"], "value_type": "string", "variable": "missing_json"},
            {"value_selector": ["answer_llm", "text"], "value_type": "string", "variable": "answer"},
        ],
    }, 2720, 420, h=240))
    edges.append(edge("answer_llm", "assemble", "llm", "code"))

    nodes.append(node("end", {
        "desc": "",
        "outputs": [{"value_selector": ["assemble", "output_json"],
                     "variable": "output_json"}],
        "selected": False, "title": "结束", "type": "end",
    }, 3040, 420, h=90))
    edges.append(edge("assemble", "end", "code", "end"))

    return {
        "app": {
            "description": "企业智能助手 WF_ENTERPRISE —— 客户/跟进/审批/售后/心理/进度/待办/知识库",
            "icon": "🤖",
            "icon_background": "#E4FBCC",
            "mode": "workflow",
            "name": "WF_ENTERPRISE",
            "use_icon_as_answer_icon": False,
        },
        "dependencies": [],
        "kind": "app",
        "version": "0.1.3",
        "workflow": {
            "conversation_variables": [],
            "environment_variables": [],
            "features": {
                "file_upload": {
                    "image": {"enabled": False, "number_limits": 3,
                              "transfer_methods": ["remote_url", "local_file"]},
                },
                "opening_statement": "",
                "retriever_resource": {"enabled": True},
                "sensitive_word_avoidance": {"enabled": False},
                "speech_to_text": {"enabled": False},
                "suggested_questions": [],
                "suggested_questions_after_answer": {"enabled": False},
                "text_to_speech": {"enabled": False, "language": "", "voice": ""},
            },
            "graph": {"edges": edges, "nodes": nodes, "viewport": {"x": 0, "y": 0}},
        },
    }


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as fh:
        fh.write("# WF_ENTERPRISE —— 企业智能助手（Dify 1.12.x Workflow）\n")
        fh.write("# 模型 provider/name 与知识库 dataset_ids 已留空，导入后在画布上配置。\n")
        fh.write("# 契约：Start 输入 payload_json（JSON 字符串），End 输出 output_json（JSON 字符串）。\n\n")
        yaml.safe_dump(build(), fh, allow_unicode=True, sort_keys=False, width=200)
    print(f"written: {OUT}")


if __name__ == "__main__":
    main()
