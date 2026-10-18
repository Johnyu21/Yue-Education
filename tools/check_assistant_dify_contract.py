"""Offline contract/graph/orchestration checks; never connects to DB or Dify.

Run: backend/.venv/Scripts/python.exe tools/check_assistant_dify_contract.py
Synthetic responses validate the framework, not real model/KB accuracy.
"""
import ast
import copy
import json
import re
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.core import runtime_state
from app.core.confirmation import sign_confirmation, verify_confirmation
from app.core.errors import AIBadResponseError, InvalidRequestError, ForbiddenError
from app.integrations.dify import contracts as c
from app.integrations.dify.client import DifyClient
from app.schemas.assistant import AssistantRequest, AssistantResult, Proposal
from app.schemas.assistant_enterprise import ALLOWED_INTENTS
from app.services import assistant_session as sessions, enterprise_assistant_service as employee, student_assistant_service as student


def output(intent, **kwargs):
    return {"schema_version": "1.0", "intent": intent, "answer": "合成回复", "draft": None,
            "missing_fields": [], "sources": [], "warnings": [], **kwargs}


def workflow(name):
    return yaml.safe_load((ROOT / "dify" / name).read_text(encoding="utf-8"))


def run(name, node, **kwargs):
    ns = {}
    code = next(n["data"]["code"] for n in workflow(name)["workflow"]["graph"]["nodes"] if n["id"] == node)
    exec(compile(code, name + ":" + node, "exec"), ns)
    return ns["main"](**kwargs)


class Framework(unittest.TestCase):
    def test_report_router_and_date_ranges(self):
        from datetime import date
        from app.services.m5_assistant_routing import classify, period
        today = date(2026, 10, 18)
        self.assertEqual(classify("今天新增客户3人，没有困难"), "DAILY_COLLECT")
        self.assertEqual(classify("本周新增客户有多少人"), "QUERY")
        self.assertEqual(classify("新增客户有哪些"), "QUERY")
        self.assertEqual(classify("生成客户经营报告"), "REPORT")
        self.assertEqual(period("上周新增客户有多少人", today), (date(2026, 10, 5), date(2026, 10, 11)))
        self.assertEqual(period("生成2026-10-01至2026-10-15的客户报告", today, True), (date(2026, 10, 1), date(2026, 10, 15)))
        for message in ("去年新增客户有多少人", "2026-10-20新增客户有多少人", "2026-99-01", "2026-10-12至2026-10-01"):
            with self.subTest(message=message), self.assertRaises(ValueError):
                period(message, today)

    def test_all_graphs_and_dominating_selectors(self):
        for path in sorted((ROOT / "dify").glob("*.yml")):
            d = workflow(path.name)
            self.assertEqual(d["version"], "0.5.0")
            nodes = {n["id"]: n["data"] for n in d["workflow"]["graph"]["nodes"]}
            parents = {key: set() for key in nodes}
            for edge in d["workflow"]["graph"]["edges"]:
                self.assertIn(edge["source"], nodes)
                self.assertIn(edge["target"], nodes)
                parents[edge["target"]].add(edge["source"])
            dom = {"start": {"start"}}
            while len(dom) < len(nodes):
                progress = False
                for key in nodes.keys() - dom.keys():
                    if parents[key] and parents[key] <= dom.keys():
                        dom[key] = {key} | set.intersection(*(dom[p] for p in parents[key]))
                        progress = True
                self.assertTrue(progress, "Cycle or unreachable node in " + path.name)
            for key, node in nodes.items():
                self.assertIn(node["type"], {"start", "code", "llm", "end", "if-else", "knowledge-retrieval"})
                if node["type"] == "llm":
                    self.assertEqual(node["model"]["provider"], "langgenius/deepseek/deepseek")
                    self.assertEqual(node["model"]["name"], "deepseek-v4-flash")
                if node["type"] == "code":
                    tree = ast.parse(node["code"])
                    for item in ast.walk(tree):
                        if isinstance(item, ast.Import):
                            self.assertTrue(all(a.name in {"json", "re", "datetime"} for a in item.names))
                        if isinstance(item, ast.ImportFrom):
                            self.assertEqual(item.module, "datetime")
                selectors = [v["value_selector"] for v in node.get("variables", []) if "value_selector" in v]
                if node["type"] == "end":
                    selectors += [v["value_selector"] for v in node["outputs"]]
                    self.assertEqual([v["variable"] for v in node["outputs"]], ["output_json"])
                if node["type"] == "knowledge-retrieval":
                    selectors += [node["query_variable_selector"]]
                if node["type"] == "if-else":
                    selectors += [v["variable_selector"] for case in node["cases"] for v in case["conditions"]]
                for p in node.get("prompt_template", []):
                    selectors += [m.split(".") for m in re.findall(r"\{\{#([^#]+)#\}\}", p["text"])]
                for source, field in selectors:
                    self.assertIn(source, dom[key] - {key}, path.name + ":" + key)
                    upstream = nodes[source]
                    available = set(upstream.get("outputs", {})) if upstream["type"] == "code" else set()
                    available |= {v["variable"] for v in upstream.get("variables", []) if "variable" in v}
                    available |= {"llm": {"text"}, "knowledge-retrieval": {"result"}}.get(upstream["type"], set())
                    self.assertIn(field, available)

    def test_invalid_json_is_not_faq(self):
        for raw in ("解释{}", "[]", "", '<think>unfinished', '{"intent":NaN}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                c.object_json(raw)
        self.assertEqual(c.object_json('<think>x</think>```json\n{"x":1}\n```'), {"x": 1})

    def test_all_employee_intents_present(self):
        self.assertEqual(set(c.READ_FIELDS) | set(c.WRITE_FIELDS) | {"KNOWLEDGE", "OTHER"}, ALLOWED_INTENTS)
        prompt = next(n["data"]["prompt_template"][0]["text"] for n in workflow("wf_enterprise.yml")["workflow"]["graph"]["nodes"] if n["id"] == "llm")
        for intent in ALLOWED_INTENTS:
            self.assertIn(intent, prompt)

    def test_employee_required_fields_no_default_approval(self):
        for intent, params, field in [("LEAVE_DECIDE", {"service_id": 4}, "decision"),
            ("FEEDBACK_HANDLE", {"ticket_id": 3, "action": "RESOLVE"}, "resolution"),
            ("FEEDBACK_HANDLE", {"ticket_id": 3, "action": "ASSIGN", "note": "转交"}, "assignee_user_id"),
            ("APPLICATION_UPDATE", {"case_no": str(uuid4()), "event_kind": "STAGE", "detail": "更新"}, "stage")]:
            self.assertIn(field, c.validate_enterprise(output(intent, params=params))["missing_fields"])
        self.assertIsNone(employee._resolve_lead_id(Mock(), Mock(), {}))

    def test_unknown_or_authority_fields_rejected(self):
        for mutation in [output("DELETE_LEAD"), output("LEAD_CREATE", params={}, draft={"owner_user_id": 1}),
                         output("LEAVE_DECIDE", params={"service_id": 2, "decision": "AUTO"}),
                         output("FOLLOWUP_ADD", params={"lead_id": 1}, draft={"content": {"bad": 1}})]:
            with self.subTest(value=mutation), self.assertRaises(ValueError):
                c.validate_enterprise(mutation)

    def test_multiturn_partial_merge_and_target_switch(self):
        old = output("LEAD_CREATE", params={}, draft={"name": "合成客户"})
        value = c.validate_enterprise(output("LEAD_CREATE", params={}, draft={"mobile": "13912345678"}), {"pending": old})
        self.assertEqual(value["draft"]["name"], "合成客户")
        self.assertEqual(value["missing_fields"], [])
        old = output("FOLLOWUP_ADD", params={"lead_id": 2}, draft={"content": "旧客户跟进"})
        value = c.validate_enterprise(output("FOLLOWUP_ADD", params={"lead_id": 3}), {"pending": old})
        self.assertIn("content", value["missing_fields"])

    def test_followup_plan_omission_vs_clear(self):
        self.assertNotIn("next_follow_up_at", c.validate_enterprise(output("FOLLOWUP_ADD", params={"lead_id": 1}, draft={"content": "回访"}))["params"])
        self.assertIsNone(c.validate_enterprise(output("FOLLOWUP_ADD", params={"lead_id": 1, "next_follow_up_at": None}, draft={"content": "回访"}))["params"]["next_follow_up_at"])

    def test_student_conditional_required_fields_and_consent(self):
        value = c.validate_student(output("SERVICE_DRAFT", draft={"service_type": "LEAVE", "title": "请假", "description": "个人事务"}))
        self.assertEqual(set(value["missing_fields"]), {"start_at", "end_at"})
        value = c.validate_student(output("SERVICE_DRAFT", draft={"service_type": "INFO_CHANGE", "title": "更正资料", "description": "更新"}))
        self.assertIn("change_request", value["missing_fields"])
        ob = {"emotion_state": "NEGATIVE", "confidence": 0.7, "direct_signal": True}
        self.assertNotIn("observation", c.validate_student(output("OTHER", observation=ob), {"observe_emotion": False}))
        self.assertFalse(c.validate_student(output("OTHER", observation=ob), {"observe_emotion": True})["observation"]["direct_signal"])

    def test_student_info_change_partial_old_and_new_values(self):
        previous = output("SERVICE_DRAFT", draft={"service_type": "INFO_CHANGE", "title": "资料更正", "description": "更正城市", "change_request": {"old_values": {"city": "旧城市"}}})
        value = c.validate_student(output("SERVICE_DRAFT", draft={"change_request": {"new_values": {"city": "新城市"}}}), {"pending": previous})
        self.assertEqual(value["missing_fields"], [])
        self.assertEqual(value["draft"]["change_request"]["old_values"], {"city": "旧城市"})

    def test_visitor_partial_contact_is_not_asked_twice(self):
        value = c.validate_visitor(output("LEAD_DRAFT", draft={"mobile": "13912345678"}), {"draft": {"name": "合成访客"}})
        self.assertEqual(value["missing_fields"], [])
        self.assertEqual(value["draft"]["name"], "合成访客")

    def test_feedback_and_upgrade_fields(self):
        value = c.validate_student(output("FEEDBACK_DRAFT", draft={"category": "COMPLAINT", "content": "合成反馈"}))
        self.assertIn("teacher_name", value["missing_fields"])
        self.assertIn("project_category", value["missing_fields"])
        with self.assertRaises(ValueError):
            c.validate_student(output("FEEDBACK_DRAFT", draft={"priority": "HIGH"}))
        self.assertEqual(c.validate_student(output("UPGRADE_INTEREST", draft={"course_project_id": 2}))["missing_fields"], [])

    def test_visitor_closed_event_and_field_whitelist(self):
        value = c.validate_visitor(output("ACTIVITY_DRAFT", draft={"event_id": 4, "name": "合成访客", "mobile": "13912345678"}), {"open_events": [{"id": "5"}]})
        self.assertIn("event_id", value["missing_fields"])
        self.assertNotIn("event_id", value["draft"])
        with self.assertRaises(ValueError):
            c.validate_visitor(output("LEAD_DRAFT", draft={"name": "访客", "dept_id": 7}))

    def test_assessment_evidence_and_confirmed_facts(self):
        payload = {"resume_text": "\n学历本科\n城市广州", "confirmed_facts": {"education": "硕士"}, "required_fields": ["education", "city"]}
        raw = {"schema_version": "1.0", "mode": "ASSESSMENT_EXTRACT", "facts": {"education": "本科", "city": "广州", "language_level": "C2"},
               "evidence": [{"field": "education", "source_ref": "resume:p2", "snippet": "学历本科"},
                            {"field": "city", "source_ref": "resume:p3", "snippet": "城市广州"}]}
        value = c.validate_assessment(raw, payload)
        self.assertEqual(value["facts"], {"education": "硕士", "city": "广州"})
        self.assertIn("CONFIRMED_FACT_CONFLICT:education", value["warnings"])
        self.assertEqual(value["missing_fields"], [])
        raw["evidence"][1]["source_ref"] = "resume:p99"
        self.assertIn("city", c.validate_assessment(raw, payload)["missing_fields"])

    def test_studio_kb_route_does_not_block_business(self):
        for name, intent, extra in [("wf_entry.yml", "LEAD_DRAFT", {"draft": {"name": "合成访客"}}),
            ("wf_enterprise.yml", "TODO_LIST", {"params": {}}), ("wf_student.yml", "SCORE_QUERY", {})]:
            prepared = run(name, "prepare", payload_json=c.dump({"message": "合成请求"}))
            value = run(name, "sanitize", raw=c.dump(output(intent, **extra)), **prepared)
            self.assertEqual(value["knowledge_route"], "skip")
            self.assertNotIn("KB_NOT_CONFIGURED", c.object_json(value["output_json"])["warnings"])
        value = run("wf_student.yml", "sanitize", raw=c.dump(output("FAQ")), normalized_json=c.dump({"message": "服务规则"}))
        self.assertEqual(value["knowledge_route"], "enabled")
        self.assertNotIn("KB_NOT_CONFIGURED", c.object_json(value["output_json"])["warnings"])

    def test_kb_sources_real_metadata_only(self):
        import build_dify_workflows as builder
        dataset_id = "11111111-1111-4111-8111-111111111111"
        d = builder.build("student")
        ns = {}
        code = next(n["data"]["code"] for n in d["workflow"]["graph"]["nodes"] if n["id"] == "knowledge_context")
        exec(code, ns)
        records = [{"content": "合成规则", "metadata": {"dataset_id": dataset_id, "document_id": "d1", "document_name": "学生规则", "segment_id": "s1"}},
                   {"content": "伪造来源，缺少文档标识", "metadata": {"dataset_id": dataset_id}}]
        context = ns["main"](records=records, query="合成问题")["context_json"]
        self.assertEqual(len(c.object_json(context)["records"]), 1)
        args = {"context_json": context, "output_json": c.dump(output("FAQ"))}
        value = run("wf_student.yml", "knowledge_validate", raw=c.dump({"answer": "合成规则答复", "citation_ids": ["1"]}), **args)
        self.assertEqual(c.object_json(value["output_json"])["sources"][0]["document_id"], "d1")
        with self.assertRaises(ValueError):
            run("wf_student.yml", "knowledge_validate", raw=c.dump({"answer": "编造", "citation_ids": ["99"]}), **args)
        value = run("wf_student.yml", "knowledge_validate", raw=c.dump({"answer": "无依据", "citation_ids": []}), **args)
        self.assertEqual(c.object_json(value["output_json"])["sources"], [])

    def test_studio_bindings_and_model_are_preserved(self):
        import build_dify_workflows as builder
        original = workflow("wf_student.yml")
        updated = builder.build("student", studio_dsl=original)
        before = {n["id"]: n["data"] for n in original["workflow"]["graph"]["nodes"]}
        after = {n["id"]: n["data"] for n in updated["workflow"]["graph"]["nodes"]}
        self.assertEqual(before["knowledge"]["dataset_ids"], after["knowledge"]["dataset_ids"])
        self.assertEqual(before["knowledge"]["multiple_retrieval_config"], after["knowledge"]["multiple_retrieval_config"])
        self.assertEqual(before["llm"]["model"]["name"], after["llm"]["model"]["name"])
        self.assertNotIn("knowledge", builder.CONFIG)

    def test_student_has_no_staff_dataset_or_staff_answer(self):
        data = {n["id"]: n["data"] for n in workflow("wf_student.yml")["workflow"]["graph"]["nodes"]}
        staff = {n["id"]: n["data"] for n in workflow("wf_enterprise.yml")["workflow"]["graph"]["nodes"]}
        self.assertTrue(data["knowledge"]["dataset_ids"])
        self.assertTrue(set(data["knowledge"]["dataset_ids"]).isdisjoint(staff["knowledge"]["dataset_ids"]))
        value = c.validate_student(output("OTHER", warnings=["OUT_OF_SCOPE"]))
        self.assertEqual(value["sources"], [])
        self.assertIn("不提供员工内部资料", value["answer"])
        value = c.validate_student(output("OTHER", warnings=["ADMIN_SERVICE_PAGE"]))
        self.assertIn("行政服务页面", value["answer"])

    def test_workflow_status_must_explicitly_succeed(self):
        for status in (None, "failed", "stopped", "running", "partial-succeeded"):
            response = Mock(status_code=200)
            response.json.return_value = {"data": {"outputs": {"output_json": "{}"}, "status": status}}
            with patch("app.integrations.dify.client.httpx.post", return_value=response), self.assertRaises(AIBadResponseError):
                DifyClient("http://synthetic.invalid").run_workflow("synthetic", {}, "synthetic")


class BackendOrchestration(unittest.TestCase):
    def setUp(self):
        self.store = {}
        self.stack = []
        def get(key): return copy.deepcopy(self.store.get(key))
        def put(key, value, ttl=900, merge=False):
            self.store[key] = {**self.store.get(key, {}), **copy.deepcopy(value)} if merge else copy.deepcopy(value)
        def compare_put(key, value, revision, ttl=900):
            if self.store.get(key, {}).get("revision") != revision:
                return False
            put(key, value, ttl)
            return True
        for name, fn in [("get", get), ("put", put), ("compare_put", compare_put), ("drop", lambda key: self.store.pop(key, None))]:
            p = patch.object(runtime_state, name, side_effect=fn)
            p.start()
            self.addCleanup(p.stop)
        self.actor = SimpleNamespace(id=71, is_employee=True)

    def req(self, text="合成消息", conversation="offline-conversation"):
        return AssistantRequest(message_id=uuid4(), conversation_id=conversation, message=text)

    def test_state_isolation_and_explicit_cancel(self):
        req = self.req()
        key, state = sessions.begin("enterprise", 71, req)
        wf = output("LEAD_CREATE", params={}, draft={"name": "合成姓名"})
        result = AssistantResult(messageId=str(req.message_id), answer="补手机号", missingFields=["mobile"])
        sessions.finish(key, state, req, wf, result)
        self.assertEqual(sessions.context(sessions.begin("enterprise", 71, req)[1])["pending"]["draft"]["name"], "合成姓名")
        self.assertIsNone(sessions.context(sessions.begin("enterprise", 72, req)[1])["pending"])
        self.assertIsNone(sessions.context(sessions.begin("student", 71, req)[1])["pending"])
        self.assertIsNone(sessions.context(sessions.begin("enterprise", 71, self.req("取消"))[1])["pending"])

    def test_old_card_revoked_after_new_message(self):
        req = self.req()
        key, state = sessions.begin("enterprise", self.actor.id, req)
        rk = str(uuid4())
        token = sign_confirmation(self.actor, "CREATE_LEAD", entity_id=None, payload={"name": "合成"}, expected_version=None, request_key=rk)
        result = AssistantResult(messageId=str(req.message_id), answer="核对", proposal=Proposal(operation="CREATE_LEAD", confirmationToken=token))
        result = sessions.finish(key, state, req, output("LEAD_CREATE", draft={"name": "合成"}), result)
        kwargs = dict(operation="CREATE_LEAD", entity_id=None, payload={"name": "合成"}, request_key=rk)
        verify_confirmation(self.actor, result.proposal.confirmationToken, **kwargs)
        sessions.begin("enterprise", self.actor.id, self.req("改一下"))
        with self.assertRaises(InvalidRequestError):
            verify_confirmation(self.actor, result.proposal.confirmationToken, **kwargs)

    def test_late_result_cannot_overwrite_new_draft(self):
        req = self.req()
        key, old = sessions.begin("student", 1, req)
        sessions.begin("student", 1, req)
        with self.assertRaises(InvalidRequestError):
            sessions.finish(key, old, req, None, AssistantResult(messageId=str(req.message_id), answer="迟到回复"))

    def test_selection_continues_pending_write_and_uses_current_version(self):
        req = self.req("2")
        pending = output("FOLLOWUP_ADD", params={"keyword": "同名"}, draft={"content": "已电话回访"})
        employee._cache_put("71:" + req.conversation_id, "lead", [101, 102], pending)
        lead = SimpleNamespace(name="合成客户", version=9)
        with patch.object(employee.crm_service, "get_lead", return_value=lead), patch.object(employee, "run_enterprise_workflow") as model:
            out = employee.handle_enterprise_message(Mock(), self.actor, req)
        model.assert_not_called()
        self.assertEqual(out.proposal.operation, "ADD_FOLLOWUP")
        self.assertEqual(out.proposal.entityId, "102")
        self.assertEqual(out.proposal.expectedVersion, 9)
        self.assertEqual(out.proposal.preview["content"], "已电话回访")

    def test_detail_keeps_only_selected_id_for_followup_reference(self):
        wf = employee.WfEnterpriseOutput(**c.validate_enterprise(output("LEAD_DETAIL", params={"lead_id": 101})))
        state = {}
        dto = SimpleNamespace(name="合成客户", status="FOLLOWING", mobileMasked="139****5678", education="本科", city="广州", ownerDisplayName="合成员工", nextFollowUpAt=None)
        with patch.object(employee.crm_service, "get_lead", return_value=dto):
            employee._handle_read(Mock(), self.actor, self.req(), wf, state)
        self.assertEqual(sessions.context(state)["candidates"], [{"kind": "lead", "id": "101"}])
        self.assertNotIn("合成客户", c.dump(state))

    def test_employee_partial_draft_reaches_next_model_call(self):
        actor = SimpleNamespace(id=71, is_employee=True, real_name="合成员工", employee_role="ADVISOR", dept_id=1,
                                can_handle_feedback=False, psych_access_enabled=False)
        responses = [output("LEAD_CREATE", params={}, draft={"name": "合成客户"}), output("LEAD_CREATE", params={}, draft={"mobile": "13912345678"})]
        with patch.object(employee, "_is_head", return_value=False), patch.object(employee, "run_enterprise_workflow", side_effect=responses) as model:
            first = employee.handle_enterprise_message(Mock(), actor, self.req("新增客户合成客户"))
            second = employee.handle_enterprise_message(Mock(), actor, self.req("手机号13912345678"))
        self.assertIn("mobile", first.missingFields)
        self.assertEqual(second.proposal.operation, "CREATE_LEAD")
        self.assertEqual(model.call_args.args[0]["pending"]["draft"]["name"], "合成客户")
        self.assertEqual(second.proposal.preview["name"], "合成客户")

    def test_signed_leave_approval_reaches_verified_state_change(self):
        from app.services import student_service
        from app.schemas.service import ServiceDecisionRequest
        svc = SimpleNamespace(id=2, status="PENDING", version=1, service_type="LEAVE",
                              handling_history=[], submitted_by_user_id=8, title="合成请假")
        req = ServiceDecisionRequest(decision="APPROVE", note="合成审批意见", expected_version=1,
                                     request_key=uuid4(), confirmation_token="synthetic")
        with patch.object(student_service.service_repo, "get_service", return_value=svc), \
             patch.object(student_service, "_check_decider_permission"), \
             patch.object(student_service, "verify_confirmation") as verify, \
             patch.object(student_service, "notify"), \
             patch.object(student_service, "_service_to_dto", return_value=svc):
            student_service.decide_service.__wrapped__(Mock(), self.actor, 2, req)
        self.assertEqual(verify.call_args.kwargs["payload"], {"decision": "APPROVE", "note": "合成审批意见"})
        self.assertEqual(svc.status, "APPROVED")
        self.assertEqual(svc.version, 2)

    def test_student_missing_leave_dates_cannot_get_confirmation_card(self):
        actor = SimpleNamespace(id=8, is_student=True)
        profile = SimpleNamespace(psych_consent_status="DENIED")
        value = output("SERVICE_DRAFT", draft={"service_type": "LEAVE", "title": "合成请假", "description": "个人事务"})
        with patch.object(student.student_repo, "get_profile_by_user", return_value=profile), \
             patch.object(student, "call_student_workflow", return_value=value), \
             patch.object(student, "_open_projects", return_value=[]):
            result = student.handle_student_message(Mock(), actor, self.req())
        self.assertIsNone(result.proposal)
        self.assertEqual(set(result.missingFields), {"start_at", "end_at"})

    def test_student_multiturn_submission_preview(self):
        actor = SimpleNamespace(id=8, is_student=True)
        profile = SimpleNamespace(psych_consent_status="DENIED")
        responses = [output("SERVICE_DRAFT", draft={"service_type": "LEAVE", "title": "合成请假", "description": "个人事务"}),
                     output("SERVICE_DRAFT", draft={"start_at": "2026-10-20T09:00:00+08:00", "end_at": "2026-10-20T12:00:00+08:00"})]
        with patch.object(student.student_repo, "get_profile_by_user", return_value=profile), \
             patch.object(student, "call_student_workflow", side_effect=responses), \
             patch.object(student, "_open_projects", return_value=[]):
            student.handle_student_message(Mock(), actor, self.req("请假"))
            result = student.handle_student_message(Mock(), actor, self.req("20号9点至12点"))
        self.assertEqual(result.proposal.operation, "SUBMIT_SERVICE")
        self.assertEqual(result.proposal.preview["title"], "合成请假")

    def test_info_change_approval_needs_business_form(self):
        wf = employee.WfEnterpriseOutput(**c.validate_enterprise(output("LEAVE_DECIDE", params={"service_id": 7, "decision": "APPROVE", "note": "核对"})))
        with patch.object(employee.student_service, "get_service", return_value=SimpleNamespace(serviceType="INFO_CHANGE", title="更名", version=3)):
            result = employee._handle_write(Mock(), self.actor, self.req(), wf)
        self.assertIsNone(result.proposal)
        self.assertIn("IDENTITY_VERIFICATION_REQUIRED", result.warnings)


if __name__ == "__main__":
    unittest.main(verbosity=2)
