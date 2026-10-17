"""Dify is the only live model channel. DEMO is explicitly labelled deterministic code."""
import json
import logging
import re
import httpx
from app.schemas.m5_report_schemas import DailyContent
from app.repositories.m5_report_repository import today

CATEGORIES={"交付":"DELIVERY","入学":"ENROLLMENT","心理":"PSYCH","投诉":"COMPLAINT","请假":"LEAVE","客户":"CUSTOMER","接待":"CUSTOMER","跟进":"CUSTOMER"}

def parse_json_output(text):
    raw=str(text).strip()
    # DeepSeek may prefix the answer with a complete reasoning block.
    raw=re.sub(r"^<think>[\s\S]*?</think>\s*", "", raw, count=1).strip()
    if raw.startswith("~~~") or raw.startswith("~~~json"):
        raw=re.sub(r"^~~~(?:json)?\s*|\s*~~~$","",raw)
    if raw.startswith(chr(96)*3):
        raw=re.sub(r"^"+chr(96)*3+r"(?:json)?\s*|\s*"+chr(96)*3+"$","",raw)
    value=json.loads(raw)
    if not isinstance(value,dict):
        raise ValueError("Expected object")
    return value

def workflow(settings,key,payload,uid):
    if not key:
        raise ValueError("未配置Dify应用密钥")
    final=None
    model_text=None
    failures=[]
    with httpx.Client(timeout=settings.ai_timeout) as client:
        with client.stream("POST",settings.dify_base+"/workflows/run",
            headers={"Authorization":"Bearer "+key},
            json={"inputs":{"payload_json":json.dumps(payload,ensure_ascii=False)},
                  "response_mode":"streaming","user":"m5-report-"+str(uid)}) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.startswith("data:"):
                    continue
                event=json.loads(line[5:].strip())
                kind=event.get("event")
                data=event.get("data",{})
                if kind=="error":
                    raise ValueError("Dify运行失败")
                if kind=="node_finished":
                    if data.get("status")=="succeeded" and data.get("node_id")=="llm":
                        model_text=data.get("outputs",{}).get("text")
                    if data.get("status") in {"failed","exception"}:
                        failures.append(data)
                if kind=="workflow_finished":
                    final=data
                    break
    if final and final.get("status")=="succeeded" and not failures:
        return parse_json_output(final["outputs"]["output_json"])
    raise ValueError("Dify工作流未成功或响应不完整")


def number(text):
    m=re.search(r"(\d+|[一二两三四五六七八九十]+)\s*(?:个|名|位|条|件|人|次)",text)
    if not m:return 1
    token=m[1]
    return int(token) if token.isdigit() else {"一":1,"二":2,"两":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10}.get(token,1)

def collect_demo(message,state,student_id=None):
    draft=dict(state)
    content=DailyContent.model_validate(draft.get("content",{})).model_dump()
    if re.search(r"^(重新开始|新日报|清空草稿)",message):
        content=DailyContent().model_dump()
    elif "困难" in message or "支持" in message or (draft.get("awaiting")=="difficulties" and message.strip() in {"无","没有","没有困难","无困难"}):
        content["difficulties"]=message.strip()
    elif "明日" in message or "明天" in message:
        content["next_plan"]=message.strip()
    else:
        fragments=[s.strip() for s in re.split(r"[，。；;\n]",message) if s.strip()]
        for fragment in fragments:
            category=next((v for k,v in CATEGORIES.items() if k in fragment),"OTHER")
            content["items"].append({"category":category,"description":fragment,"count":number(fragment),
                "student_ids":[student_id] if student_id else [],"source_event_id":None,"result":""})
        content["work_summary"]="；".join(i["description"] for i in content["items"])
    missing=[]
    if not content["work_summary"]: missing.append("work_summary")
    if not content["difficulties"].strip():missing.append("difficulties")
    answer=("请描述今天完成的工作。" if "work_summary" in missing else "今天是否遇到困难或需要协助？没有可以回复“无”。") if missing else "必要信息已齐全，日报草稿已整理。请打开“我的日报”检查后提交；明日计划可选填。"
    draft.update(content=content,awaiting=missing[0] if missing else None)
    return {"answer":answer,"draft":draft,"missing_fields":missing,"ai_status":"MOCK","warnings":["规则演示，尚未调用Dify"]}

def collect(settings,message,state,uid,history,student_id=None):
    if settings.ai_mode=="DEMO":
        return collect_demo(message,state,student_id)
    if settings.ai_mode=="DISABLED":
        return {"answer":"AI未启用，请在日报表单填写。","draft":state,"missing_fields":[],"ai_status":"UNAVAILABLE","warnings":["AI_DISABLED"]}
    try:
        result=workflow(settings,settings.assistant_key,{"task":"DAILY_COLLECT","content_policy":"日报仅普通工作，禁止心理原文、投诉明细和专项事件引用","message":message,
            "draft":state.get("content",{}),"history":history[-10:],"selected_student_ids":[student_id] if student_id else [],
            "report_date":state.get("report_date",today().isoformat())},uid)
        content=DailyContent.model_validate(result["content"]).model_dump()
        missing=[]
        if not content["work_summary"].strip():missing.append("work_summary")
        if not content["difficulties"].strip():missing.append("difficulties")
        return {"answer":str(result["answer"]),"draft":{**state,"content":content,"awaiting":missing[0] if missing else None},
                "missing_fields":missing,"ai_status":"LIVE","warnings":[]}
    except (httpx.HTTPError,ValueError,KeyError,TypeError):
        return {"answer":"Dify暂不可用，请在日报页面手动填写，或稍后重试。","draft":state,
                "missing_fields":[],"ai_status":"UNAVAILABLE","warnings":["本次未生成AI草稿，原有内容已保留"]}
