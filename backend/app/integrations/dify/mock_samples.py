"""
Dify 离线样本（dify_mode=mock）

用途：并行开发/测试阶段不依赖真实 Dify，返回**确定性**且**不编造事实**的结构化输出。
     所有样本与 live 模式共用同一输出契约，接上 key 切 live 即可。

⚠️ 两条底线：
  1. 不编造公司政策、项目条件、年龄/语言/资金门槛、医疗结论；
     资料不足时明确说"资料不足，请转人工/补充资料"。
  2. 只做字段提取与证据定位，**不做录取判定**（判定由 Python 按已审核规则执行）。
"""
from __future__ import annotations

import re

# ---------------- 访客客服（WF_VISITOR）----------------

_OUT_OF_SCOPE_PATTERNS = (
    "导出客户", "客户名单", "客户库", "导出数据", "所有客户", "数据库导出",
    "哪些客户", "客户有哪些", "已签约", "签约客户", "客户资料", "客户信息",
    "员工手机号", "顾问手机号", "接口文档", "系统提示词", "prompt",
)

_LEAD_PATTERNS = ("留资", "留个电话", "留下联系方式", "联系我", "预约", "咨询顾问", "加微信")
_EVENT_PATTERNS = ("报名", "讲座", "说明会", "宣讲", "见面会", "活动")

_MOBILE_RE = re.compile(r"1[3-9]\d{9}")

# 只做最保守的姓名提取：必须出现"我叫/我是/姓名是"等引导词
_NAME_RE = re.compile(r"(?:我叫|我是|姓名是?|名字是?|叫我)\s*([\u4e00-\u9fa5A-Za-z]{2,8})")
_NAME_STOPWORDS = {"学生", "家长", "咨询", "留学", "本人", "自己", "一个", "想了解"}


def _match_any(text: str, words: tuple[str, ...]) -> bool:
    low = text.lower()
    return any(w.lower() in low for w in words)


def _extract_name(text: str) -> str | None:
    """保守提取姓名：无引导词或命中停用词就返回 None（宁缺勿错）。"""
    m = _NAME_RE.search(text)
    if not m:
        return None
    name = m.group(1)
    return None if name in _NAME_STOPWORDS else name


def visitor_answer(payload: dict) -> dict:
    """确定性 VISITOR_ANSWER：公开问答 / 留资草稿 / 活动意向 / 越界拒绝。"""
    message = str(payload.get("message") or "")
    projects = payload.get("public_projects") or []
    events = payload.get("open_events") or []

    # ① 越界请求（提示词注入/索取客户库）→ 明确拒绝，且不返回任何客户明细
    if _match_any(message, _OUT_OF_SCOPE_PATTERNS):
        return {
            "schema_version": "1.0",
            "mode": "VISITOR_ANSWER",
            "intent": "OUT_OF_SCOPE",
            "answer": "抱歉，我只能介绍已公开发布的项目与活动信息，不能提供任何客户资料或内部数据。"
                      "如需帮助请留言，我们会安排顾问与您联系。",
            "draft": None,
            "missing_fields": [],
            "sources": [],
            "warnings": ["OUT_OF_SCOPE_REQUEST"],
        }

    # ② 活动意向：命中活动关键词，且能对上已开放活动
    if _match_any(message, _EVENT_PATTERNS):
        mobile = _MOBILE_RE.search(message)
        hit = None
        for ev in events:
            title = str(ev.get("title") or "")
            if title and title in message:
                hit = ev
                break
        draft = {"event_id": hit.get("id") if hit else None,
                 "name": _extract_name(message),
                 "mobile": mobile.group(0) if mobile else None}
        missing = [f for f in ("name", "mobile") if not draft.get(f)]
        if hit:
            answer = f"已为您准备「{hit.get('title')}」的报名草稿，确认姓名与手机号后即可提交。"
        else:
            answer = "已为您准备活动报名草稿，请确认想参加的活动并填写姓名与手机号。"
        return {
            "schema_version": "1.0",
            "mode": "VISITOR_ANSWER",
            "intent": "ACTIVITY_DRAFT",
            "answer": answer,
            "draft": draft,
            "missing_fields": missing,
            "sources": [],
            "warnings": [] if hit else ["EVENT_NOT_SPECIFIED"],
        }

    # ③ 留资意向：命中留资关键词或直接给了手机号/姓名
    mobile = _MOBILE_RE.search(message)
    name = _extract_name(message)
    if mobile or name or _match_any(message, _LEAD_PATTERNS):
        draft = {"name": name, "mobile": mobile.group(0) if mobile else None}
        missing = [f for f in ("name", "mobile") if not draft.get(f)]
        return {
            "schema_version": "1.0",
            "mode": "VISITOR_ANSWER",
            "intent": "LEAD_DRAFT",
            "answer": "好的，已为您准备留资草稿。确认姓名和手机号后提交，顾问会与您联系。",
            "draft": draft,
            "missing_fields": missing,
            "sources": [],
            "warnings": [],
        }

    # ④ 公开问答：只用 payload 里的已发布项目事实，缺资料明确说不足
    if projects:
        names = [str(p.get("name")) for p in projects[:3] if p.get("name")]
        answer = ("目前可公开了解的项目有：" + "、".join(names) +
                  "。以上为公开发布信息，具体申请条件请以顾问核对后的书面说明为准。")
        sources = [{"document_id": None, "title": str(p.get("name")),
                    "section": "公开项目信息"} for p in projects[:3] if p.get("name")]
    else:
        answer = "暂无已公开发布的项目资料可供回答，我会把您的问题转给顾问跟进。"
        sources = []

    return {
        "schema_version": "1.0",
        "mode": "VISITOR_ANSWER",
        "intent": "FAQ",
        "answer": answer,
        "draft": None,
        "missing_fields": [],
        "sources": sources,
        "warnings": [] if projects else ["INSUFFICIENT_KNOWLEDGE"],
    }


# ---------------- 企业助手（WF_ENTERPRISE）----------------

_E_NAME = re.compile(r"(?:客户|姓名|名字|叫)\s*([\u4e00-\u9fa5A-Za-z]{2,8})")
_E_ID = re.compile(r"(?:#|编号|id)\s*(\d+)", re.IGNORECASE)
_E_NUM = re.compile(r"(\d+)")


def _ent_text(payload: dict) -> str:
    return str(payload.get("message") or "")


def enterprise_output(payload: dict) -> dict:
    """确定性企业助手输出：意图 + 参数 + 草稿；不执行写操作。"""
    text = _ent_text(payload)
    mobile = _MOBILE_RE.search(text)
    name_match = _E_NAME.search(text)
    name = name_match.group(1) if name_match else None
    id_match = _E_ID.search(text)
    rid = int(id_match.group(1)) if id_match else None

    def out(intent: str, *, params=None, draft=None, missing=None, answer=""):
        return {
            "schema_version": "1.0",
            "intent": intent,
            "action": None,
            "params": params or {},
            "draft": draft,
            "missing_fields": missing or [],
            "answer": answer,
            "sources": [],
            "warnings": [],
        }

    # 写意图优先
    if _match_any(text, ("建客户", "新增客户", "录入客户", "新建客户")):
        draft = {"name": name, "mobile": mobile.group(0) if mobile else None}
        missing = [k for k, v in (("name", name), ("mobile", mobile)) if not v]
        return out("LEAD_CREATE", draft=draft, missing=missing,
                   answer="已准备客户草稿，请核对后确认。")

    if _match_any(text, ("流失", "恢复跟进")):
        target = "LOST" if "流失" in text else "FOLLOWING"
        return out("LEAD_CHANGE_STATUS",
                   params={"lead_id": rid, "keyword": name,
                           "target_status": target, "reason": text},
                   answer="请确认客户状态变更。")

    if _match_any(text, ("记个跟进", "写跟进", "记录跟进", "跟进一下", "加一条跟进")):
        return out("FOLLOWUP_ADD",
                   params={"lead_id": rid, "keyword": name},
                   draft={"content": text}, answer="请确认跟进内容。")

    if "请假" in text and _match_any(text, ("批准", "同意", "驳回", "审批")):
        decision = "APPROVE" if _match_any(text, ("批准", "同意")) else "REJECT"
        return out("LEAVE_DECIDE",
                   params={"service_id": rid, "decision": decision, "note": text},
                   answer="请确认审批结果。")

    if _match_any(text, ("解决", "处理")) and _match_any(text, ("工单", "投诉", "售后")):
        return out("FEEDBACK_HANDLE",
                   params={"ticket_id": rid, "action": "RESOLVE",
                           "note": text, "resolution": text},
                   answer="请确认售后处理结果。")

    if _match_any(text, ("关怀", "心理")) and _match_any(text, ("记录", "跟进", "说明")):
        return out("PSYCH_NOTE",
                   params={"alert_id": rid, "note": text},
                   answer="请确认关怀跟进说明。")

    if _match_any(text, ("推进", "更新")) and _match_any(text, ("进度", "申请", "文书", "签证")):
        return out("APPLICATION_UPDATE",
                   params={"case_no": None, "event_kind": "DETAIL", "detail": text},
                   answer="请确认进度更新。")

    # 读意图
    if _match_any(text, ("跟进记录", "跟进历史")):
        return out("FOLLOWUP_LIST", params={"lead_id": rid, "keyword": name})

    if _match_any(text, ("查客户", "找客户", "客户详情", "客户列表", "查一下客户")):
        return out("LEAD_SEARCH", params={"keyword": name})

    if _match_any(text, ("待办", "今天要做什么", "有什么要处理")):
        return out("TODO_LIST")

    if _match_any(text, ("申请列表", "待审", "待审批")):
        return out("SERVICE_LIST", params={"status": "PENDING"})

    if _match_any(text, ("售后", "投诉", "工单")) and not _match_any(text, ("解决", "处理")):
        return out("FEEDBACK_LIST", params={"assignee": "pool"})

    if _match_any(text, ("心理", "关怀", "预警")):
        return out("PSYCH_LIST")

    if _match_any(text, ("申请进度", "进度", "文书", "签证", "院校")):
        return out("APPLICATION_SEARCH", params={"student_name": name})

    if _match_any(text, ("签约", "统计", "多少个", "几个", "多少", "趋势")):
        metric = "SIGNED_COUNT" if "签约" in text else "LEAD_COUNT"
        time_range = "THIS_MONTH" if "本月" in text else (
            "THIS_WEEK" if "本周" in text else "THIS_MONTH")
        return out("METRIC_QUERY", params={"metric": metric, "time_range": time_range})

    if _match_any(text, ("组织", "通讯录", "同事", "部门")):
        return out("ORG_SEARCH")

    if "日报" in text:
        return out("DAILY_SEARCH")

    if _match_any(text, ("入职", "制度", "流程", "新人", "规章")):
        return out("KNOWLEDGE",
                   answer="目前员工知识库暂无相关制度文档，资料不足，请联系行政确认。",
                   )

    return out("OTHER", answer="我可以帮你查客户、跟进、待办、审批、售后和申请进度。")


# ---------------- 客户研判（WF_ASSESSMENT）----------------

_EDUCATION_ORDER = ("硕士", "本科", "大专", "专科", "中专", "职高", "高中", "初中")
_LANGUAGE_KEYWORDS = ("雅思", "IELTS", "托福", "TOEFL", "德福", "TestDaF",
                      "歌德", "日语", "JLPT", "多邻国", "Duolingo", "德语")
_SCORE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(分|分以上)?")
_DATE_RE = re.compile(r"(19\d{2}|20\d{2})\s*[-/年]\s*(\d{1,2})\s*[-/月]\s*(\d{1,2})")

# 提取时要求的必填画像字段（缺失即列入 missing_fields，由顾问补充核对）
_REQUIRED_PROFILE_FIELDS = ("education", "language_level", "date_of_birth")


def _evidence(field: str, line_no: int, line: str) -> dict:
    return {"field": field, "source_ref": f"resume:p{line_no}", "snippet": line.strip()[:120]}


def assessment_extract(payload: dict) -> dict:
    """确定性 ASSESSMENT_EXTRACT：只做字段提取 + 证据定位 + 缺项，不做录取判定。"""
    facts: dict = dict(payload.get("confirmed_facts") or {})
    resume_text = str(payload.get("resume_text") or "")
    warnings: list[str] = []
    evidence: list[dict] = []

    if not resume_text.strip():
        warnings.append("NO_RESUME_TEXT")
        missing = [f for f in _REQUIRED_PROFILE_FIELDS if not facts.get(f)]
        return {
            "schema_version": "1.0",
            "mode": "ASSESSMENT_EXTRACT",
            "facts": facts,
            "evidence": [],
            "missing_fields": missing,
            "warnings": warnings,
        }

    lines = resume_text.splitlines()

    # ① 学历：取文档中最高一档（只提取，不判断是否达标）
    if not facts.get("education"):
        for edu in _EDUCATION_ORDER:
            for idx, line in enumerate(lines, start=1):
                if edu in line:
                    facts["education"] = edu
                    evidence.append(_evidence("education", idx, line))
                    break
            if facts.get("education"):
                break

    # ② 语言水平：命中关键词时带上相邻分数（若有）
    if not facts.get("language_level"):
        for idx, line in enumerate(lines, start=1):
            if any(k.lower() in line.lower() for k in _LANGUAGE_KEYWORDS):
                score = _SCORE_RE.search(line)
                facts["language_level"] = (score.group(1) if score else "已提及") + \
                    ("分" if score else "")
                evidence.append(_evidence("language_level", idx, line))
                break

    # ③ 出生日期：仅做格式提取
    if not facts.get("date_of_birth"):
        for idx, line in enumerate(lines, start=1):
            m = _DATE_RE.search(line)
            if m:
                facts["date_of_birth"] = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
                evidence.append(_evidence("date_of_birth", idx, line))
                break

    missing = [f for f in _REQUIRED_PROFILE_FIELDS if not facts.get(f)]
    if missing:
        warnings.append("NEEDS_MANUAL_CONFIRMATION")

    return {
        "schema_version": "1.0",
        "mode": "ASSESSMENT_EXTRACT",
        "facts": facts,
        "evidence": evidence,
        "missing_fields": missing,
        "warnings": warnings,
    }
