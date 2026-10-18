r"""Offline regression checks for the actual M5 DSL code and backend adapter.

Run from the repository root:
    backend\.venv\Scripts\python.exe tools\check_m5_dify_contract.py
No database connection, model call, or real credentials are used.
"""
import copy
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.integrations.dify import m5_report_ai as ai
from app.schemas.m5_report_schemas import DailyContent
from app.services.m5_report_service import validate_content


def node(app, name):
    dsl = yaml.safe_load((ROOT / "dify" / (app + ".yml")).read_text(encoding="utf-8"))
    return next(n["data"] for n in dsl["workflow"]["graph"]["nodes"] if n["id"] == name)


def run_node(app, name, **inputs):
    namespace = {}
    exec(compile(node(app, name)["code"], app + ":" + name, "exec"), namespace)
    return namespace["main"](**inputs)


ASSISTANT = "m5_report_assistant"
REPORT = "m5_report_generation"
CONTENT = {"work_summary": "跟进客户2次", "items": [{"category": "CUSTOMER",
    "description": "跟进客户", "count": 2, "student_ids": [],
    "source_event_id": None, "result": "待回复"}], "difficulties": "无", "next_plan": ""}
DAILY = {"task": "DAILY_COLLECT", "content_policy": "日报仅普通工作",
    "message": "没有困难", "draft": CONTENT, "history": [],
    "selected_student_ids": [], "report_date": "2026-10-18"}
PAYLOAD = {"task": "REPORT_GENERATE", "type": "DAILY_WEEK", "start_date": "2026-10-12",
    "end_date": "2026-10-18", "scope": "本人 · 合成部门",
    "metrics": [{"key": "daily_coverage", "label": "审核通过覆盖率", "value": None,
                 "unit": "%", "formula": "分母为零时无值", "available": True}],
    "facts": [{"section": "困难与支持", "text": "无"}], "warnings": ["合成验收资料"]}


def validate(app, raw, payload):
    data = node(app, "validate")
    arguments = {"raw": json.dumps(raw, ensure_ascii=False)}
    # Also runs against the old single-input validator to demonstrate the regression.
    if any(v["variable"] == "normalized_json" for v in data["variables"]):
        arguments["normalized_json"] = json.dumps(payload, ensure_ascii=False)
    return json.loads(run_node(app, "validate", **arguments)["output_json"])


class ContractTests(unittest.TestCase):
    def test_unknown_work_count_is_not_defaulted(self):
        content = copy.deepcopy(CONTENT)
        content["items"][0].pop("count")
        with self.assertRaises(ValueError):
            validate(ASSISTANT, {"answer": "草稿", "content": content}, DAILY)

    def test_concrete_question_and_specialist_redirect_preserved(self):
        value = validate(ASSISTANT, {"answer": "草稿", "next_question": "客户回访具体进行了几次？", "specialist_redirect": True, "content": CONTENT}, DAILY)
        self.assertIn("几次", value["answer"])
        self.assertIn("专项模块", value["answer"])

    def test_model_wrappers_and_invalid_json(self):
        raw = json.dumps({"narrative": "合成事实整理"}, ensure_ascii=False)
        for wrapper in (raw, "```json\n" + raw + "\n```", "~~~json\n" + raw + "\n~~~",
                        "<think>仅合成推理</think>\n```json\n" + raw + "\n```"):
            prepared = run_node(REPORT, "prepare", payload_json=json.dumps(PAYLOAD))
            result = run_node(REPORT, "validate", raw=wrapper, normalized_json=prepared["normalized_json"])
            self.assertIn("合成事实整理", json.loads(result["output_json"])["narrative"])
        for invalid in ("", "[]", "<think>unfinished", '{"narrative":',
                        '{"narrative":"x","value":NaN}'):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                run_node(REPORT, "validate", raw=invalid, normalized_json=json.dumps(PAYLOAD))

    def test_student_binding_and_draft_input(self):
        content = copy.deepcopy(CONTENT)
        content["items"][0]["student_ids"] = ["synthetic-student"]
        for payload in ({**DAILY, "selected_student_ids": ["synthetic-student"]}, {**DAILY, "draft": content}):
            prepared = run_node(ASSISTANT, "prepare", payload_json=json.dumps(payload))
            output = validate(ASSISTANT, {"answer": "草稿", "content": content}, json.loads(prepared["normalized_json"]))
            self.assertEqual(output["content"]["items"][0]["student_ids"], ["synthetic-student"])

    def test_dsl_graph_and_code(self):
        for app in (ASSISTANT, REPORT):
            dsl = yaml.safe_load((ROOT / "dify" / (app + ".yml")).read_text(encoding="utf-8"))
            self.assertEqual(dsl["app"]["mode"], "workflow")
            nodes = {n["id"]: n["data"] for n in dsl["workflow"]["graph"]["nodes"]}
            self.assertEqual(set(nodes), {"start", "prepare", "llm", "validate", "end"})
            for n in nodes.values():
                self.assertNotEqual(n["type"], "http-request")
                if n["type"] == "code":
                    compile(n["code"], app, "exec")
                for v in n.get("variables", []) + (n.get("outputs", []) if n["type"] == "end" else []):
                    if "value_selector" in v:
                        source, key = v["value_selector"]
                        self.assertIn(source, nodes)
                        outputs = nodes[source].get("outputs", {})
                        keys = {x["variable"] for x in nodes[source].get("variables", [])}
                        self.assertTrue(key in outputs or key in keys or (source == "llm" and key == "text"))
            self.assertEqual([(e["source"], e["target"]) for e in dsl["workflow"]["graph"]["edges"]],
                             [("start", "prepare"), ("prepare", "llm"), ("llm", "validate"), ("validate", "end")])

    def test_ordinary_daily_reaches_backend_validation(self):
        result = validate(ASSISTANT, {"answer": "请核对草稿", "content": CONTENT}, DAILY)
        content = DailyContent.model_validate(result["content"]).model_dump()
        with patch("app.services.m5_report_service.visible_students", return_value=[]):
            validate_content({"_events": []}, content)

    def test_sensitive_items_fail_in_dsl_before_backend_422(self):
        for category in ("PSYCH", "COMPLAINT"):
            content = copy.deepcopy(CONTENT)
            content["items"][0]["category"] = category
            with self.subTest(category=category), self.assertRaises(ValueError):
                validate(ASSISTANT, {"answer": "已整理", "content": content}, DAILY)

    def test_event_reference_rejected(self):
        content = copy.deepcopy(CONTENT)
        content["items"][0]["source_event_id"] = "invented-event"
        with self.assertRaises(ValueError):
            validate(ASSISTANT, {"answer": "草稿", "content": content}, DAILY)

    def test_unknown_student_rejected(self):
        content = copy.deepcopy(CONTENT)
        content["items"][0]["student_ids"] = ["unauthorized"]
        with self.assertRaises(ValueError):
            validate(ASSISTANT, {"answer": "草稿", "content": content}, DAILY)

    def test_schema_and_limits(self):
        for mutation in ({"items": None}, {"work_summary": "x" * 5001}, {"unexpected": True}):
            with self.subTest(mutation=list(mutation)), self.assertRaises(ValueError):
                validate(ASSISTANT, {"answer": "草稿", "content": {**CONTENT, **mutation}}, DAILY)
        for count in (-1, 10001, True, "2"):
            content = copy.deepcopy(CONTENT)
            content["items"][0]["count"] = count
            with self.subTest(count=count), self.assertRaises(ValueError):
                validate(ASSISTANT, {"answer": "草稿", "content": content}, DAILY)

    def test_missing_fields_and_nonempty_answer(self):
        content = {**CONTENT, "work_summary": "", "difficulties": ""}
        result = validate(ASSISTANT, {"answer": "草稿已完成", "content": content}, DAILY)
        self.assertEqual(result["missing_fields"], ["work_summary", "difficulties"])
        self.assertIn("今日工作", result["answer"])
        with self.assertRaises(ValueError):
            validate(ASSISTANT, {"answer": " ", "content": CONTENT}, DAILY)

    def test_query_uses_verified_answer(self):
        query = {"task": "QUERY", "message": "有多少人", "verified_answer": "本期新增0人",
                 "scope": "合成部门", "report_date": "2026-10-18"}
        result = validate(ASSISTANT, {"answer": "新增100人"}, query)
        self.assertEqual(result, {"answer": query["verified_answer"]})

    def test_report_requires_narrative(self):
        for raw in ({"answer": "不是报告正文"}, {"narrative": " "}):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                validate(REPORT, raw, PAYLOAD)

    def test_report_retains_backend_basis_and_strips_write_fields(self):
        result = validate(REPORT, {"narrative": "困难与支持：无。", "metrics": [], "confirmed": True}, PAYLOAD)
        self.assertEqual(set(result), {"narrative"})
        for text in (PAYLOAD["scope"], PAYLOAD["start_date"], PAYLOAD["end_date"],
                     "审核通过覆盖率", "暂无可用值", "合成验收资料"):
            self.assertIn(text, result["narrative"])
        self.assertNotIn("None%", result["narrative"])

    def test_all_six_report_types_and_bad_inputs(self):
        for kind in ("CUSTOMER_OPERATION", "DAILY_DAY", "DAILY_WEEK", "PSYCH_WEEK", "COMPLAINT_WEEK", "MANAGER_WEEK"):
            payload = {**PAYLOAD, "type": kind}
            if kind == "DAILY_DAY":
                payload["start_date"] = payload["end_date"]
            normalized = run_node(REPORT, "prepare", payload_json=json.dumps(payload))
            self.assertEqual(json.loads(normalized["normalized_json"])["type"], kind)
        for app, payload in ((ASSISTANT, {**DAILY, "task": "WRITE"}),
                             (REPORT, {**PAYLOAD, "type": "UNKNOWN"}),
                             (REPORT, {**PAYLOAD, "end_date": "2026-01-01"})):
            with self.subTest(app=app, payload=payload), self.assertRaises(ValueError):
                run_node(app, "prepare", payload_json=json.dumps(payload))

    def test_sse_adapter_and_collect_preserve_multiturn_draft(self):
        output = validate(ASSISTANT, {"answer": "请核对草稿", "content": CONTENT}, DAILY)
        events = [{"event": "workflow_finished", "data": {"status": "succeeded", "outputs": {
            "output_json": json.dumps(output, ensure_ascii=False)}}}]

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def raise_for_status(self): pass
            def iter_lines(self): return iter("data:" + json.dumps(e) for e in events)

        class Client:
            def __init__(self, *args, **kwargs): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def stream(self, *args, **kwargs):
                self.request = kwargs["json"]
                assert self.request["response_mode"] == "streaming"
                assert json.loads(self.request["inputs"]["payload_json"])["task"] == "DAILY_COLLECT"
                return Response()

        settings = SimpleNamespace(ai_mode="DIFY", ai_timeout=1, dify_base="http://example.invalid/v1", assistant_key="synthetic")
        state = {"content": CONTENT, "report_date": "2026-10-18"}
        with patch.object(ai.httpx, "Client", Client):
            result = ai.collect(settings, "没有困难", state, 1, [])
            self.assertEqual(result["ai_status"], "LIVE")
            self.assertEqual(result["draft"]["content"], CONTENT)
            events.clear()
            result = ai.collect(settings, "没有困难", state, 1, [])
            self.assertEqual(result["ai_status"], "UNAVAILABLE")
            self.assertEqual(result["draft"], state)


if __name__ == "__main__":
    unittest.main(verbosity=2)
