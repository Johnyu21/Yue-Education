"""Dify is the only live model channel. DEMO is explicitly labelled deterministic code."""
import json
import re
import httpx
from app.schemas.m5_report_schemas import DailyContent
from app.repositories.m5_report_repository import today

CATEGORIES={"交付":"DELIVERY","入学":"ENROLLMENT","心理":"PSYCH","投诉":"COMPLAINT","请假":"LEAVE","客户":"CUSTOMER","接待":"CUSTOMER","跟进":"CUSTOMER"}

def chat(settings,key,inputs,query,uid):
    """调用 Chat 版应用（advanced-chat），返回 answer 文本。"""
    if not key:
        raise ValueError("未配置Dify应用密钥")
    r=httpx.post(settings.dify_base+"/chat-messages",
        headers={"Authorization":"Bearer "+key},
        json={"inputs":inputs,"query":query,"response_mode":"blocking",
              "conversation_id":"","user":"m5-report-"+str(uid)},
        timeout=settings.ai_timeout)
    r.raise_for_status()
    data=r.json()
    answer=data.get("answer")
    if not isinstance(answer,str):
        raise ValueError("Chat 应用未返回 answer")
    return answer


def extract_json(answer):
    """从 Chat 版 answer 提取结构化 JSON（[[JSON:{...}]] 或纯 JSON）。"""
    raw=str(answer or "").strip()
    raw=re.sub(r"^<think>[\s\S]*?</think>\s*","",raw,count=1).strip()
    idx=raw.find("[[JSON:")
    if idx!=-1:
        start=raw.find("{",idx)
        if start!=-1:
            try:
                value,_=json.JSONDecoder().raw_decode(raw[start:])
                if isinstance(value,dict):
                    return value
            except json.JSONDecodeError:
                pass
    if raw.startswith("{"):
        value=json.loads(raw)
        if isinstance(value,dict):
            return value
    raise ValueError("无法从 answer 提取 JSON 对象")


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
        inputs={"task":"DAILY_COLLECT",
            "draft_json":json.dumps(state.get("content",{}),ensure_ascii=False),
            "history_json":json.dumps(history[-10:],ensure_ascii=False),
            "selected_student_ids_json":json.dumps([student_id] if student_id else [],ensure_ascii=False),
            "report_date":state.get("report_date",today().isoformat())}
        result=extract_json(chat(settings,settings.assistant_key,inputs,message,uid))
        content=DailyContent.model_validate(result["content"]).model_dump()
        missing=[]
        if not content["work_summary"].strip():missing.append("work_summary")
        if not content["difficulties"].strip():missing.append("difficulties")
        return {"answer":str(result["answer"]),"draft":{**state,"content":content,"awaiting":missing[0] if missing else None},
                "missing_fields":missing,"ai_status":"LIVE","warnings":[]}
    except (httpx.HTTPError,ValueError,KeyError,TypeError):
        return {"answer":"Dify暂不可用，请在日报页面手动填写，或稍后重试。","draft":state,
                "missing_fields":[],"ai_status":"UNAVAILABLE","warnings":["本次未生成AI草稿，原有内容已保留"]}


def generate_report(settings,key,report_type,start_date,end_date,scope,metrics,facts,warnings,uid):
    """调用 Chat 版报告生成应用，返回 narrative 正文。"""
    if not key:
        raise ValueError("未配置Dify应用密钥")
    inputs={"report_type":report_type,"start_date":start_date,"end_date":end_date,"scope":scope,
        "metrics_json":json.dumps(metrics,ensure_ascii=False),
        "facts_json":json.dumps(facts,ensure_ascii=False),
        "warnings_json":json.dumps(warnings,ensure_ascii=False)}
    result=extract_json(chat(settings,key,inputs,"请生成报告正文。",uid))
    narrative=result.get("narrative")
    if not isinstance(narrative,str) or not narrative.strip():
        raise ValueError("Empty narrative")
    return narrative


def query(settings,key,message,verified_answer,report_date,uid):
    """调用 Chat 版日报助手 QUERY，仅用于确认 live 状态，不消费返回。"""
    if not key:
        raise ValueError("未配置Dify应用密钥")
    inputs={"task":"QUERY","verified_answer":verified_answer,"report_date":report_date}
    chat(settings,key,inputs,message,uid)
