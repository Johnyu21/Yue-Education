"""临时冒烟脚本：API041/API042/API096（验证后删除）"""
import json
import uuid
from pathlib import Path

import sqlalchemy as sa
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.session import SessionLocal
from app.main import app

c = TestClient(app)
MOBILE = "13900000201"
RESUME_TEXT = "张三\n本科\n雅思6.5\n1998年5月12日"


def login(u, p):
    r = c.post("/api/v1/auth/login", json={"username": u, "password": p})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["data"]["accessToken"]}


db = SessionLocal()
db.execute(sa.text("DELETE FROM course_project WHERE code LIKE 'M2_ASSESS%'"))
db.execute(sa.text(
    "DELETE FROM crm_follow_up WHERE lead_id IN (SELECT id FROM crm_lead WHERE mobile=:m)"),
    {"m": MOBILE})
db.execute(sa.text("DELETE FROM crm_lead WHERE mobile=:m"), {"m": MOBILE})
db.commit()

admin_id = db.execute(sa.text("SELECT id FROM sys_user WHERE username='admin'")).scalar()

rules_ok = {"criteria": [{"field": "education", "op": "IN",
                          "values": ["本科", "硕士"], "label": "学历要求"}],
            "scoring": [{"field": "education", "weights": {"大专": 20, "本科": 30, "硕士": 40}}]}
rules_no_approve = {"criteria": [{"field": "education", "op": "IN",
                                  "values": ["本科"], "label": "学历要求"}]}

for code, name, rules, approved in (
        ("M2_ASSESS_OK", "M2研判项目-已审规则", rules_ok, True),
        ("M2_ASSESS_RAW", "M2研判项目-未审规则", rules_no_approve, False)):
    if approved:
        sql = sa.text("""
            INSERT INTO course_project(code,name,description,is_published,admission_rules,
                                       rule_version,rule_approved_at,rule_approved_by,version)
            VALUES (:c,:n,'冒烟',true,CAST(:r AS jsonb),'v1',now(),:by,1)
        """)
        params = {"c": code, "n": name, "r": json.dumps(rules), "by": admin_id}
    else:
        sql = sa.text("""
            INSERT INTO course_project(code,name,description,is_published,admission_rules,
                                       rule_version,rule_approved_at,rule_approved_by,version)
            VALUES (:c,:n,'冒烟',true,CAST(:r AS jsonb),'v1',NULL,NULL,1)
        """)
        params = {"c": code, "n": name, "r": json.dumps(rules)}
    db.execute(sql, params)
db.commit()
pid_ok = db.execute(sa.text("SELECT id FROM course_project WHERE code='M2_ASSESS_OK'")).scalar()
pid_raw = db.execute(sa.text("SELECT id FROM course_project WHERE code='M2_ASSESS_RAW'")).scalar()
db.close()

admin = login("admin", "admin123")

# ---------- 留资（带学历）----------
r = c.post("/api/v1/public/leads", json={
    "name": "冒烟研判", "mobile": MOBILE, "channel": "FORM",
    "request_key": str(uuid.uuid4()), "confirmed": True,
    "gender": "男", "city": "广州", "education": "本科"})
print("023 留资:", r.status_code, r.json()["data"]["accepted"])

db = SessionLocal()
lead_id = db.execute(sa.text("SELECT id FROM crm_lead WHERE mobile=:m"), {"m": MOBILE}).scalar()
lead_ver = db.execute(sa.text("SELECT version FROM crm_lead WHERE id=:i"), {"i": lead_id}).scalar()
db.close()
print("   lead_id=", lead_id, "version=", lead_ver)

# ---------- API041 研判（已审规则 → MATCH + 分数）----------
r = c.post(f"/api/v1/employees/leads/{lead_id}/assessments", headers=admin, json={
    "request_key": str(uuid.uuid4()), "expected_version": lead_ver,
    "project_ids": [pid_ok], "confirmed_facts": {"education": "本科"}})
print("041 研判(已审规则):", r.status_code, r.text[:300])
ver2 = r.json()["data"]["leadVersion"]

# ---------- API042 查询 ----------
r = c.get(f"/api/v1/employees/leads/{lead_id}/assessment", headers=admin)
d = r.json()["data"]
rep = d["report"]
print("042 状态:", d["assessmentStatus"], "score=", d["latestScore"],
      "isPreviousReport=", d["isPreviousReport"])
print("   项目判定:", [(p["projectId"], p["decision"], p["passedRules"],
                   p["failedRules"], p["missingFields"]) for p in rep["projects"]])
print("   规则版本:", rep["ruleVersion"], "证据条数=", len(rep["evidence"]),
      "提取参考=", rep["extraction"]["facts"])

# ---------- 未审规则 → NEEDS_INFO 且分数为空 ----------
r = c.post(f"/api/v1/employees/leads/{lead_id}/assessments", headers=admin, json={
    "request_key": str(uuid.uuid4()), "expected_version": ver2,
    "project_ids": [pid_raw], "confirmed_facts": {"education": "本科"}})
print("041 研判(未审规则):", r.status_code)
ver3 = r.json()["data"]["leadVersion"]

r = c.get(f"/api/v1/employees/leads/{lead_id}/assessment", headers=admin)
d = r.json()["data"]
print("042 未审规则 → decision=", d["report"]["projects"][0]["decision"],
      "missing=", d["report"]["projects"][0]["missingFields"],
      "score=", d["latestScore"])

# ---------- 版本冲突 ----------
r = c.post(f"/api/v1/employees/leads/{lead_id}/assessments", headers=admin, json={
    "request_key": str(uuid.uuid4()), "expected_version": 1,
    "project_ids": [pid_ok], "confirmed_facts": {}})
print("041 版本冲突:", r.status_code, r.json()["code"])

# ---------- 越权（新人无客户范围）→ 404 ----------
newbie = login("newcomer01", "test123")
r = c.post(f"/api/v1/employees/leads/{lead_id}/assessments", headers=newbie, json={
    "request_key": str(uuid.uuid4()), "expected_version": ver3,
    "project_ids": [pid_ok], "confirmed_facts": {}})
print("041 越权:", r.status_code, r.json()["code"])

# ---------- 项目不存在 ----------
r = c.post(f"/api/v1/employees/leads/{lead_id}/assessments", headers=admin, json={
    "request_key": str(uuid.uuid4()), "expected_version": ver3,
    "project_ids": [999999], "confirmed_facts": {}})
print("041 项目不存在:", r.status_code, r.json()["code"])

# ---------- RUNNING 冲突（人工置 RUNNING）----------
db = SessionLocal()
db.execute(sa.text("UPDATE crm_lead SET assessment_status='RUNNING', assessment_started_at=now() "
                   "WHERE id=:i"), {"i": lead_id})
db.commit()
db.close()
r = c.post(f"/api/v1/employees/leads/{lead_id}/assessments", headers=admin, json={
    "request_key": str(uuid.uuid4()), "expected_version": ver3,
    "project_ids": [pid_ok], "confirmed_facts": {}})
print("041 研判进行中:", r.status_code, r.json()["code"])

db = SessionLocal()
db.execute(sa.text("UPDATE crm_lead SET assessment_status='SUCCEEDED' WHERE id=:i"), {"i": lead_id})
db.commit()
db.close()

# ---------- API096 简历提取草稿 ----------
root = Path(settings.file_storage_root).resolve() / "u" / str(admin_id)
root.mkdir(parents=True, exist_ok=True)
txt = root / "m2_smoke_resume.txt"
txt.write_text(RESUME_TEXT, encoding="utf-8")
empty_pdf = root / "m2_smoke_empty.pdf"
empty_pdf.write_bytes(b"")

object_key = f"u/{admin_id}/m2_smoke_resume.txt"
r = c.post(f"/api/v1/employees/leads/{lead_id}/resume-extraction", headers=admin, json={
    "object_key": object_key, "request_key": str(uuid.uuid4()), "expected_version": ver3})
print("096 简历提取:", r.status_code, r.text[:320])

r = c.post(f"/api/v1/employees/leads/{lead_id}/resume-extraction", headers=admin, json={
    "object_key": f"u/{admin_id}/m2_smoke_empty.pdf", "request_key": str(uuid.uuid4()),
    "expected_version": ver3})
print("096 扫描件/无可读文本:", r.status_code, r.json().get("code"))

r = c.post(f"/api/v1/employees/leads/{lead_id}/resume-extraction", headers=admin, json={
    "object_key": "u/999999/m2_smoke_resume.txt", "request_key": str(uuid.uuid4()),
    "expected_version": ver3})
print("096 越权 object_key:", r.status_code, r.json().get("code"))

# 确认 096 未改正式事实与研判状态
db = SessionLocal()
row = db.execute(sa.text(
    "SELECT assessment_status, profile_summary, version FROM crm_lead WHERE id=:i"),
    {"i": lead_id}).mappings().first()
db.close()
print("096 后：状态=", row["assessment_status"], "profile_summary=", row["profile_summary"],
      "version=", row["version"])

print("SMOKE DONE lead_id=", lead_id)
