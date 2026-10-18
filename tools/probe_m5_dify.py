"""Show only configuration presence; --live tests configured Dify apps with synthetic data."""
import json
import sys
import re
from pathlib import Path
from unittest.mock import patch
import httpx
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.services.m5_report_config import get_m5_settings
from app.integrations.dify.m5_report_ai import workflow
from app.schemas.m5_report_schemas import DailyContent


def main():
    settings = get_m5_settings()
    print("M5_AI_MODE=" + settings.ai_mode)
    print("DIFY_BASE=" + ("CONFIGURED" if urlparse(settings.dify_base).netloc else "MISSING"))
    print("ASSISTANT_KEY=" + ("CONFIGURED" if settings.assistant_key else "MISSING"))
    print("REPORT_KEY=" + ("CONFIGURED" if settings.report_key else "MISSING"))
    if "--live" not in sys.argv:
        return 0
    if settings.ai_mode != "DIFY":
        print("LIVE_PROBE=SKIPPED (M5 mode does not enable live Dify)")
        return 1
    from datetime import datetime
    from zoneinfo import ZoneInfo
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    cases = [
        ("DAILY_COLLECT", settings.assistant_key, {"task": "DAILY_COLLECT", "message": "整理公开活动资料2次，没有困难。",
            "content_policy": "普通日报，不收集专项明细", "draft": {}, "history": [],
            "selected_student_ids": [], "report_date": today}),
        ("QUERY", settings.assistant_key, {"task": "QUERY", "message": "合成验收有多少人", "verified_answer": "合成验收新增客户0人。",
            "scope": "合成验收范围", "report_date": today}),
        ("REPORT_GENERATE", settings.report_key, {"task": "REPORT_GENERATE", "type": "DAILY_DAY", "start_date": today,
            "end_date": today, "scope": "合成验收范围", "metrics": [],
            "facts": [{"section": "普通工作", "text": "整理公开活动资料；仅合成验收资料。"}], "warnings": ["仅合成验收资料"]}),
    ]
    failed = False
    evidence = []
    replay = {}
    def trace(response):
        response.read()
        for line in response.text.splitlines():
            if not line.startswith("data:"):
                continue
            try:
                event = json.loads(line[5:].strip())
            except ValueError:
                print("TRACE invalid SSE JSON")
                continue
            data = event.get("data", {})
            if event.get("event") in {"workflow_finished", "node_finished", "error"}:
                entry = {"event": event.get("event"), "status": data.get("status"), "node_id": data.get("node_id")}
                error = data.get("error") or event.get("message")
                if error:
                    error = str(error)
                    for secret in (settings.assistant_key, settings.report_key):
                        if secret:
                            error = error.replace(secret, "<REDACTED>")
                    error = re.sub(r"https?://\S+|app-[\w-]+|sk-[\w-]+|Bearer\s+\S+", "<REDACTED>", error)
                    entry["error"] = error[:800]
                outputs = data.get("outputs")
                if isinstance(outputs, dict):
                    entry["output_fields"] = sorted(outputs)
                    if data.get("node_id") == "llm":
                        raw = outputs.get("text", "")
                        if isinstance(raw, str):
                            entry.update(text_length=len(raw), finish_reason=outputs.get("finish_reason"),
                                starts_json=raw.lstrip().startswith("{"),
                                starts_fence=raw.lstrip().startswith(("```", "~~~")),
                                starts_think=raw.lstrip().startswith("<think>"),
                                first_object_offset=raw.find("{"))
                            if "--replay-local" in sys.argv:
                                try:
                                    from check_m5_dify_contract import run_node, ASSISTANT, REPORT
                                    app = REPORT if name == "REPORT_GENERATE" else ASSISTANT
                                    prepared = run_node(app, "prepare", payload_json=json.dumps(payload, ensure_ascii=False))
                                    replayed = json.loads(run_node(app, "validate", raw=raw,
                                        normalized_json=prepared["normalized_json"])["output_json"])
                                    if name == "DAILY_COLLECT":
                                        DailyContent.model_validate(replayed["content"])
                                    replay[name] = "PASS"
                                except Exception as replay_error:
                                    replay[name] = "FAIL " + type(replay_error).__name__
                                entry["local_new_dsl_replay"] = replay[name]
                    if "output_json" in outputs:
                        try:
                            obj = json.loads(outputs["output_json"]) if isinstance(outputs["output_json"], str) else outputs["output_json"]
                            entry["output_json_fields"] = sorted(obj) if isinstance(obj, dict) else type(obj).__name__
                        except ValueError:
                            entry["output_json_format"] = "INVALID_JSON"
                print("TRACE " + json.dumps(entry, ensure_ascii=True))
                if event.get("event") == "workflow_finished":
                    evidence.append({"task": name, "workflow_run_id": event.get("workflow_run_id") or data.get("id"),
                        "status": data.get("status"), "failed_node": "validate" if "JSONDecodeError" in str(error) else None,
                        "error_kind": "JSONDecodeError" if "JSONDecodeError" in str(error) else type(error).__name__ if error else None,
                        "local_new_dsl_replay": replay.get(name)})
    original_client = httpx.Client
    def client(*args, **kwargs):
        if any(flag in sys.argv for flag in ("--trace", "--replay-local", "--save-evidence")):
            kwargs["event_hooks"] = {"response": [trace]}
        return original_client(*args, **kwargs)
    for name, key, payload in cases:
        try:
            with patch.object(httpx, "Client", client):
                result = workflow(settings, key, payload, "synthetic-contract-check")
            if name == "DAILY_COLLECT":
                DailyContent.model_validate(result["content"])
                if not isinstance(result.get("answer"), str) or not result["answer"].strip():
                    raise ValueError("Missing answer")
                for item in result["content"].get("items", []):
                    if item.get("category") in {"PSYCH", "COMPLAINT"} or item.get("source_event_id") or item.get("student_ids"):
                        raise ValueError("Invalid ordinary daily")
            elif name == "REPORT_GENERATE":
                if not isinstance(result.get("narrative"), str) or not result["narrative"].strip():
                    raise ValueError("Missing narrative")
            elif result.get("answer") != payload["verified_answer"]:
                raise ValueError("Query changed backend verified facts")
            print(name + "=PASS")
        except Exception as error:
            # Do not print URLs, request headers, keys, or remote response bodies.
            status = getattr(getattr(error, "response", None), "status_code", None)
            print(name + "=FAIL " + type(error).__name__ + (" HTTP " + str(status) if status else ""))
            failed = True
    if "--save-evidence" in sys.argv:
        from datetime import timezone
        target = ROOT / "docs" / "fixtures" / "m5_dify_live_probe.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"checked_at": datetime.now(timezone.utc).isoformat(),
            "data_kind": "synthetic_only", "mode": settings.ai_mode, "runs": evidence}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("Saved redacted run evidence to docs/fixtures/m5_dify_live_probe.json")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
