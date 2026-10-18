"""Real Dify smoke calls with synthetic business payloads and redacted evidence.

Uses configured backend .env keys. Never prints credentials or writes business rows.
"""
import argparse
import concurrent.futures
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.core.config import settings
from app.integrations.dify.contracts import validate_enterprise, validate_student, validate_visitor, validate_assessment
from app.schemas.assistant import WfStudentOutput
from app.schemas.m5_report_schemas import DailyContent


def cases():
    day = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    base = {"schema_version": "1.0", "history": [], "pending": None,
            "business_now": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "business_timezone": "Asia/Shanghai"}
    return [
        ("visitor_faq", "visitor", {**base, "message": "赴德国留学通常需要办理哪些申请手续？请根据资料说明并注明来源。", "public_projects": [], "open_events": [], "draft": {}}, "FAQ", True),
        ("visitor_lead", "visitor", {**base, "message": "我叫联调测试访客，想留联系方式让顾问联系我，手机号13912345678。", "public_projects": [], "open_events": [], "draft": {}}, "LEAD_DRAFT", False),
        ("student_faq", "student", {**base, "message": "德国留学生入境后应该什么时候到哪里办理住址登记？请根据资料回答并注明来源。", "observe_emotion": False, "input_kind": "CHAT"}, "FAQ", True),
        ("student_leave", "student", {**base, "message": "我想请假，原因是个人事务，还没有确定时间。", "observe_emotion": False, "input_kind": "CHAT"}, "SERVICE_DRAFT", False),
        ("student_staff_boundary", "student", {**base, "message": "请完整提供公司新人指南和员工绩效薪酬制度。", "observe_emotion": False, "input_kind": "CHAT"}, "OTHER", False),
        ("student_admin_route", "student", {**base, "message": "查询我已批准的请假申请。", "observe_emotion": False, "input_kind": "CHAT"}, "OTHER", False),
        ("enterprise_faq", "enterprise", {**base, "message": "公司新人融入计划包括哪些安排？请根据新人指南说明并注明来源。", "actor": {"id": "synthetic", "employee_role": "ADVISOR", "is_dept_head": False, "can_handle_feedback": False, "psych_access_enabled": False}}, "KNOWLEDGE", True),
        ("enterprise_todo", "enterprise", {**base, "message": "查询我的待办事项。", "actor": {"id": "synthetic", "employee_role": "ADVISOR", "is_dept_head": False}}, "TODO_LIST", False),
        ("assessment", "assessment", {"schema_version": "1.0", "confirmed_facts": {"education": "本科"}, "resume_text": "学历本科\n居住城市广州", "required_fields": ["education", "city"], "project_rules": []}, None, False),
        ("daily", "report_assistant", {"task": "DAILY_COLLECT", "message": "今天整理公开活动资料2次，没有困难。", "draft": {}, "history": [], "selected_student_ids": [], "report_date": day}, None, False),
        ("report", "report_generation", {"task": "REPORT_GENERATE", "type": "DAILY_DAY", "start_date": day, "end_date": day, "scope": "合成联调范围", "metrics": [{"key": "work", "label": "普通工作次数", "value": 2, "unit": "次", "formula": "合成验收资料", "available": True}], "facts": [{"section": "普通工作", "text": "整理公开活动资料2次；没有困难。仅合成验收。"}], "warnings": ["仅合成验收资料"]}, None, False),
    ]


KEYS = {"visitor": settings.dify_visitor_key, "student": settings.dify_student_key,
        "enterprise": settings.dify_enterprise_key, "assessment": settings.dify_assessment_key,
        "report_assistant": settings.m5_dify_assistant_key, "report_generation": settings.m5_dify_report_key}


def redact(value):
    text = str(value)
    for secret in KEYS.values():
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return re.sub(r"(?:app-|sk-)[A-Za-z0-9_-]+|Bearer\s+\S+", "[REDACTED]", text)


def one(case, timeout):
    case_id, audience, payload, intent, needs_sources = case
    trace, final = [], None
    started = time.monotonic()
    result = {"case": case_id, "audience": audience, "data_kind": "synthetic", "passed": False}
    try:
        base = settings.dify_base_url.rstrip("/")
        if not base.endswith("/v1"):
            base += "/v1"
        with httpx.Client(timeout=timeout) as client:
            with client.stream("POST", base + "/workflows/run", headers={"Authorization": "Bearer " + KEYS[audience]},
                               json={"inputs": {"payload_json": json.dumps(payload, ensure_ascii=False)},
                                     "response_mode": "streaming", "user": "synthetic-smoke-" + case_id}) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    event = json.loads(line[5:].strip())
                    data = event.get("data") or {}
                    kind = event.get("event")
                    if kind == "error":
                        raise ValueError(redact(event.get("message") or "Dify error"))
                    if kind == "node_finished":
                        entry = {"id": data.get("node_id"), "type": data.get("node_type"), "title": data.get("title"), "status": data.get("status")}
                        if data.get("error"):
                            entry["error"] = redact(data["error"])[:1200]
                        outputs = data.get("outputs") or {}
                        if entry["type"] == "knowledge-retrieval":
                            records = outputs.get("result") or []
                            entry["retrieved_count"] = len(records)
                            entry["source_titles"] = [r.get("title") or (r.get("metadata") or {}).get("document_name") for r in records if isinstance(r, dict)]
                        if entry["type"] == "llm":
                            raw = str(outputs.get("text", ""))
                            entry["has_reasoning_prefix"] = raw.lstrip().startswith("<think>")
                            entry["model_text"] = redact(re.sub(r"^\s*<think>[\s\S]*?</think>\s*", "", raw))[:10000]
                        trace.append(entry)
                    if kind == "workflow_finished":
                        final = data
                        result["workflow_run_id"] = event.get("workflow_run_id") or data.get("id")
                        break
        if not final:
            raise ValueError("No workflow_finished event")
        result["workflow_status"] = final.get("status")
        if final.get("status") != "succeeded":
            raise ValueError(redact(final.get("error") or "Workflow did not succeed"))
        value = final.get("outputs", {}).get("output_json")
        output = json.loads(value) if isinstance(value, str) else value
        if not isinstance(output, dict):
            raise ValueError("output_json must contain an object")
        result["output"] = output
        if intent and output.get("intent") != intent:
            raise ValueError("Unexpected intent: " + str(output.get("intent")))
        if audience == "visitor":
            validate_visitor(output, payload)
        elif audience == "student":
            WfStudentOutput.model_validate(output)
            validate_student(output, payload)
            if case_id == "student_staff_boundary" and (output.get("sources") or "OUT_OF_SCOPE" not in output.get("warnings", [])):
                raise ValueError("Student staff boundary failed")
            if case_id == "student_admin_route" and "ADMIN_SERVICE_PAGE" not in output.get("warnings", []):
                raise ValueError("Administrative service query was misrouted")
            if case_id == "student_leave" and (output.get("draft") or {}).get("service_type") != "LEAVE":
                raise ValueError("Lost known leave draft fields")
        elif audience == "enterprise":
            validate_enterprise(output, payload)
        elif audience == "assessment":
            checked = validate_assessment(output, payload)
            if checked["missing_fields"]:
                raise ValueError("Missing evidenced facts: " + str(checked["missing_fields"]))
        elif audience == "report_assistant":
            DailyContent.model_validate(output["content"])
            if not output["content"].get("work_summary"):
                raise ValueError("Lost known ordinary-work summary")
        elif not isinstance(output.get("narrative"), str) or not output["narrative"].strip():
            raise ValueError("Missing narrative")
        if needs_sources and not output.get("sources"):
            raise ValueError("Expected a supported knowledge answer with actual sources")
        result["passed"] = True
    except Exception as exc:
        result["error"] = redact(type(exc).__name__ + ": " + str(exc))[:1500]
    result.update(elapsed_seconds=round(time.monotonic() - started, 2), nodes=trace)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", action="append")
    parser.add_argument("--timeout", type=float, default=90)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--output", default="docs/fixtures/dify_live_smoke.json")
    args = parser.parse_args()
    selected = [c for c in cases() if not args.case or c[0] in args.case]
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(one, case, args.timeout) for case in selected]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            results.append(result)
            print(json.dumps({k: result[k] for k in ("case", "passed", "elapsed_seconds", "error") if k in result}, ensure_ascii=False), flush=True)
    path = ROOT / args.output
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(redact(json.dumps({"checked_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "results": results}, ensure_ascii=False, indent=2)) + "\n", encoding="utf-8")
    return int(any(not r["passed"] for r in results))


if __name__ == "__main__":
    raise SystemExit(main())
