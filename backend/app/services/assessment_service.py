"""
客户研判（API041 / API042 / API096）—— M2

流程（对齐 02 文档"AI 事务外、结果按请求号条件回写"）：
  ① 事务内：校验范围/版本 → 写 RUNNING + assessment_request_id + started_at（版本 +1）
  ② **事务外**：抽取简历文本 → 调 Dify 做字段提取（不持有客户行锁）
  ③ 事务内：**条件更新** `WHERE id=? AND assessment_request_id=?` 回写结果；
     请求号被更新的任务自动失效（旧任务不覆盖新结果）；
     失败只保存符号错误码，并保留上一份成功报告（由 API042 标 isPreviousReport）。

判定与打分：`assessment_rules` 按已审核 admission_rules 确定性计算；
      **参与判定的只有"已确认事实"**（客户主档既有事实 ∪ 本次 confirmed_facts），
      AI 提取结果仅作为参考资料与证据，不直接用于判定。
"""
from __future__ import annotations

import logging
import uuid
from copy import deepcopy
from types import SimpleNamespace
from datetime import date, datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import (AIBadResponseError, AITimeoutError, AIUnavailableError,
                             NotFoundError, ValidationError, VersionConflictError)
from app.core.storage import resolve_path
from app.core.transaction import with_business_transaction
from app.integrations.dify import ai_status
from app.integrations.dify.assessment import run_assessment
from app.models.course_project import CourseProject
from app.models.lead import CrmLead
from app.models.user import SysUser
from app.repositories import project as project_repo
from app.schemas.lead import AssessmentIn, ResumeExtractionIn
from app.services import assessment_rules
from app.services.m2_errors import AssessmentRunningError

logger = logging.getLogger(__name__)

# 简历提取草稿（进程内短期缓存；重启即失效，属设计取舍）
_DRAFT_TTL_MINUTES = 60
_drafts: dict[str, tuple[dict, float]] = {}

# 参与判定的客户事实字段
_LEAD_FACT_FIELDS = ("gender", "city", "education", "date_of_birth")

# 画像必填字段（WF_ASSESSMENT 的 required_fields 默认口径，与 mock 共用）
_REQUIRED_PROFILE_FIELDS = ("education", "language_level", "date_of_birth")

# 由其它字段派生、不需要 AI 直接提取的字段
_DERIVED_FIELDS = {"age"}

_MAX_REQUIRED_FIELDS = 12

_MAX_PROJECTS = 20


# ============================================================
# 校验工具
# ============================================================
def _lead_facts(lead: CrmLead) -> dict:
    """客户主档里已经确认过的事实（留资/顾问核对所得）。"""
    facts: dict = {}
    for field in _LEAD_FACT_FIELDS:
        value = getattr(lead, field, None)
        if value in (None, ""):
            continue
        facts[field] = value.isoformat() if isinstance(value, date) else value
    return facts


def _require_resume_path(user: SysUser, object_key: str | None):
    """附件必须属于当前员工（前缀 u/{actor_id}/）且文件存在；否则 404。"""
    if not object_key:
        return None
    if not object_key.startswith(f"u/{user.id}/"):
        # 越权的 object_key 不返回 403，避免暴露他人文件是否存在
        raise NotFoundError("资源不存在")
    path = resolve_path(object_key)
    if path is None:
        raise NotFoundError("资源不存在")
    return path


def _symbol_error_code(exc: Exception) -> str:
    if isinstance(exc, AITimeoutError):
        return "AI_TIMEOUT"
    if isinstance(exc, AIUnavailableError):
        return "AI_UNAVAILABLE"
    if isinstance(exc, AIBadResponseError):
        return "AI_BAD_RESPONSE"
    code = getattr(exc, "code", None)
    if isinstance(code, str) and code.isupper():
        return code
    return "INTERNAL_ERROR"


def _load_projects(db: Session, project_ids: list[int]) -> list[CourseProject]:
    ids = list(dict.fromkeys(project_ids))          # 去重且保序
    if len(ids) > _MAX_PROJECTS:
        raise ValidationError("一次最多研判 20 个项目",
                              errors=[{"field": "project_ids", "reason": "最多 20 个"}])

    projects: list[CourseProject] = []
    for pid in ids:
        project = project_repo.get_by_id(db, pid)
        if project is None:
            raise ValidationError("项目不存在",
                                  errors=[{"field": "project_ids", "reason": f"项目 {pid} 不存在"}])
        projects.append(project)
    return projects


def _rule_fields(node) -> list[str]:
    """收集规则里引用到的字段名（支持 all_of/any_of 嵌套）。"""
    if isinstance(node, dict):
        fields = [node["field"]] if isinstance(node.get("field"), str) else []
        for key in ("all_of", "any_of"):
            for child in node.get(key) or []:
                fields.extend(_rule_fields(child))
        return fields
    if isinstance(node, list):
        fields: list[str] = []
        for item in node:
            fields.extend(_rule_fields(item))
        return fields
    return []


def _required_fields(projects: list[CourseProject]) -> list[str]:
    """送进工作流的必填字段清单：画像默认项 ∪ 已审核规则引用的字段。

    ⚠️ "必填"只在这里定义一次：工作流的 missing_fields 归一到本清单，
       mock 样本也读同一个 payload 字段，live 与 mock 的缺项口径才不会各说一套。
    """
    fields = list(_REQUIRED_PROFILE_FIELDS)
    for project in projects:
        if project.rule_approved_at is None:
            continue
        rules = project.admission_rules if isinstance(project.admission_rules, dict) else None
        if not rules:
            continue
        for field in _rule_fields(rules.get("criteria")):
            if field in _DERIVED_FIELDS or field in fields:
                continue
            fields.append(field)
    return fields[:_MAX_REQUIRED_FIELDS]


def _build_payload(lead: CrmLead, request_id, judgement_facts: dict,
                   resume_text: str | None, projects: list[CourseProject]) -> dict:
    """发送给 Dify 的最小载荷：单个客户的已确认事实 + 简历片段 + 项目规则 + 必填字段。

    ⚠️ 不发整张客户表、不发员工 token、不发其它客户数据。
    ⚠️ project_rules[].rules 在规则未审核时为 null —— 工作流不得据此推断门槛。
    """
    return {
        "schema_version": "1.0",
        "lead_id": str(lead.id),
        "request_id": str(request_id),
        "confirmed_facts": judgement_facts,
        "required_fields": _required_fields(projects),
        "resume_text": resume_text or "",
        "project_rules": [
            {
                "project_id": str(p.id),
                "rule_version": p.rule_version,
                "rules": p.admission_rules if p.rule_approved_at is not None else None,
            }
            for p in projects
        ],
    }


# ============================================================
# API041 启动一次客户研判
# ============================================================
def assess_lead(db: Session, user: SysUser, lead_id: int, data: AssessmentIn) -> dict:
    from app.core.permissions import build_scope       # 局部导入，避免模块级循环

    actor_id=user.id
    scope = build_scope(db, user, "lead")
    lead = scope.get_or_404(db, CrmLead, lead_id)      # 越权一律 404

    resume_path = _require_resume_path(user, data.resume_object_key)
    projects = _load_projects(db, data.project_ids)

    now = datetime.now(timezone.utc)

    # ---- ① 事务内：请求号落库（RUNNING），版本 +1 ----
    with with_business_transaction(db):
        lead = db.get(CrmLead, lead_id, with_for_update=True, populate_existing=True)
        if lead is None or not scope.can_see(lead):raise NotFoundError()
        if lead.version != data.expected_version:
            raise VersionConflictError(lead.version)

        if lead.assessment_status == "RUNNING" and lead.assessment_started_at is not None:
            elapsed = (now - lead.assessment_started_at).total_seconds()
            if elapsed < settings.assessment_reclaim_after_seconds:
                raise AssessmentRunningError("该客户已有研判正在进行中")
            logger.warning("接管超时的研判任务 lead=%s", lead_id)

        lead.assessment_status = "RUNNING"
        lead.assessment_request_id = data.request_key
        lead.assessment_started_at = now
        lead.assessment_error_code = None
        if data.resume_object_key:
            lead.resume_object_key = data.resume_object_key
        lead.version += 1
        db.flush()
        started_version = lead.version
        judgement_facts = {**_lead_facts(lead), **{k:v for k,v in (data.confirmed_facts or {}).items() if v not in (None, "")}}
        projects = [SimpleNamespace(id=p.id,name=p.name,admission_rules=deepcopy(p.admission_rules),rule_version=p.rule_version,rule_approved_at=p.rule_approved_at,version=p.version) for p in projects]
        lead_snapshot = SimpleNamespace(id=lead.id)

    request_id = data.request_key

    # ---- ② 事务外：提取文本 + 调用 Dify ----
    try:
        resume_text = ""
        if resume_path is not None:
            from app.services.resume_extract import extract_text
            resume_text = extract_text(resume_path)


        extraction = run_assessment(
            _build_payload(lead_snapshot, request_id, judgement_facts, resume_text, projects),
            user=str(actor_id),
            timeout_s=settings.ai_timeout_assessment_seconds,
        )
    except Exception as exc:                          # noqa: BLE001 —— 需分类落库后再抛
        code = _symbol_error_code(exc)
        _mark_failed(db, lead_id, request_id, code)
        logger.warning("研判失败 lead=%s code=%s", lead_id, code)
        raise

    # ---- ③ 事务内：按请求号条件回写（旧任务自动失效）----
    report, score = assessment_rules.build_report(
        projects,
        judgement_facts,
        evidence=extraction.get("evidence", []),
        extraction_missing=extraction.get("missing_fields", []),
        warnings=extraction.get("warnings", []),
        request_id=str(request_id),
    )
    report["extraction"] = {                          # AI 提取结果仅供参考，不参与判定
        "facts": extraction.get("facts", {}),
        "mode": extraction.get("mode", "ASSESSMENT_EXTRACT"),
        "schema_version": extraction.get("schema_version", "1.0"),
    }

    with with_business_transaction(db):
        current_user=db.get(SysUser,actor_id,populate_existing=True)
        current_scope=build_scope(db,current_user,"lead")
        current_lead=db.get(CrmLead,lead_id,with_for_update=True,populate_existing=True)
        if current_user.status!="NORMAL" or not current_scope.can_see(current_lead):raise NotFoundError()
        rules_unchanged=all(db.scalar(select(CourseProject.version).where(CourseProject.id==p.id))==p.version for p in projects)
        if not rules_unchanged:
            if current_lead.assessment_request_id==request_id:
                current_lead.assessment_status="FAILED";current_lead.assessment_error_code="RULES_CHANGED";current_lead.version+=1;db.flush()
            return {"assessmentRequestId":str(request_id),"status":"FAILED","leadVersion":current_lead.version,"superseded":True}
        changed = db.execute(
            update(CrmLead)
            .where(CrmLead.id == lead_id, CrmLead.assessment_request_id == request_id, CrmLead.version == started_version)
            .values(
                assessment_status="SUCCEEDED",
                assessment_report=report,
                latest_score=score,
                assessed_at=datetime.now(timezone.utc),
                assessment_error_code=None,
                version=CrmLead.version + 1,
            )
        ).rowcount

        if not changed:
            # 请求号已被更新（有更新的研判接管）→ 本次结果作废，返回当前状态
            logger.info("研判结果作废（请求号已变更）lead=%s", lead_id)
            current = db.get(CrmLead, lead_id)
            if current.assessment_request_id==request_id and current.assessment_status=="RUNNING":
                current.assessment_status="FAILED";current.assessment_error_code="FACTS_CHANGED";current.version+=1;db.flush()
            return {
                "assessmentRequestId": str(current.assessment_request_id)
                if current.assessment_request_id else None,
                "status": current.assessment_status,
                "leadVersion": current.version,
                "superseded": True,
            }

        current = db.get(CrmLead, lead_id)
        result = {
            "assessmentRequestId": str(request_id),
            "status": current.assessment_status,
            "leadVersion": current.version,
        }

    logger.info("研判完成 lead=%s decision=%s score=%s", lead_id,
                [p["decision"] for p in report["projects"]], score)
    logger.info("研判起始版本 %s", started_version)
    return result


def _mark_failed(db: Session, lead_id: int, request_id, code: str) -> None:
    """失败只保存符号错误码，并**保留上一份成功报告**（前端标 isPreviousReport）。"""
    with with_business_transaction(db):
        db.execute(
            update(CrmLead)
            .where(CrmLead.id == lead_id, CrmLead.assessment_request_id == request_id)
            .values(
                assessment_status="FAILED",
                assessment_error_code=code,
                version=CrmLead.version + 1,
            )
        )


# ============================================================
# API042 查询最近研判
# ============================================================
def get_assessment(db: Session, user: SysUser, lead_id: int) -> dict:
    from app.core.permissions import build_scope

    scope = build_scope(db, user, "lead")
    lead = scope.get_or_404(db, CrmLead, lead_id)

    has_report = lead.assessment_report is not None
    return {
        "assessmentStatus": lead.assessment_status,
        "assessmentRequestId": str(lead.assessment_request_id)
        if lead.assessment_request_id else None,
        "assessedAt": lead.assessed_at,
        "report": lead.assessment_report,
        "latestScore": lead.latest_score,
        "assessmentErrorCode": lead.assessment_error_code,
        # 本次研判失败但保留了上一份成功报告 → 明确标为历史报告
        "isPreviousReport": lead.assessment_status == "FAILED" and has_report,
    }


# ============================================================
# API096 简历提取草稿（顾问核对用，不改正式事实与销售状态）
# ============================================================
def extract_resume_draft(db: Session, user: SysUser, lead_id: int,
                         data: ResumeExtractionIn) -> dict:
    from app.core.permissions import build_scope

    scope = build_scope(db, user, "lead")
    lead = scope.get_or_404(db, CrmLead, lead_id)
    if lead.version != data.expected_version:
        raise VersionConflictError(lead.version)

    resume_path = _require_resume_path(user, data.object_key)
    if resume_path is None:
        raise NotFoundError("资源不存在")

    from app.services.resume_extract import extract_text

    resume_text = extract_text(resume_path)          # 抽不到 → 422 NO_READABLE_TEXT

    actor_id=user.id
    captured_lead_id=lead.id
    captured_facts=_lead_facts(lead)
    db.rollback()
    extraction = run_assessment(
        {
            "schema_version": "1.0",
            "lead_id": str(captured_lead_id),
            "request_id": str(data.request_key),
            "confirmed_facts": captured_facts,
            "required_fields": _required_fields([]),   # 无项目上下文 → 画像默认必填项
            "resume_text": resume_text,
            "project_rules": [],
        },
        user=str(actor_id),
        timeout_s=settings.ai_timeout_assessment_seconds,
    )

    user=db.get(SysUser,actor_id,populate_existing=True)
    build_scope(db,user,"lead").get_or_404(db,CrmLead,lead_id)
    draft_id = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc).timestamp() + _DRAFT_TTL_MINUTES * 60
    _drafts[draft_id] = ({
        "facts": extraction.get("facts", {}),
        "evidence": extraction.get("evidence", []),
        "missingFields": extraction.get("missing_fields", []),
    }, expires_at)
    _prune_drafts()

    logger.info("简历提取草稿生成 lead=%s draft=%s", lead_id, draft_id)
    # ⚠️ 不写任何正式客户事实、不改销售状态、不改研判状态
    return {
        "draftId": draft_id,
        "facts": extraction.get("facts", {}),
        "evidence": extraction.get("evidence", []),
        "missingFields": extraction.get("missing_fields", []),
        "expiresAt": datetime.fromtimestamp(expires_at, tz=timezone.utc),
        "aiStatus": ai_status(),
        "warnings": extraction.get("warnings", []),
    }


def _prune_drafts() -> None:
    now = datetime.now(timezone.utc).timestamp()
    for key, (_, exp) in list(_drafts.items()):
        if exp < now:
            _drafts.pop(key, None)
