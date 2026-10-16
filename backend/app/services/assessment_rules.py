"""
项目准入规则判定（确定性）—— M2

⚠️ 职责边界（对齐 02/01 文档）：
  - Dify 只做**字段提取 + 证据定位 + 解释**；
  - **匹配结论（MATCH/NO_MATCH/NEEDS_INFO）与分数（score）由本模块按
    course_project.admission_rules（必须已审核）确定性计算**；
  - 规则缺失/未审核 → NEEDS_INFO 且 score 为 null，**绝不编造门槛或分数**。

admission_rules 契约（M2 与项目维护方约定）：
{
  "version": "v1",
  "criteria": [
    {"field": "education",       "op": "IN",       "values": ["本科","硕士"], "label": "学历要求"},
    {"field": "language_level",  "op": "GTE_NUM",  "value": 6.0,               "label": "语言成绩"},
    {"field": "city",            "op": "EXISTS",                                "label": "需填写城市"}
  ],
  "scoring": [
    {"field": "education", "weights": {"大专": 20, "本科": 30, "硕士": 40}}
  ]
}

op 取值：EQ / IN / GTE / LTE / GTE_NUM / EXISTS
score：仅当 scoring 存在**且**规则已审核时才计算；否则为 null。
"""
from __future__ import annotations

import logging
import re

from app.models.course_project import CourseProject

logger = logging.getLogger(__name__)

NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")

# 判定结果
DECISION_MATCH = "MATCH"
DECISION_NO_MATCH = "NO_MATCH"
DECISION_NEEDS_INFO = "NEEDS_INFO"


def _as_number(value) -> float | None:
    """从任意值里取数字：接受 int/float/str（如 "6.5分"）。"""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    m = NUMBER_RE.search(str(value))
    return float(m.group(0)) if m else None


def _check_one(criterion: dict, facts: dict) -> str:
    """返回 PASS / FAIL / MISSING。"""
    field = criterion.get("field")
    op = str(criterion.get("op") or "EXISTS").upper()
    if not field:
        return "MISSING"

    value = facts.get(field)

    if op == "EXISTS":
        return "PASS" if value not in (None, "", []) else "MISSING"

    if value in (None, ""):
        return "MISSING"

    if op == "EQ":
        return "PASS" if str(value) == str(criterion.get("value")) else "FAIL"

    if op == "IN":
        allowed = [str(v) for v in (criterion.get("values") or [])]
        return "PASS" if str(value) in allowed else "FAIL"

    if op in ("GTE", "LTE", "GTE_NUM"):
        actual = _as_number(value)
        expected = _as_number(criterion.get("value"))
        if actual is None or expected is None:
            return "MISSING"                 # 无法比较：不给结论
        if op == "GTE" or op == "GTE_NUM":
            return "PASS" if actual >= expected else "FAIL"
        return "PASS" if actual <= expected else "FAIL"

    logger.warning("未知规则运算符 %s，按 MISSING 处理", op)
    return "MISSING"


def evaluate_project(project: CourseProject, facts: dict) -> dict:
    """按已审核规则判定单个项目。

    ⚠️ 规则缺失、未审核、或 criteria 为空 → 一律 NEEDS_INFO，
       并把 approved_project_rules 列入缺项（前端显示"评分规则未配置"）。
    """
    rules = project.admission_rules if isinstance(project.admission_rules, dict) else None
    needs_rules = {
        "projectId": str(project.id),
        "projectName": project.name,
        "decision": DECISION_NEEDS_INFO,
        "passedRules": [],
        "failedRules": [],
        "missingFields": ["approved_project_rules"],
        "ruleVersion": project.rule_version,
    }

    if not rules or project.rule_approved_at is None:
        # 未配置或未审核 → 不作自动判定（缺信息可补）
        return needs_rules

    criteria = rules.get("criteria") or []
    if not isinstance(criteria, list) or not criteria:
        return needs_rules

    passed: list[str] = []
    failed: list[str] = []
    missing: list[str] = []

    for criterion in criteria:
        if not isinstance(criterion, dict):
            continue
        label = str(criterion.get("label") or criterion.get("field") or "规则")
        result = _check_one(criterion, facts)
        if result == "PASS":
            passed.append(label)
        elif result == "FAIL":
            failed.append(label)
        else:
            missing.append(str(criterion.get("field")))

    if failed:
        # 已明确不满足硬性条件 → 结论确定
        decision = DECISION_NO_MATCH
    elif missing:
        decision = DECISION_NEEDS_INFO
    else:
        decision = DECISION_MATCH

    return {
        "projectId": str(project.id),
        "projectName": project.name,
        "decision": decision,
        "passedRules": passed,
        "failedRules": failed,
        "missingFields": missing,
        "ruleVersion": project.rule_version,
    }


def compute_score(project: CourseProject, facts: dict) -> int | None:
    """按已批准权重算 0~100 分；无权重/缺输入 → None（不显示 0 分）。"""
    rules = project.admission_rules if isinstance(project.admission_rules, dict) else None
    if not rules or project.rule_approved_at is None:
        return None

    scoring = rules.get("scoring")
    if not isinstance(scoring, list) or not scoring:
        return None

    total = 0.0
    for item in scoring:
        if not isinstance(item, dict):
            continue
        field = item.get("field")
        weights = item.get("weights") or {}
        value = facts.get(field)
        if value in (None, "") or str(value) not in {str(k) for k in weights}:
            # 缺输入或未覆盖的取值 → 不能给出貌似精确的分数
            return None
        weight = weights.get(str(value))
        if weight is None:
            return None
        try:
            total += float(weight)
        except (TypeError, ValueError):
            return None

    return max(0, min(100, int(round(total))))


def build_report(projects: list[CourseProject], facts: dict, *,
                 evidence: list[dict], extraction_missing: list[str],
                 warnings: list[str], request_id: str) -> tuple[dict, int | None]:
    """生成研判报告 + 总评分。

    ⚠️ 打分口径（防止"貌似精确的分数"）：
       只有当**每个项目都能给出确定结论**（MATCH / NO_MATCH，不存在 NEEDS_INFO）
       且都能算出分数时，才给出总分；否则一律为 null。

    Returns:
        (report, score)
    """
    results = [evaluate_project(p, facts) for p in projects]

    has_undecided = any(r["decision"] == DECISION_NEEDS_INFO for r in results)
    scores = [compute_score(p, facts) for p in projects]
    usable = [s for s in scores if s is not None]
    score = (max(usable)
             if not has_undecided and usable and len(usable) == len(scores)
             else None)

    rule_versions = {p.rule_version for p in projects}
    rule_version = rule_versions.pop() if len(rule_versions) == 1 else None

    missing = sorted({m for r in results for m in r["missingFields"]} | set(extraction_missing))

    report = {
        "schema_version": "1.0",
        "ruleVersion": rule_version,
        "projects": results,
        "score": score,
        "facts": facts,
        "evidence": evidence,
        "missingFields": missing,
        "warnings": warnings,
        # 便于排查"是哪次请求产出的"，也用于过时任务比对
        "assessedForRequestId": request_id,
    }
    return report, score
