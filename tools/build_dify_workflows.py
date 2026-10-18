"""Build Studio-managed Dify DSLs, preserving existing model/knowledge bindings."""
import copy
import json
from pathlib import Path
import yaml
from assistant_dify_prompts import ASSESSMENT, ENTERPRISE, KNOWLEDGE, STUDENT, VISITOR
from build_m5_dify_workflows import ReadableDumper, build as build_m5
from m5_dify_nodes import (ASSISTANT_PREPARE, ASSISTANT_VALIDATE, ASSISTANT_PROMPT,
                           REPORT_PREPARE, REPORT_VALIDATE, REPORT_PROMPT)

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = (ROOT / "backend/app/integrations/dify/contracts.py").read_text(encoding="utf-8")
CONFIG = json.loads((ROOT / "dify/workflow_config.json").read_text(encoding="utf-8"))
PLUGIN = "langgenius/deepseek:0.0.24@9e12eef09973667f0eaf4f082af883167e1de88740b22e71e71488d020c3778a"
FILES = {"visitor": "wf_entry.yml", "assessment": "wf_profile.yml",
         "enterprise": "wf_enterprise.yml", "student": "wf_student.yml"}


def node(node_id, kind, title, x, y=260, **data):
    return {"id": node_id, "type": "custom", "data": {"type": kind, "title": title,
            "desc": "", "selected": False, **data}, "position": {"x": x, "y": y},
            "positionAbsolute": {"x": x, "y": y}, "width": 244, "height": 116,
            "sourcePosition": "right", "targetPosition": "left", "selected": False}


def code(node_id, title, source, variables, outputs, x, y=260):
    return node(node_id, "code", title, x, y, code=source.strip() + "\n", code_language="python3",
                variables=[{"variable": key, "value_selector": selector} for key, selector in variables.items()],
                outputs={key: {"type": value, "children": None} for key, value in outputs.items()})


def llm(node_id, title, prompt, user, x, y=260):
    return node(node_id, "llm", title, x, y, context={"enabled": False, "variable_selector": []},
                model={"provider": CONFIG["model_provider"], "name": CONFIG["model_name"], "mode": "chat",
                       "completion_params": {"temperature": 0.1}},
                prompt_template=[{"id": node_id + "-system", "role": "system", "text": prompt},
                                 {"id": node_id + "-user", "role": "user", "text": user}],
                variables=[], vision={"enabled": False}, structured_output_enabled=False)


def end(node_id, source, x, y=260):
    return node(node_id, "end", "结束：output_json", x, y,
                outputs=[{"variable": "output_json", "value_selector": [source, "output_json"]}])


def graph_edges(nodes, links):
    types = {n["id"]: n["data"]["type"] for n in nodes}
    return [{"id": f"{src}-{handle}-{dst}", "source": src, "target": dst,
             "sourceHandle": handle, "targetHandle": "target", "type": "custom", "zIndex": 0,
             "data": {"isInIteration": False, "isInLoop": False,
                      "sourceType": types[src], "targetType": types[dst]}}
            for src, dst, handle in links]


KB_CONTEXT = r'''
def main(records: list, query: str) -> dict:
    if not isinstance(records, list):
        raise ValueError("Invalid retrieval result")
    cleaned = []
    for record in records[:8]:
        if not isinstance(record, dict):
            continue
        meta = record.get("metadata") or {}
        # This input is wired directly to Dify's trusted retrieval node, never the LLM.
        # Dataset selection belongs to Studio; do not duplicate it in project config.
        if not isinstance(meta, dict) or not meta.get("dataset_id") or not meta.get("document_id"):
            continue
        content = record.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        cleaned.append({"record_id": str(len(cleaned) + 1), "content": content[:6000],
                        "document_id": str(meta["document_id"]),
                        "title": str(meta.get("document_name") or record.get("title") or "知识文档")[:200],
                        "section": str(meta.get("segment_id") or "")[:200]})
    return {"context_json": dump({"query": query, "audience": AUDIENCE, "records": cleaned})}
'''

KB_VALIDATE = r'''
def main(raw: str, context_json: str, output_json: str) -> dict:
    context, output, value = object_json(context_json), object_json(output_json), object_json(raw)
    if set(value) - {"answer", "citation_ids"}:
        raise ValueError("Invalid knowledge answer")
    used = strings(value.get("citation_ids", []))
    available = {r["record_id"]: r for r in context["records"]}
    if not set(used) <= set(available):
        raise ValueError("Invented knowledge citation")
    if not used:
        output["answer"] = "当前知识库资料不足，暂无法核实该问题，请联系相应业务人员。"
        output["sources"] = []
        output["warnings"].append("KB_NO_SUPPORTED_ANSWER")
    else:
        answer = string(value.get("answer"), 8000)
        if not answer:
            raise ValueError("Empty knowledge answer")
        output["answer"] = answer
        output["sources"] = [{k: available[key][k] for k in ("document_id", "title", "section")} for key in used]
    return {"output_json": dump(output)}
'''


def build(kind, studio_dsl=None):
    if CONFIG["target_dify_version"] != "1.12.1" or CONFIG["dsl_version"] != "0.5.0":
        raise ValueError("This builder targets Dify 1.12.1 / DSL 0.5.0")
    knowledge = kind in {"visitor", "enterprise", "student"}
    prepare = CONTRACTS + '\nKIND = ' + repr(kind) + r'''
def main(payload_json: str) -> dict:
    payload = prepare_payload(object_json(payload_json), KIND)
    if KIND == "assessment":
        payload["resume_lines"] = [{"source_ref": "resume:p" + str(i), "text": line}
                                   for i, line in enumerate(payload.get("resume_text", "").splitlines(), 1)]
    return {"normalized_json": dump(payload)}
'''
    sanitize = CONTRACTS + '\nKIND = ' + repr(kind) + r'''
def main(raw: str, normalized_json: str) -> dict:
    payload = object_json(normalized_json)
    validator = {"visitor": validate_visitor, "enterprise": validate_enterprise,
                 "student": validate_student, "assessment": validate_assessment}[KIND]
    output = validator(object_json(raw), payload)
    is_question = output.get("intent") == ("KNOWLEDGE" if KIND == "enterprise" else "FAQ")
    return {"output_json": dump(output), "knowledge_route": "enabled" if is_question else "skip",
            "query": payload.get("message", "")}
'''
    nodes = [node("start", "start", "开始：payload_json", 50,
                  variables=[{"variable": "payload_json", "label": "payload_json", "type": "paragraph",
                              "required": True, "max_length": 180000, "options": []}]),
             code("prepare", "核验入参及多轮上下文", prepare, {"payload_json": ["start", "payload_json"]},
                  {"normalized_json": "string"}, 350),
             llm("llm", "提取受控业务意图与草稿" if kind != "assessment" else "提取简历事实与原文证据",
                 {"visitor": VISITOR, "enterprise": ENTERPRISE, "student": STUDENT, "assessment": ASSESSMENT}[kind],
                 "{{#prepare.normalized_json#}}", 650),
             code("sanitize", "校验意图、字段、缺项及业务边界", sanitize,
                  {"raw": ["llm", "text"], "normalized_json": ["prepare", "normalized_json"]},
                  {"output_json": "string", "knowledge_route": "string", "query": "string"}, 950)]
    links = [("start", "prepare", "source"), ("prepare", "llm", "source"), ("llm", "sanitize", "source")]
    if knowledge:
        nodes += [node("knowledge_gate", "if-else", "仅知识问答进入检索", 1250,
                       cases=[{"case_id": "true", "logical_operator": "and", "conditions": [
                           {"id": "kb-ready", "varType": "string", "variable_selector": ["sanitize", "knowledge_route"],
                            "comparison_operator": "is", "value": "enabled"}]}]),
                  end("end", "sanitize", 1550, 520),
                  node("knowledge", "knowledge-retrieval", "在工作室选择对应知识库", 1550,
                       dataset_ids=[], retrieval_mode="multiple",
                       query_variable_selector=["sanitize", "query"], metadata_filtering_mode="disabled",
                       multiple_retrieval_config={"top_k": 4, "reranking_enable": False, "score_threshold": None}),
                  code("knowledge_context", "核验实际检索来源", CONTRACTS + '\nAUDIENCE = ' + repr(kind) + '\n' + KB_CONTEXT,
                       {"records": ["knowledge", "result"], "query": ["sanitize", "query"]},
                       {"context_json": "string"}, 1850),
                  llm("knowledge_llm", "依据已核验资料回答", KNOWLEDGE, "{{#knowledge_context.context_json#}}", 2150),
                  code("knowledge_validate", "引用白名单及无依据兜底", CONTRACTS + KB_VALIDATE,
                       {"raw": ["knowledge_llm", "text"], "context_json": ["knowledge_context", "context_json"],
                        "output_json": ["sanitize", "output_json"]}, {"output_json": "string"}, 2450),
                  end("end_knowledge", "knowledge_validate", 2750)]
        links += [("sanitize", "knowledge_gate", "source"), ("knowledge_gate", "knowledge", "true"),
                  ("knowledge_gate", "end", "false"), ("knowledge", "knowledge_context", "source"),
                  ("knowledge_context", "knowledge_llm", "source"), ("knowledge_llm", "knowledge_validate", "source"),
                  ("knowledge_validate", "end_knowledge", "source")]
    else:
        nodes.append(end("end", "sanitize", 1250))
        links.append(("sanitize", "end", "source"))
    result = {"app": {"name": {"visitor": "WF_VISITOR", "assessment": "WF_ASSESSMENT",
                              "enterprise": "WF_ENTERPRISE", "student": "WF_STUDENT"}[kind],
                    "description": "Dify 1.12.1：工作室直接绑定模型与知识库；意图/草稿受控，后端鉴权执行",
                    "mode": "workflow", "icon": "📋", "icon_type": "emoji",
                    "icon_background": "#E4FBCC", "use_icon_as_answer_icon": False},
            "dependencies": [{"type": "marketplace", "value": {"marketplace_plugin_unique_identifier": PLUGIN, "version": None}}],
            "kind": "app", "version": "0.5.0", "workflow": {
                "conversation_variables": [], "environment_variables": [],
                "features": {"opening_statement": "", "suggested_questions": [],
                             "suggested_questions_after_answer": {"enabled": False},
                             "speech_to_text": {"enabled": False}, "text_to_speech": {"enabled": False},
                             "sensitive_word_avoidance": {"enabled": False}, "retriever_resource": {"enabled": bool(knowledge)},
                             "file_upload": {"enabled": False, "image": {"enabled": False,
                                             "number_limits": 3, "transfer_methods": ["local_file", "remote_url"]}}},
                "graph": {"nodes": nodes, "edges": graph_edges(nodes, links), "viewport": {"x": 0, "y": 0, "zoom": 0.5}}}}
    if studio_dsl:
        originals = {n["id"]: n["data"] for n in studio_dsl["workflow"]["graph"]["nodes"]}
        result["app"] = {**studio_dsl["app"], "description": result["app"]["description"]}
        result["dependencies"] = copy.deepcopy(studio_dsl.get("dependencies", result["dependencies"]))
        for n in nodes:
            original = originals.get(n["id"], {})
            if n["data"]["type"] == "llm" and original.get("model"):
                n["data"]["model"] = copy.deepcopy(original["model"])
                n["data"]["model"]["completion_params"]["temperature"] = 0.1
            if n["data"]["type"] == "knowledge-retrieval" and original.get("dataset_ids"):
                for field in ("dataset_ids", "retrieval_mode", "multiple_retrieval_config", "single_retrieval_config",
                              "metadata_filtering_mode", "metadata_filtering_conditions"):
                    if field in original:
                        n["data"][field] = copy.deepcopy(original[field])
    return result


def write(kind):
    path = ROOT / "dify" / FILES[kind]
    original = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None
    path.write_text("# Generated by tools/build_dify_workflows.py; Dify 1.12.1 / DSL 0.5.0.\n"
                    "# 知识库在工作室直接选择；保留已有绑定，不依赖项目中的知识库 UUID/开关。\n"
                    + yaml.dump(build(kind, original), Dumper=ReadableDumper, allow_unicode=True, sort_keys=False, width=110), encoding="utf-8")


def main():
    for kind in FILES:
        write(kind)
    build_m5("m5_report_assistant.yml", ASSISTANT_PREPARE, ASSISTANT_VALIDATE, ASSISTANT_PROMPT,
             "Dify 1.12.1：普通日报多轮收集与后端核实查询；确认提交由项目页面执行")
    build_m5("m5_report_generation.yml", REPORT_PREPARE, REPORT_VALIDATE, REPORT_PROMPT,
             "Dify 1.12.1：六类报告正文整理；指标、范围、数据说明由后端核定并保留")
    print("Built all six Dify 1.12.1 workflows.")


if __name__ == "__main__":
    main()
