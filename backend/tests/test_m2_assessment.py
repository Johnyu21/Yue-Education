"""
M2 客户研判与简历提取（API041 / API042 / API096）测试

覆盖验收点：
- 已审规则 + 满足条件 → MATCH 且给出分数；不满足 → NO_MATCH
- **未配置/未审核规则 → NEEDS_INFO 且 score 为 null**（不编造门槛与分数）
- 客户匹配多个项目 → 逐项目 decision
- 版本冲突 409；越权 404；研判进行中 409
- **旧任务后返回不得覆盖新结果**（请求号条件回写）
- 失败保留上一份成功报告并标 isPreviousReport
- API096 只出草稿：不改正式事实、不改销售状态、不改研判状态
- 扫描 PDF → 422 NO_READABLE_TEXT；越权 object_key → 404
"""
import json
import shutil
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.core.errors import AIUnavailableError, NotFoundError, VersionConflictError
from app.db.session import SessionLocal
from app.models.user import SysUser
from app.schemas.lead import AssessmentIn, ResumeExtractionIn
from app.services import assessment_service
from app.services.m2_errors import AssessmentRunningError, NoReadableTextError
from tests.conftest import m2_mobile

FIXTURES = Path(__file__).resolve().parent / "fixtures"

@pytest.fixture(scope="module", autouse=True)
def generated_resume_fixtures(tmp_path_factory):
    global FIXTURES
    from tests.fixture_factory import create_resumes
    FIXTURES = tmp_path_factory.mktemp("synthetic_resumes")
    create_resumes(FIXTURES)



def _make_lead(db, mobile: str, dept: int | None, **facts) -> int:
    columns = ", ".join(facts)
    placeholders = ", ".join(f":{k}" for k in facts)
    extra = f", {columns}" if facts else ""
    tail = f", {placeholders}" if facts else ""
    db.execute(text(f"""
        INSERT INTO crm_lead(name,mobile,source,status,dept_id,profile_completeness,
                             request_key,version{extra})
        VALUES ('研判客户',:m,'WEBSITE','NEW',:d,'COMPLETE',:rk,1{tail})
    """), {"m": mobile, "d": dept, "rk": uuid4(), **facts})
    return db.scalar(text("SELECT id FROM crm_lead WHERE mobile=:m"), {"m": mobile})


def _lead_row(db, lead_id: int):
    return db.execute(text(
        "SELECT assessment_status,assessment_report,latest_score,assessment_error_code,"
        "assessment_request_id,version,profile_summary FROM crm_lead WHERE id=:i"),
        {"i": lead_id}).mappings().first()


def _valid_extraction(**_):
    return {
        "schema_version": "1.0",
        "mode": "ASSESSMENT_EXTRACT",
        "facts": {"language_level": "6.5分"},
        "evidence": [{"field": "language_level", "source_ref": "resume:p3",
                      "snippet": "雅思6.5"}],
        "missing_fields": [],
        "warnings": [],
    }


# ============================================================
# 规则判定
# ============================================================
def test_已审规则命中_MATCH并给分(m2_db, m2_env):
    db = m2_db
    head = db.get(SysUser, m2_env["head"])
    lead_id = _make_lead(db, m2_mobile(301), m2_env["dept"], education="本科")
    db.commit()

    res = assessment_service.assess_lead(db, head, lead_id, AssessmentIn(
        request_key=uuid4(), expected_version=1,
        project_ids=[m2_env["M2P_OK"]], confirmed_facts={"education": "本科"}))
    assert res["status"] == "SUCCEEDED"

    out = assessment_service.get_assessment(db, head, lead_id)
    assert out["assessmentStatus"] == "SUCCEEDED"
    project = out["report"]["projects"][0]
    assert project["decision"] == "MATCH"
    assert project["passedRules"] == ["学历要求"]
    assert out["latestScore"] == 30, "已批准权重下应给出分数"
    assert out["isPreviousReport"] is False
    # 报告里带上 AI 提取结果作为参考材料
    assert "extraction" in out["report"]


def test_已审规则不满足_NO_MATCH(m2_db, m2_env):
    db = m2_db
    head = db.get(SysUser, m2_env["head"])
    lead_id = _make_lead(db, m2_mobile(302), m2_env["dept"], education="高中")
    db.commit()

    assessment_service.assess_lead(db, head, lead_id, AssessmentIn(
        request_key=uuid4(), expected_version=1,
        project_ids=[m2_env["M2P_OK"]], confirmed_facts={"education": "高中"}))
    out = assessment_service.get_assessment(db, head, lead_id)
    project = out["report"]["projects"][0]
    assert project["decision"] == "NO_MATCH"
    assert project["failedRules"] == ["学历要求"]
    assert out["latestScore"] is None


def test_未审规则_NEEDS_INFO且分数为空(m2_db, m2_env):
    """⚠️ M2 验收点：项目条件未提供/未审核 → 不做判定、不给分数。"""
    db = m2_db
    head = db.get(SysUser, m2_env["head"])
    lead_id = _make_lead(db, m2_mobile(303), m2_env["dept"], education="本科")
    db.commit()

    assessment_service.assess_lead(db, head, lead_id, AssessmentIn(
        request_key=uuid4(), expected_version=1,
        project_ids=[m2_env["M2P_RAW"]], confirmed_facts={"education": "本科"}))
    out = assessment_service.get_assessment(db, head, lead_id)
    project = out["report"]["projects"][0]
    assert project["decision"] == "NEEDS_INFO"
    assert project["missingFields"] == ["approved_project_rules"]
    assert out["latestScore"] is None, "没有批准权重就不能出现分数（更不能是 0）"


def test_结论未定时不给分数(m2_db, m2_env):
    """⚠️ 只要存在 NEEDS_INFO，就不能给出"貌似精确"的分数。"""
    db = m2_db
    head = db.get(SysUser, m2_env["head"])

    rules = {
        "criteria": [
            {"field": "education", "op": "IN", "values": ["本科"], "label": "学历要求"},
            {"field": "language_level", "op": "GTE_NUM", "value": 4.0, "label": "语言成绩"},
        ],
        "scoring": [{"field": "education", "weights": {"本科": 30}}],
    }
    db.execute(text("""
        INSERT INTO course_project(code,name,description,is_published,admission_rules,
                                   rule_version,rule_approved_at,rule_approved_by,version)
        VALUES ('M2P_TWO','M2P两项条件项目','x',true,CAST(:r AS jsonb),'v1',now(),:by,1)
    """), {"r": json.dumps(rules), "by": head.id})
    db.commit()
    pid_two = db.scalar(text("SELECT id FROM course_project WHERE code='M2P_TWO'"))

    lead_id = _make_lead(db, m2_mobile(3031), m2_env["dept"], education="本科")
    db.commit()

    res = assessment_service.assess_lead(db, head, lead_id, AssessmentIn(
        request_key=uuid4(), expected_version=1,
        project_ids=[pid_two], confirmed_facts={"education": "本科"}))
    out = assessment_service.get_assessment(db, head, lead_id)
    assert out["report"]["projects"][0]["decision"] == "NEEDS_INFO"
    assert out["latestScore"] is None, "结论未定时不能出现貌似精确的分数"

    # 补齐语言成绩 → 两项条件都确定 → 才给分
    assessment_service.assess_lead(db, head, lead_id, AssessmentIn(
        request_key=uuid4(), expected_version=res["leadVersion"],
        project_ids=[pid_two],
        confirmed_facts={"education": "本科", "language_level": "6.5"}))
    out = assessment_service.get_assessment(db, head, lead_id)
    assert out["report"]["projects"][0]["decision"] == "MATCH"
    assert out["latestScore"] == 30


def test_客户匹配多个项目逐个判定(m2_db, m2_env):
    db = m2_db
    head = db.get(SysUser, m2_env["head"])
    lead_id = _make_lead(db, m2_mobile(304), m2_env["dept"], education="本科")
    db.commit()

    assessment_service.assess_lead(db, head, lead_id, AssessmentIn(
        request_key=uuid4(), expected_version=1,
        project_ids=[m2_env["M2P_OK"], m2_env["M2P_RAW"]],
        confirmed_facts={"education": "本科"}))
    out = assessment_service.get_assessment(db, head, lead_id)
    decisions = {p["projectId"]: p["decision"] for p in out["report"]["projects"]}
    assert decisions[str(m2_env["M2P_OK"])] == "MATCH"
    assert decisions[str(m2_env["M2P_RAW"])] == "NEEDS_INFO"
    assert out["latestScore"] is None, "含未审规则项目时不给总分"


def test_缺信息返回NEEDS_INFO并列出缺项(m2_db, m2_env):
    db = m2_db
    head = db.get(SysUser, m2_env["head"])
    lead_id = _make_lead(db, m2_mobile(305), m2_env["dept"])       # 没有任何事实
    db.commit()

    assessment_service.assess_lead(db, head, lead_id, AssessmentIn(
        request_key=uuid4(), expected_version=1,
        project_ids=[m2_env["M2P_OK"]], confirmed_facts={}))
    out = assessment_service.get_assessment(db, head, lead_id)
    project = out["report"]["projects"][0]
    assert project["decision"] == "NEEDS_INFO"
    assert "education" in project["missingFields"]


# ============================================================
# 权限 / 并发
# ============================================================
def test_研判版本冲突(m2_db, m2_env):
    db = m2_db
    head = db.get(SysUser, m2_env["head"])
    lead_id = _make_lead(db, m2_mobile(306), m2_env["dept"], education="本科")
    db.commit()
    with pytest.raises(VersionConflictError):
        assessment_service.assess_lead(db, head, lead_id, AssessmentIn(
            request_key=uuid4(), expected_version=99,
            project_ids=[m2_env["M2P_OK"]], confirmed_facts={}))


def test_越权客户_404(m2_db, m2_env):
    db = m2_db
    advisor = db.get(SysUser, m2_env["advisor"])
    # 未路由客户（dept_id 为空）→ 普通顾问既不是负责人也拿不到部门范围
    lead_id = _make_lead(db, m2_mobile(307), None, education="本科")
    db.commit()
    with pytest.raises(NotFoundError):
        assessment_service.assess_lead(db, advisor, lead_id, AssessmentIn(
            request_key=uuid4(), expected_version=1,
            project_ids=[m2_env["M2P_OK"]], confirmed_facts={}))
    with pytest.raises(NotFoundError):
        assessment_service.get_assessment(db, advisor, lead_id)


def test_主管可研判本部门客户(m2_db, m2_env):
    db = m2_db
    head = db.get(SysUser, m2_env["head"])
    lead_id = _make_lead(db, m2_mobile(308), m2_env["dept"], education="本科")
    db.commit()
    out = assessment_service.get_assessment(db, head, lead_id)
    assert out["assessmentStatus"] == "NONE"


def test_研判进行中_409(m2_db, m2_env):
    db = m2_db
    head = db.get(SysUser, m2_env["head"])
    lead_id = _make_lead(db, m2_mobile(309), m2_env["dept"], education="本科")
    db.execute(text("UPDATE crm_lead SET assessment_status='RUNNING', "
                    "assessment_started_at=now() WHERE id=:i"), {"i": lead_id})
    db.commit()
    with pytest.raises(AssessmentRunningError):
        assessment_service.assess_lead(db, head, lead_id, AssessmentIn(
            request_key=uuid4(), expected_version=1,
            project_ids=[m2_env["M2P_OK"]], confirmed_facts={}))


# ============================================================
# 过时任务与失败保留
# ============================================================
def test_旧请求不得覆盖新结果(m2_db, m2_env, monkeypatch):
    """⚠️ M2-05 验收点：旧任务后返回不能覆盖新结果。"""
    db = m2_db
    head = db.get(SysUser, m2_env["head"])
    lead_id = _make_lead(db, m2_mobile(310), m2_env["dept"], education="本科")
    db.commit()

    old_request, new_request = uuid4(), uuid4()

    def fake_run(payload, **_):
        # 模拟：本次 AI 调用期间，一个更新的研判请求接管了该客户
        with SessionLocal() as other:
            other.execute(text("UPDATE crm_lead SET assessment_request_id=:n, "
                               "assessment_status='RUNNING' WHERE id=:i"),
                          {"n": new_request, "i": lead_id})
            other.commit()
        return _valid_extraction()

    monkeypatch.setattr(assessment_service, "run_assessment", fake_run)

    res = assessment_service.assess_lead(db, head, lead_id, AssessmentIn(
        request_key=old_request, expected_version=1,
        project_ids=[m2_env["M2P_OK"]], confirmed_facts={"education": "本科"}))

    assert res.get("superseded") is True
    row = _lead_row(db, lead_id)
    assert str(row["assessment_request_id"]) == str(new_request)
    assert row["assessment_report"] is None, "过时任务绝不能写入报告"


def test_研判失败保留上一份报告并标记(m2_db, m2_env, monkeypatch):
    db = m2_db
    head = db.get(SysUser, m2_env["head"])
    lead_id = _make_lead(db, m2_mobile(311), m2_env["dept"], education="本科")
    db.commit()

    state = {"fail": False}

    def fake_run(payload, **_):
        if state["fail"]:
            raise AIUnavailableError("模拟 AI 不可用")
        return _valid_extraction()

    monkeypatch.setattr(assessment_service, "run_assessment", fake_run)

    first = assessment_service.assess_lead(db, head, lead_id, AssessmentIn(
        request_key=uuid4(), expected_version=1,
        project_ids=[m2_env["M2P_OK"]], confirmed_facts={"education": "本科"}))
    assert first["status"] == "SUCCEEDED"
    assert _lead_row(db, lead_id)["assessment_report"] is not None

    state["fail"] = True
    with pytest.raises(AIUnavailableError):
        assessment_service.assess_lead(db, head, lead_id, AssessmentIn(
            request_key=uuid4(), expected_version=first["leadVersion"],
            project_ids=[m2_env["M2P_OK"]], confirmed_facts={"education": "本科"}))

    row = _lead_row(db, lead_id)
    assert row["assessment_status"] == "FAILED"
    assert row["assessment_error_code"] == "AI_UNAVAILABLE", "失败只保存符号错误码"
    assert row["assessment_report"] is not None, "失败必须保留上一份成功报告"

    out = assessment_service.get_assessment(db, head, lead_id)
    assert out["isPreviousReport"] is True


# ============================================================
# API096 简历提取草稿
# ============================================================
def _place_resume(tmp_path, actor_id: int, name: str, fixture: str) -> str:
    dest = tmp_path / "u" / str(actor_id)
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy(FIXTURES / fixture, dest / name)
    return f"u/{actor_id}/{name}"


def test_简历提取只出草稿不改事实与状态(m2_db, m2_env, tmp_path, monkeypatch):
    from app.core import storage
    monkeypatch.setattr(storage, "_storage_root", lambda: tmp_path)

    db = m2_db
    head = db.get(SysUser, m2_env["head"])
    lead_id = _make_lead(db, m2_mobile(320), m2_env["dept"])
    db.commit()
    before = _lead_row(db, lead_id)

    object_key = _place_resume(tmp_path, head.id, "resume.pdf", "m2_resume_text.pdf")
    out = assessment_service.extract_resume_draft(db, head, lead_id, ResumeExtractionIn(
        object_key=object_key, request_key=uuid4(), expected_version=1))

    assert out["aiStatus"] == "MOCK"
    assert out["facts"]["education"] == "本科"
    assert out["facts"]["language_level"].startswith("6.5")
    assert out["draftId"]
    assert out["expiresAt"] > __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc)

    after = _lead_row(db, lead_id)
    assert after["assessment_status"] == before["assessment_status"] == "NONE"
    assert after["assessment_report"] is None
    assert after["profile_summary"] is None, "提取草稿不得写入正式客户事实"
    assert after["version"] == before["version"], "提取草稿不得推进客户版本"


def test_简历提取支持docx(m2_db, m2_env, tmp_path, monkeypatch):
    from app.core import storage
    monkeypatch.setattr(storage, "_storage_root", lambda: tmp_path)

    db = m2_db
    head = db.get(SysUser, m2_env["head"])
    lead_id = _make_lead(db, m2_mobile(321), m2_env["dept"])
    db.commit()

    object_key = _place_resume(tmp_path, head.id, "resume.docx", "m2_resume.docx")
    out = assessment_service.extract_resume_draft(db, head, lead_id, ResumeExtractionIn(
        object_key=object_key, request_key=uuid4(), expected_version=1))
    assert out["facts"]["education"] == "本科"


def test_扫描件无可读文本_422(m2_db, m2_env, tmp_path, monkeypatch):
    """⚠️ M2 验收点：扫描 PDF 不假装识别成功。"""
    from app.core import storage
    monkeypatch.setattr(storage, "_storage_root", lambda: tmp_path)

    db = m2_db
    head = db.get(SysUser, m2_env["head"])
    lead_id = _make_lead(db, m2_mobile(322), m2_env["dept"])
    db.commit()

    object_key = _place_resume(tmp_path, head.id, "scan.pdf", "m2_resume_scanned.pdf")
    with pytest.raises(NoReadableTextError) as exc:
        assessment_service.extract_resume_draft(db, head, lead_id, ResumeExtractionIn(
            object_key=object_key, request_key=uuid4(), expected_version=1))
    assert exc.value.code == "NO_READABLE_TEXT"
    assert exc.value.http_status == 422


def test_越权object_key_404(m2_db, m2_env, tmp_path, monkeypatch):
    from app.core import storage
    monkeypatch.setattr(storage, "_storage_root", lambda: tmp_path)

    db = m2_db
    head = db.get(SysUser, m2_env["head"])
    lead_id = _make_lead(db, m2_mobile(323), m2_env["dept"])
    db.commit()

    _place_resume(tmp_path, 999999, "other.pdf", "m2_resume_text.pdf")
    with pytest.raises(NotFoundError):
        assessment_service.extract_resume_draft(db, head, lead_id, ResumeExtractionIn(
            object_key="u/999999/other.pdf", request_key=uuid4(), expected_version=1))
