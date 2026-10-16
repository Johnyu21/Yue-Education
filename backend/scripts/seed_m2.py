"""
M2 种子数据（幂等）—— 项目规则样例 / 开放活动 / 演示客户

⚠️ 与公共 `scripts/seed.py` 相互独立（不改动公共脚本）：
   本项目只补 M2 需要的"可研判"数据，方便联调与演示。

用法：
    cd backend && python -m scripts.seed_m2

幂等策略：按 code / title / mobile 判重，已存在就跳过。
⚠️ 演示手机号用 138 段（与测试清理前缀 13700 区分，跑测试不会误删种子数据）。
"""
from __future__ import annotations

import json

from sqlalchemy import text

from app.db.session import SessionLocal

DEMO_MOBILE = "13800009001"

# 已审核的结构化准入规则（演示"有规则 → 可自动判定"）
RULES_DUAL = {
    "version": "v1",
    "criteria": [
        {"field": "education", "op": "IN",
         "values": ["高中", "中专", "职高", "大专", "本科"], "label": "学历要求"},
        {"field": "language_level", "op": "GTE_NUM", "value": 4.0, "label": "语言成绩"},
    ],
    "scoring": [
        {"field": "education",
         "weights": {"高中": 20, "中专": 20, "职高": 20, "大专": 30, "本科": 40}},
    ],
}

PROJECTS = [
    # (code, name, country, education_level, description, rules, approved)
    ("M2_SEED_DUAL", "中德双元制就业定向班（规则样例）", "德国", "高中及以上",
     "M2 种子：已审核规则的项目，可用于演示自动判定与打分。", RULES_DUAL, True),
    ("M2_SEED_SG", "新加坡升学预备班（无规则样例）", "新加坡", "初中毕业生",
     "M2 种子：未配置规则的项目，研判应返回 NEEDS_INFO 且不给分数。", None, False),
]

EVENTS = [
    ("M2开放日：德国双元制说明会", 7, 30, "线上（腾讯会议）"),
]


def _project_id(db, code: str):
    return db.scalar(text("SELECT id FROM course_project WHERE code=:c"), {"c": code})


def _dept_id(db, code: str):
    return db.scalar(text("SELECT id FROM sys_department WHERE code=:c"), {"c": code})


def _admin_id(db):
    return db.scalar(text("SELECT id FROM sys_user WHERE username='admin'"))


def seed() -> None:
    db = SessionLocal()
    try:
        print("=" * 60)
        print("M2 种子数据（项目规则 / 开放活动 / 演示客户）")
        print("=" * 60)

        dept = _dept_id(db, "TECH")
        admin = _admin_id(db)
        if admin is None:
            print("⚠️ 未找到 admin 账号，请先运行 `python -m scripts.seed`")
            return

        print("\n[1/3] 项目（含准入规则）")
        for code, name, country, level, desc, rules, approved in PROJECTS:
            if _project_id(db, code):
                print(f"  = {code}（已存在，跳过）")
                continue
            db.execute(text("""
                INSERT INTO course_project(code,name,country,education_level,description,
                                           is_published,default_dept_id,admission_rules,
                                           rule_version,rule_approved_at,rule_approved_by,
                                           version)
                VALUES (:c,:n,:co,:el,:d,true,:dept,CAST(:r AS jsonb),:rv,
                        CASE WHEN :ap THEN now() END, CASE WHEN :ap THEN :by END, 1)
            """), {"c": code, "n": name, "co": country, "el": level, "d": desc,
                   "dept": dept, "r": json.dumps(rules) if rules else None,
                   "rv": (rules or {}).get("version") if rules else None,
                   "ap": approved, "by": admin})
            print(f"  + {code} {name}（{'已审核规则' if approved else '未配置规则'}）")
        db.commit()

        print("\n[2/3] 开放活动")
        for title, days, capacity, location in EVENTS:
            exists = db.scalar(text("SELECT id FROM event_lecture WHERE title=:t"), {"t": title})
            if exists:
                print(f"  = {title}（已存在，跳过）")
                continue
            db.execute(text("""
                INSERT INTO event_lecture(title,organizer_user_id,host_department_id,
                                          description,start_at,end_at,signup_deadline,
                                          capacity,location,status,version)
                VALUES (:t,:o,:d,:desc, now() + make_interval(days => :days),
                        now() + make_interval(days => :days, hours => 2),
                        now() + make_interval(days => :days) - interval '1 day',
                        :cap,:loc,'OPEN',1)
            """), {"t": title, "o": admin, "d": dept, "desc": title,
                   "days": days, "cap": capacity, "loc": location})
            print(f"  + {title}（{days} 天后，名额 {capacity}）")
        db.commit()

        print("\n[3/3] 演示客户")
        from uuid import uuid4

        if db.scalar(text("SELECT id FROM crm_lead WHERE mobile=:m"), {"m": DEMO_MOBILE}):
            print(f"  = {DEMO_MOBILE}（已存在，跳过）")
        else:
            db.execute(text("""
                INSERT INTO crm_lead(name,mobile,source,status,dept_id,gender,city,education,
                                     profile_completeness,request_key,version)
                VALUES ('演示客户',:m,'WEBSITE','NEW',:d,'男','广州','本科','COMPLETE',:rk,1)
            """), {"m": DEMO_MOBILE, "d": dept, "rk": uuid4()})
            lead_id = db.scalar(text("SELECT id FROM crm_lead WHERE mobile=:m"), {"m": DEMO_MOBILE})
            db.execute(text("""
                INSERT INTO crm_follow_up(lead_id,follow_up_type,content,status_before,
                                          status_after,details,request_key)
                VALUES (:l,'ACQUIRED','M2 种子演示客户','NEW','NEW',CAST(:d AS jsonb),:rk)
            """), {"l": lead_id, "d": json.dumps({"channel": "FORM", "seeded": True}),
                   "rk": uuid4()})
            print(f"  + 演示客户 {DEMO_MOBILE}（学历=本科，可用于研判演示）")
        db.commit()

        print("\n" + "=" * 60)
        print("完成。联调建议顺序：")
        print("  1) API015/016 看公开项目    2) API019/020 看开放活动")
        print("  3) API023 留资              4) API041 研判（用 M2_SEED_DUAL）")
        print("  5) API042 查报告            6) API096 简历提取草稿")
        print("=" * 60)
    finally:
        db.close()


if __name__ == "__main__":
    seed()
