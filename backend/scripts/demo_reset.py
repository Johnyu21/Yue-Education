"""临时脚本：清理测试脏数据并统一演示命名（用完删除）。"""
from sqlalchemy import text
from app.db.session import engine

# 按外键依赖顺序清空，后续脚本重建干净内容
CLEAR = [
    "m5_chat", "m5_daily_revision", "m5_daily", "m5_report", "m5_report_snapshot",
    "notification", "student_psych_alert", "student_psych_profile",
    "student_application_progress", "student_score", "student_academic_schedule",
    "student_admin_service", "student_feedback_ticket", "event_registration",
    "student_course_enrollment", "crm_follow_up",
]

with engine.begin() as db:
    for t in CLEAR:
        db.execute(text(f"DELETE FROM {t}"))
        print("cleared", t)

    # 删除测试学生档案与账号
    db.execute(text("DELETE FROM student_profile WHERE id=1"))
    db.execute(text("DELETE FROM sys_user WHERE username='student01'"))
    db.execute(text("DELETE FROM sys_class WHERE code='CLS_A'"))
    print("removed test student/class")

    # 删除测试线索与上一轮重建的线索（保留 1-7 演示客户）
    db.execute(text("DELETE FROM crm_lead WHERE id BETWEEN 8 AND 30"))
    print("removed test leads")

    # 删除测试项目与活动
    db.execute(text("DELETE FROM course_project WHERE code LIKE 'DIFY_TEST_%'"))
    db.execute(text("DELETE FROM event_lecture WHERE title LIKE '%界面联调%'"))
    print("removed test project/event")

    # ---- 统一命名 ----
    names = {
        "ui_admin": "系统管理员",
        "ui_head": "周明",
        "ui_advisor": "陈志远",
        "ui_advisor2": "林嘉怡",
        "ui_teacher": "李婉婷",
        "ui_teacher2": "陈静",
        "ui_first": "吴佳（新入职）",
        "13911110001": "陈晓明",
    }
    for username, real_name in names.items():
        db.execute(text("UPDATE sys_user SET real_name=:n WHERE username=:u"),
                   {"n": real_name, "u": username})
    student_names = {
        "13911110002": "王梓涵", "13911110003": "赵沐晴", "13911110004": "刘星宇",
        "13911110005": "周思远", "13911110006": "黄雨桐", "13911110007": "何嘉宁",
    }
    for username, real_name in student_names.items():
        db.execute(text("UPDATE sys_user SET real_name=:n WHERE username=:u"),
                   {"n": real_name, "u": username})

    db.execute(text("UPDATE sys_department SET name='国际教育事业部' WHERE id=7"))
    db.execute(text("UPDATE sys_class SET name='2026级新加坡项目班' WHERE id=2"))
    db.execute(text("UPDATE sys_class SET name='2026级德国双元制班' WHERE id=3"))
    db.execute(text("UPDATE course_project SET name='新加坡国际本科直通项目', description='面向高中及同等学力学生的新加坡本科升学项目，提供语言强化、院校申请与落地服务。' WHERE id=5"))
    db.execute(text("UPDATE course_project SET name='德国双元制就业定向项目', description='面向高中毕业生的德国双元制职业教育项目，企业实践与学校理论结合，毕业可获职业资格。' WHERE id=6"))
    db.execute(text("UPDATE event_lecture SET location='广州市越秀区东风东路723号' WHERE location IS NULL"))
    db.execute(text("UPDATE crm_lead SET name='陈晓明' WHERE id=1"))
    print("renamed demo entities")

print("clean done")
