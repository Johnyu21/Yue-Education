"""临时脚本：重建干净、完整的答辩演示数据集（用完删除）。

前置：_demo_backup.py 已备份到 bak_20261019_*，_demo_clean.py 已清理测试数据。
全部写入在一个事务中，失败自动回滚。
"""
import json
from collections import defaultdict
from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import text
from app.db.session import engine


def J(value):
    return json.dumps(value, ensure_ascii=False)


def T(d, h=9, mi=0):
    return datetime(2026, 10, d, h, mi, tzinfo=timezone.utc)


DEPT = 7
ADV1, ADV2 = 7, 12
TEACH1, TEACH2 = 8, 13
HEAD, ADMIN, NEWBIE = 9, 10, 6
STU = {1: 11, 2: 14, 3: 15, 4: 16, 5: 17, 6: 18, 7: 19}
PROFILE = {1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 7, 7: 8}
ADVISOR = {1: ADV1, 2: ADV1, 3: ADV1, 4: ADV1, 5: ADV2, 6: ADV2, 7: ADV2}
PROJECT = {1: 1, 2: 4, 3: 1, 4: 1, 5: 4, 6: 4, 7: 4}


def notification(db, uid, cat, title, content, key):
    db.execute(text("""
        INSERT INTO notification(recipient_user_id,category,title,content,business_event_key)
        VALUES (:u,:c,:t,:ct,:k)
    """), {"u": uid, "c": cat, "t": title, "ct": content, "k": key})


with engine.begin() as db:
    # ---------------- 学生档案补全 ----------------
    profiles = [
        (2, "男", "广州", "高中", "GRANTED"),
        (3, "女", "深圳", "高中", "GRANTED"),
        (4, "女", "广州", "高中", "GRANTED"),
        (5, "男", "佛山", "高中", "GRANTED"),
        (6, "男", "东莞", "高中", "GRANTED"),
        (7, "女", "广州", "高中", "GRANTED"),
        (8, "男", "珠海", "高中", "NOT_GIVEN"),
    ]
    for pid, gender, city, edu, consent in profiles:
        granted = consent == "GRANTED"
        db.execute(text("""
            UPDATE student_profile SET gender=:g, city=:c, education=:e,
                enrollment_date=DATE '2026-09-01',
                psych_consent_status=CAST(:s AS varchar),
                psych_consent_at=:ca,
                psych_consent_version=:cv
            WHERE id=:p
        """), {"g": gender, "c": city, "e": edu, "s": consent,
               "ca": T(5, 9) if granted else None,
               "cv": "v1" if granted else None, "p": pid})
    print("profiles updated")

    # ---------------- 线索 1-7 更新 ----------------
    signed = [
        (1, "陈晓明", "男", "13811110001", "广州", "高中", 1, "2026-09-01", ADV1),
        (2, "王梓涵", "女", "13911110002", "深圳", "高中", 4, "2026-10-10", ADV1),
        (3, "赵沐晴", "女", "13911110003", "广州", "高中", 1, "2026-10-10", ADV1),
        (4, "刘星宇", "男", "13911110004", "佛山", "高中", 1, "2026-10-10", ADV1),
        (5, "周思远", "男", "13911110005", "东莞", "高中", 4, "2026-10-10", ADV2),
        (6, "黄雨桐", "女", "13911110006", "广州", "高中", 4, "2026-10-10", ADV2),
        (7, "何嘉宁", "男", "13911110007", "珠海", "高中", 4, "2026-10-10", ADV2),
    ]
    for lid, name, gender, mobile, city, edu, proj, sign_date, owner in signed:
        db.execute(text("""
            UPDATE crm_lead SET name=:n, gender=:g, city=:c, education=:e,
                intended_project_id=:p, status='SIGNED', signed_at=:sd,
                profile_completeness='COMPLETE', interest_level='高',
                contract_ref=:ref, contract_currency=NULL, study_purpose='升学'
            WHERE id=:id
        """), {"n": name, "g": gender, "c": city, "e": edu, "p": proj,
               "sd": datetime.fromisoformat(sign_date + "T10:00:00+00:00"),
               "ref": f"YUE-2026-{lid:04d}", "id": lid})

    # ---------------- 新增线索 ----------------
    new_leads = [
        (17, "张一诺", "女", "13800001001", "广州", "本科", 1, "WEBSITE", "NEW", None, "高", None, None),
        (18, "李思远", "男", "13800001002", "深圳", "大专", 4, "CHAT", "NEW", None, "中", None, None),
        (19, "陈雨欣", "女", "13800001003", "广州", "高中", 1, "EVENT", "NEW", None, "高", None, None),
        (20, "王浩然", "男", "13800001004", "佛山", "高中", 4, "MANUAL", "FOLLOWING", ADV1, "高", None, None),
        (21, "刘佳琪", "女", "13800001005", "东莞", "高中", 1, "MANUAL", "FOLLOWING", ADV2, "中", None, None),
        (22, "赵子轩", "男", "13800001006", "广州", "本科", 4, "WEBSITE", "LOST", ADV1, "低", "2026-10-15", "预算与时间安排不匹配"),
        (23, "孙悦", "女", "13800001007", "深圳", "高中", 1, "CHAT", "LOST", ADV2, "中", "2026-10-16", "已选择其他机构"),
    ]
    for (lid, name, gender, mobile, city, edu, proj, source, status,
         owner, interest, loss_at, loss_reason) in new_leads:
        db.execute(text("""
            INSERT INTO crm_lead(id,name,gender,mobile,city,education,intended_project_id,
                source,status,dept_id,owner_user_id,interest_level,profile_completeness,
                study_purpose,lost_at,loss_reason,request_key)
            OVERRIDING SYSTEM VALUE
            VALUES (:id,:n,:g,:m,:c,:e,:p,:src,:st,:d,:o,:i,'COMPLETE','升学',:la,:lr,
                CAST(:rk AS uuid))
        """), {"id": lid, "n": name, "g": gender, "m": mobile, "c": city, "e": edu,
               "p": proj, "src": source, "st": status, "d": DEPT, "o": owner,
               "i": interest,
               "la": datetime.fromisoformat(loss_at + "T10:00:00+00:00") if loss_at else None,
               "lr": loss_reason, "rk": str(uuid4())})
    print("leads inserted")

    # ---------------- 跟进记录 ----------------
    followups = [
        (1, ADV1, "SIGNED", "完成签约，转入学生服务。", "FOLLOWING", "SIGNED", "2026-09-01"),
        (2, ADV1, "SIGNED", "确认德国项目录取，完成签约。", "FOLLOWING", "SIGNED", "2026-10-10"),
        (3, ADV1, "SIGNED", "新加坡项目签约，进入语言强化阶段。", "FOLLOWING", "SIGNED", "2026-10-10"),
        (4, ADV1, "SIGNED", "完成新加坡项目签约。", "FOLLOWING", "SIGNED", "2026-10-10"),
        (5, ADV2, "SIGNED", "德国双元制项目签约。", "FOLLOWING", "SIGNED", "2026-10-10"),
        (6, ADV2, "SIGNED", "确认企业面试通过，完成签约。", "FOLLOWING", "SIGNED", "2026-10-10"),
        (7, ADV2, "SIGNED", "完成德国项目签约。", "FOLLOWING", "SIGNED", "2026-10-10"),
        (17, None, "ACQUIRED", "官网表单留资：想了解新加坡本科升学路径。", "NEW", "NEW", "2026-10-17"),
        (18, None, "ACQUIRED", "AI 客服对话留资：关注德国双元制项目。", "NEW", "NEW", "2026-10-18"),
        (19, None, "ACQUIRED", "活动报名留资：新加坡项目说明会。", "NEW", "NEW", "2026-10-16"),
        (20, ADV1, "ACQUIRED", "手工录入：家长来电咨询德国项目。", "NEW", "NEW", "2026-10-12"),
        (20, ADV1, "CLAIMED", "顾问认领并建立联系。", "NEW", "NEW", "2026-10-12"),
        (20, ADV1, "CONTACT", "已电话沟通，介绍德国双元制培养模式与费用。", "NEW", "FOLLOWING", "2026-10-14"),
        (21, ADV2, "ACQUIRED", "手工录入：在读高中生咨询新加坡升学。", "NEW", "NEW", "2026-10-11"),
        (21, ADV2, "CLAIMED", "顾问认领。", "NEW", "NEW", "2026-10-11"),
        (21, ADV2, "CONTACT", "微信沟通，发送项目资料与入学要求。", "NEW", "FOLLOWING", "2026-10-13"),
        (22, ADV1, "ACQUIRED", "官网留资：德国项目。", "NEW", "NEW", "2026-10-08"),
        (22, ADV1, "STATUS", "客户确认暂缓，原因：预算与时间安排不匹配。", "FOLLOWING", "LOST", "2026-10-15"),
        (23, ADV2, "ACQUIRED", "客服对话留资。", "NEW", "NEW", "2026-10-09"),
        (23, ADV2, "STATUS", "客户已选择其他机构，标记流失。", "FOLLOWING", "LOST", "2026-10-16"),
    ]
    for lid, actor, ftype, content, before, after, day in followups:
        db.execute(text("""
            INSERT INTO crm_follow_up(lead_id,actor_user_id,follow_up_type,content,
                status_before,status_after,details,request_key,create_time)
            VALUES (:lid,:actor,:ft,:ct,:bb,:ba,CAST(:det AS jsonb),CAST(:rk AS uuid),:ctime)
        """), {"lid": lid, "actor": actor, "ft": ftype, "ct": content, "bb": before,
               "ba": after, "det": J({"demo": True}), "rk": str(uuid4()),
               "ctime": T(int(day[8:10]), 10)})
    print("followups inserted")

    # ---------------- 课程关联 ----------------
    enroll_ids = {}
    for idx in range(1, 8):
        row = db.execute(text("""
            INSERT INTO student_course_enrollment(student_profile_id,course_project_id,status,enrolled_at)
            VALUES (:s,:p,'ENROLLED',TIMESTAMPTZ '2026-09-01 09:00+08') RETURNING id
        """), {"s": PROFILE[idx], "p": PROJECT[idx]}).scalar_one()
        enroll_ids[idx] = row
    print("enrollments inserted")

    # ---------------- 成绩 ----------------
    scores = {
        1: [("英语", "NUMERIC", "88", 88, 100), ("数学", "NUMERIC", "91", 91, 100),
            ("德语", "GRADE", "B+", None, None), ("专业基础", "PASS_FAIL", "PASS", None, None)],
        2: [("英语", "NUMERIC", "92", 92, 100), ("数学", "NUMERIC", "86", 86, 100),
            ("德语", "GRADE", "A", None, None)],
        3: [("英语", "NUMERIC", "85", 85, 100), ("数学", "NUMERIC", "90", 90, 100),
            ("德语", "GRADE", "B", None, None)],
        4: [("英语", "NUMERIC", "79", 79, 100), ("数学", "NUMERIC", "82", 82, 100),
            ("专业基础", "PASS_FAIL", "PASS", None, None)],
        5: [("英语", "NUMERIC", "84", 84, 100), ("数学", "NUMERIC", "88", 88, 100),
            ("德语", "GRADE", "B+", None, None)],
        6: [("英语", "NUMERIC", "90", 90, 100), ("数学", "NUMERIC", "85", 85, 100),
            ("德语", "GRADE", "A-", None, None)],
        7: [("英语", "NUMERIC", "81", 81, 100), ("数学", "NUMERIC", "87", 87, 100),
            ("专业基础", "PASS_FAIL", "PASS", None, None)],
    }
    for idx, items in scores.items():
        for subject, stype, stext, snum, smax in items:
            db.execute(text("""
                INSERT INTO student_score(student_profile_id,enrollment_id,subject,score_type,
                    score_text,score_numeric,max_score,graded_at,recorded_by_user_id,remark,data_source)
                VALUES (:s,:en,:sub,:ty,:tx,:num,:max,DATE '2026-10-15',:u,'演示成绩','TEST')
            """), {"s": PROFILE[idx], "en": enroll_ids[idx], "sub": subject, "ty": stype,
                   "tx": stext, "num": snum, "max": smax, "u": ADVISOR[idx]})
    print("scores inserted")

    # ---------------- 教务日程 ----------------
    schedules = [
        (1, "EXAM", "德语 A2 等级模拟考试", 22, 9, "A栋301", 1),
        (1, "DEADLINE", "新加坡院校申请材料补充截止", 28, 18, None, 1),
        (2, "EXAM", "德国双元制企业面试", 25, 14, "线上会议", 2),
        (2, "CLASS", "德语口语强化课", 21, 10, "B栋205", 2),
        (3, "EXAM", "英语阶段测评", 23, 9, "A栋202", 3),
        (3, "DEADLINE", "新加坡学生签证材料提交", 30, 18, None, 3),
        (4, "CLASS", "专业基础导论", 21, 14, "C栋101", 4),
        (4, "EXAM", "数学阶段测验", 26, 9, "A栋203", 4),
        (5, "EXAM", "德语 B1 模拟考试", 24, 9, "A栋301", 5),
        (5, "DEADLINE", "德国企业实践确认表提交", 29, 18, None, 5),
        (6, "CLASS", "跨文化沟通工作坊", 22, 14, "D栋302", 6),
        (6, "EXAM", "德语阶段测评", 27, 9, "A栋301", 6),
        (7, "CLASS", "职业规划辅导", 23, 15, "B栋108", 7),
        (7, "DEADLINE", "德国项目报名材料截止", 31, 18, None, 7),
    ]
    for idx, stype, title, day, hour, loc, by in schedules:
        db.execute(text("""
            INSERT INTO student_academic_schedule(student_profile_id,schedule_type,title,description,
                start_at,end_at,location,status,data_source,created_by_user_id)
            VALUES (:s,:ty,:t,'演示教务安排',:st,:et,:loc,'SCHEDULED','MANUAL',:u)
        """), {"s": PROFILE[idx], "ty": stype, "t": title,
               "st": T(day, hour), "et": T(day, hour + 2), "loc": loc,
               "u": ADVISOR[idx] if by <= 4 else TEACH2})
    print("schedules inserted")

    # ---------------- 申请进度 ----------------
    cases = [
        (1, "SCHOOL", "新加坡 2+2 定向培养本科申请", "新加坡", "新加坡管理学院", "工商管理本科",
         [("SUBMITTED", 20, "已提交院校申请与成绩单"), ("PROCESSING", 8, "院校初审中，等待面试安排"),
          ("COMPLETED", 16, "已收到录取通知，进入缴费确认")]),
        (2, "DOCUMENT", "德国双元制项目申请材料", "德国", "柏林双元制职业学院", "机电一体化",
         [("SUBMITTED", 28, "材料已递交企业方"), ("PROCESSING", 12, "企业审核中，安排线上面试")]),
        (5, "VISA", "德国学生签证申请", "德国", "德国驻广州总领事馆", "职业培训签证",
         [("SUBMITTED", 10, "签证材料已递交"), ("PROCESSING", 18, "等待使领馆审核")]),
    ]
    for idx, item_type, title, country, school, program, events in cases:
        case_no = str(uuid4())
        prev = None
        for seq, (stage, day, detail) in enumerate(events, start=1):
            row = db.execute(text("""
                INSERT INTO student_application_progress(case_no,student_profile_id,sequence_no,
                    previous_id,item_type,title,target_country,target_school,target_program,
                    stage,event_kind,detail,assignee_user_id,recorded_by_user_id,data_source,
                    occurred_at,request_key)
                VALUES (CAST(:cn AS uuid),:sp,:sq,:pv,:it,:ti,:co,:sc,:pg,:st,'STAGE',:de,:as,:rb,
                    'MANUAL',:oc,CAST(:rk AS uuid))
                RETURNING id
            """), {"cn": case_no, "sp": PROFILE[idx], "sq": seq, "pv": prev,
                   "it": item_type, "ti": title, "co": country, "sc": school, "pg": program,
                   "st": stage, "de": detail, "as": ADVISOR[idx], "rb": ADVISOR[idx],
                   "oc": T(day, 10), "rk": str(uuid4())}).scalar_one()
            prev = row
    print("application cases inserted")

    # ---------------- 行政申请 ----------------
    services = [
        (2, "LEAVE", "因病请假一天", "发热就医，附就诊记录。", "PENDING", 11, TEACH1, T(20), T(21), None, None, None),
        (3, "LEAVE", "参加家庭活动请假", "周五下午需提前离校。", "APPROVED", 14, TEACH1, T(15, 14), T(15, 18), None, "已核实，同意请假。", T(15, 12)),
        (4, "LEAVE", "外出办理证件", "需前往出入境大厅办理护照。", "REJECTED", 15, TEACH1, T(12, 9), T(12, 12), None, "当天有阶段测评，建议改期。", T(11, 16)),
        (5, "EXAM", "德语 A2 等级考试报名", "申请参加 11 月德语 A2 等级考试。", "PENDING", 16, TEACH1, None, None, None, None, None),
        (6, "INFO_CHANGE", "联系电话变更", "原手机号停用，申请更新联系方式。", "PENDING", 17, TEACH2, None, None,
         J({"field": "mobile", "old": "13911110005", "new": "13911110055"}), None, None),
    ]
    for sp, stype, title, desc, status, by, assignee, start, end, change, note, decided in services:
        db.execute(text("""
            INSERT INTO student_admin_service(student_profile_id,dept_id,service_type,title,description,
                start_at,end_at,change_request,submitted_by_user_id,assignee_user_id,status,
                decision_note,decided_at,handling_history,request_key,create_time,update_time)
            VALUES (:sp,:d,:ty,:t,:de,:st,:en,CAST(:ch AS jsonb),:by,:asg,:status,
                :note,:dec,CAST('[]' AS jsonb),CAST(:rk AS uuid),:ct,:ct)
        """), {"sp": sp, "d": DEPT, "ty": stype, "t": title, "de": desc, "st": start, "en": end,
               "ch": change, "by": by, "asg": assignee, "status": status, "note": note,
               "dec": decided, "rk": str(uuid4()), "ct": T(12, 10)})
    print("admin services inserted")

    # ---------------- 售后工单 ----------------
    tickets = [
        (2, "COMPLAINT", "课程时间调整未及时通知", "王老师", "语言培训", 1,
         "原定周六的德语课临时调整，未提前通知，影响出行安排。", "HIGH", "PROCESSING",
         None, None, None, None, 9),
        (3, "SUGGESTION", "建议增加晚间答疑时段", "李老师", "语言培训", 4,
         "希望每周增加一次晚间线上答疑，方便在职学生。", "NORMAL", "RESOLVED",
         "已协调教研组，每周三 19:30 增加线上答疑。", T(16, 15), None, None, 9),
        (4, "COMPLAINT", "教材发放延迟", "陈老师", "教务管理", 1,
         "开学两周仍未收到德语教材，影响学习进度。", "HIGH", "CLOSED",
         "教材已于次日补发并致电说明，学生确认收到。", T(14, 11), T(15, 9), 5, 9),
        (5, "CONSULTATION", "咨询项目转班流程", "未知", "学生服务", 4,
         "想了解从德国项目转到新加坡项目需要哪些手续。", "NORMAL", "PENDING",
         None, None, None, None, None),
    ]
    for (sp, cat, subject, teacher, projcat, proj, content, priority, status,
         resolution, resolved_at, closed_at, rating, assignee) in tickets:
        row_id = db.execute(text("""
            INSERT INTO student_feedback_ticket(student_profile_id,dept_id,assignee_user_id,
                category,subject,teacher_name,project_category,course_project_id,content,priority,
                status,resolution,first_response_at,first_resolved_at,resolved_at,closed_at,due_at,
                is_notified,reopened_count,satisfaction_rating,satisfaction_comment,rated_at,
                handling_history,request_key)
            VALUES (:sp,:d,:asg,:cat,:sub,:te,:pc,:proj,:ct,:pr,:st,:res,:fr,:fr2,:res_at,:cl,
                :due,:notified,0,:rating,:comment,:rated,CAST('[]' AS jsonb),CAST(:rk AS uuid))
            RETURNING id
        """), {"sp": sp, "d": DEPT, "asg": assignee, "cat": cat, "sub": subject, "te": teacher,
               "pc": projcat, "proj": proj, "ct": content, "pr": priority, "st": status,
               "res": resolution, "fr": T(13, 10) if status != "PENDING" else None,
               "fr2": T(14, 10) if status in ("RESOLVED", "CLOSED") else None,
               "res_at": resolved_at, "cl": closed_at,
               "due": T(13, 18) if priority == "HIGH" else None,
               "notified": status in ("RESOLVED", "CLOSED"),
               "rating": rating, "comment": "处理及时，沟通顺畅。" if rating else None,
               "rated": T(16, 10) if rating else None,
               "rk": str(uuid4())}).scalar_one()
        if status in ("RESOLVED", "CLOSED"):
            notification(db, STU[sp], "FEEDBACK_RESOLVED", "售后工单已解决",
                         f"你提交的「{subject}」已处理完成，请确认并评价。",
                         f"demo:ticket:{row_id}:resolved")
    print("tickets inserted")

    # ---------------- 心理观测 ----------------
    psych_obs = [
        (2, "HEALTHY", "情绪平稳，学习状态良好。"),
        (2, "NEGATIVE", "近期考试压力较大，睡眠偏少。"),
        (3, "NEGATIVE", "与同学沟通较少，情绪偏低落。"),
        (3, "VERY_NEGATIVE", "连续多日情绪低落，需持续关注。"),
        (4, "HEALTHY", "适应良好，参与课堂积极。"),
        (5, "HEALTHY", "状态稳定，按计划推进学习。"),
        (6, "NEGATIVE", "对签证进度感到焦虑。"),
        (7, "HEALTHY", "情绪平稳。"),
    ]
    versions = defaultdict(int)
    obs_ids = {}
    for sp, emotion, summary in psych_obs:
        versions[sp] += 1
        ver = versions[sp]
        day = 17 if ver == 1 else 18
        row = db.execute(text("""
            INSERT INTO student_psych_profile(student_profile_id,version_no,assessment_date,
                business_timezone,observed_at,source_event_key,assessment_source,emotion_state,
                assessment_data,summary,consent_at,status,is_valid,created_by_user_id)
            VALUES (:sp,:v,:d,'Asia/Shanghai',:ob,CAST(:rk AS uuid),'RULE',:em,
                CAST(:adata AS jsonb),:sum,TIMESTAMPTZ '2026-09-05 09:00+08',
                'AUTO_RECORDED',true,:cb)
            RETURNING id
        """), {"sp": sp, "v": ver, "d": date(2026, 10, day), "ob": T(day, 20),
               "rk": str(uuid4()), "em": emotion,
               "adata": J({"confidence": 0.8, "rule_version": "v1", "evidence": summary}),
               "sum": summary, "cb": TEACH1 if sp <= 4 else TEACH2}).scalar_one()
        obs_ids[sp] = row
    db.execute(text("""
        INSERT INTO student_psych_alert(student_profile_id,psych_profile_id,severity,signal_code,
            trigger_summary,status,created_by_user_id,follow_up_user_id,handling_history,
            trigger_key,last_triggered_at,create_time,update_time)
        VALUES (3,:pp,'HIGH','H_CONTINUOUS_NEGATIVE',
            '连续两日情绪消极，最近一次为极度消极，建议人工复核。','PENDING_REVIEW',
            :cb,:fu,CAST('[]' AS jsonb),'demo-psych-alert-profile3',:lt,:lt,:lt)
    """), {"pp": obs_ids[3], "cb": TEACH1, "fu": HEAD, "lt": T(18, 20)})
    print("psych inserted")

    # ---------------- 日报 ----------------
    advisor_days = [
        (ADV1, 12, "APPROVED", "跟进 5 名意向客户，完成 2 名学生的入学材料核对。", [
            ("CUSTOMER", "电话回访新加坡项目意向客户张一诺，介绍课程与费用", [], 1, "客户同意本周到访"),
            ("ENROLLMENT", "核对陈晓明新加坡院校申请材料", ["2"], 1, "材料已补齐"),
            ("DELIVERY", "整理德国双元制项目介绍资料", [], 1, "已上传共享盘"),
        ], "无", "继续跟进王浩然家长"),
        (ADV1, 13, "APPROVED", "接待来访家长 2 组，推进 1 名学生签约。", [
            ("CUSTOMER", "接待王浩然家长，介绍德国双元制培养模式", ["5"], 1, "家长考虑中"),
            ("ENROLLMENT", "协助赵沐晴准备英语阶段测评", ["4"], 1, "已完成复习计划"),
            ("OTHER", "参加部门周会，同步本周招生进度", [], 1, "已记录待办"),
        ], "部分家长对费用仍有顾虑", "准备费用说明材料"),
        (ADV1, 14, "RETURNED", "处理客户咨询与日常教务沟通。", [
            ("CUSTOMER", "回复官网咨询 3 条", [], 3, "已分配跟进"),
            ("DELIVERY", "与教学组沟通课程调整", [], 1, "待确认"),
        ], "课程调整方案未确定", "跟进课程调整结果"),
        (ADV1, 15, "APPROVED", "完成学生签证材料初审与客户跟进。", [
            ("ENROLLMENT", "初审周思远德国签证材料", ["6"], 1, "材料基本齐全"),
            ("CUSTOMER", "跟进刘佳琪新加坡项目意向", ["5"], 1, "客户希望周末面谈"),
            ("OTHER", "整理本周客户跟进台账", [], 1, "已更新"),
        ], "无", "周末面谈准备"),
        (ADV1, 16, "SUBMITTED", "完成本周客户回访与学生服务记录。", [
            ("CUSTOMER", "电话回访本周新增客户 4 名", [], 4, "2 名有意向"),
            ("ENROLLMENT", "更新学生申请进度台账", ["2", "3"], 2, "已同步系统"),
            ("DELIVERY", "整理下周活动报名名单", [], 1, "待发布"),
        ], "活动场地尚未最终确认", "周一确认场地"),
    ]
    advisor2_days = [
        (ADV2, 12, "APPROVED", "完成德国项目学生服务与客户接待。", [
            ("CUSTOMER", "接待刘佳琪家长，介绍新加坡项目", [], 1, "家长满意"),
            ("DELIVERY", "组织德国项目学生行前说明会", ["6", "7"], 1, "学生全部参加"),
            ("ENROLLMENT", "跟进黄雨桐德语学习进度", ["7"], 1, "进度正常"),
        ], "无", "继续跟进刘佳琪"),
        (ADV2, 13, "APPROVED", "跟进 4 名意向客户，完成 1 次项目宣讲。", [
            ("CUSTOMER", "电话跟进孙悦，了解择校顾虑", [], 1, "客户仍在比较"),
            ("DELIVERY", "准备德国双元制项目宣讲材料", [], 1, "已完成"),
            ("OTHER", "参加项目宣讲彩排", [], 1, "已反馈修改意见"),
        ], "无", "宣讲会执行"),
        (ADV2, 14, "APPROVED", "执行项目宣讲并整理客户反馈。", [
            ("CUSTOMER", "项目宣讲会现场接待客户 3 组", [], 3, "2 组留下联系方式"),
            ("OTHER", "整理宣讲会客户反馈", [], 1, "已提交"),
            ("ENROLLMENT", "核对何嘉宁德国项目报名材料", ["8"], 1, "缺少一份证明"),
        ], "部分材料需补充", "提醒学生补交"),
        (ADV2, 15, "APPROVED", "完成学生材料核对与客户回访。", [
            ("ENROLLMENT", "跟进何嘉宁补充材料", ["8"], 1, "已补齐"),
            ("CUSTOMER", "回访德国项目意向客户李思远", [], 1, "客户计划下周到访"),
            ("DELIVERY", "整理学生德语学习反馈", ["6", "7"], 2, "已反馈教学组"),
        ], "无", "准备下周到访接待"),
        (ADV2, 16, "SUBMITTED", "完成本周收尾与学生服务记录。", [
            ("CUSTOMER", "整理本周客户跟进记录", [], 1, "已归档"),
            ("DELIVERY", "更新德国项目学生服务台账", ["6", "7", "8"], 1, "已更新"),
            ("OTHER", "提交本周工作总结", [], 1, "已完成"),
        ], "无", "下周重点跟进签证"),
    ]
    teacher_days = [
        (TEACH1, 15, "APPROVED", "完成班级日常管理与学生谈话。", [
            ("DELIVERY", "组织班级晨会，强调考试纪律", [], 1, "全员参加"),
            ("ENROLLMENT", "与赵沐晴沟通英语测评准备情况", ["4"], 1, "状态良好"),
            ("OTHER", "整理班级考勤记录", [], 1, "已提交"),
        ], "无", "关注学生情绪状态"),
        (TEACH1, 16, "SUBMITTED", "完成本周班级管理与家长沟通。", [
            ("DELIVERY", "与 3 名家长电话沟通学生学习情况", ["3", "4", "5"], 3, "家长反馈良好"),
            ("OTHER", "更新班级学生档案", [], 1, "已完成"),
            ("ENROLLMENT", "跟进刘星宇课程出勤", ["5"], 1, "已恢复正常"),
        ], "个别学生作息不规律", "持续关注"),
    ]
    teacher2_days = [
        (TEACH2, 15, "APPROVED", "完成德国班日常管理与项目沟通。", [
            ("DELIVERY", "组织德国班行前安全培训", ["6", "7"], 1, "全员参加"),
            ("ENROLLMENT", "跟进黄雨桐签证材料", ["7"], 1, "材料已递交"),
            ("OTHER", "整理班级活动照片与记录", [], 1, "已归档"),
        ], "无", "跟进签证结果"),
        (TEACH2, 16, "SUBMITTED", "完成本周班级管理与学生关怀记录。", [
            ("DELIVERY", "与何嘉宁家长沟通报名材料", ["8"], 1, "已说明要求"),
            ("OTHER", "统计本周班级出勤", [], 1, "出勤正常"),
            ("ENROLLMENT", "跟进周思远德语学习进度", ["6"], 1, "进度正常"),
        ], "无", "下周安排模拟面试"),
    ]
    newcomer_days = [
        (NEWBIE, 16, "DRAFT", "学习客户接待流程并旁听顾问沟通。", [
            ("OTHER", "学习 CRM 系统操作", [], 1, "已完成基础操作"),
            ("CUSTOMER", "旁听顾问电话回访", [], 1, "记录沟通要点"),
        ], "对项目细节还不熟悉", "继续熟悉项目资料"),
    ]

    def insert_daily(user_id, day, status, summary, items, difficulties, next_plan):
        items_json = [{"category": c, "description": desc, "student_ids": [str(x) for x in ids],
                       "count": n, "result": result, "source_event_id": None}
                      for c, desc, ids, n, result in items]
        content = {"work_summary": summary, "items": items_json,
                   "difficulties": difficulties, "next_plan": next_plan}
        did = str(uuid4())
        ver = 2 if status in ("APPROVED", "SUBMITTED") else 1
        submitted = T(day, 18) if status in ("SUBMITTED", "APPROVED") else None
        approved_at = T(day + 1, 10) if status == "APPROVED" else None
        db.execute(text("""
            INSERT INTO m5_daily(id,user_id,dept_id,report_date,original_text,content,status,
                return_reason,version,approved_snapshot,submitted_at,updated_at,
                required_capabilities,approved_required_capabilities,approved_version,approved_at)
            VALUES (:id,:u,:d,:dt,:orig,CAST(:c AS json),:st,:rr,:v,CAST(:snap AS json),:sub,:upd,
                CAST('[]' AS jsonb),CAST('[]' AS jsonb),:av,:aa)
        """), {"id": did, "u": user_id, "d": DEPT, "dt": date(2026, 10, day),
               "orig": summary, "c": J(content), "st": status,
               "rr": "请补充客户跟进的具体结果与下一步计划。" if status == "RETURNED" else "",
               "v": ver,
               "snap": J(content) if status == "APPROVED" else None,
               "sub": submitted, "upd": approved_at or submitted or T(day, 18),
               "av": 1 if status == "APPROVED" else None, "aa": approved_at})
        if status == "APPROVED":
            db.execute(text("""
                INSERT INTO m5_daily_revision(id,daily_id,version,approved_by,approved_at,
                    content,required_capabilities)
                VALUES (:id,:did,1,:by,:at,CAST(:c AS jsonb),CAST('[]' AS jsonb))
            """), {"id": str(uuid4()), "did": did, "by": HEAD, "at": approved_at,
                   "c": J(content)})
        return did

    for group in (advisor_days, advisor2_days, teacher_days, teacher2_days, newcomer_days):
        for uid, day, status, summary, items, diff, plan in group:
            insert_daily(uid, day, status, summary, items, diff, plan)
    print("dailies inserted")

    # ---------------- 报告 ----------------
    reports = [
        ("CUSTOMER_OPERATION", "客户经营周报（10.12-10.16）", 12, 16, [], [
            ("new_customers", "期间新增客户", 5, "人", "created_date 在统计范围内，按客户 ID 去重"),
            ("intent_students", "当前未签约意向客户", 5, "人", "意向已填写且状态为 NEW/FOLLOWING"),
            ("enrolled", "期间签约客户", 0, "人", "signed_at 在统计范围内"),
            ("lost_customers", "期间流失客户", 2, "人", "lost_at 在统计范围内"),
            ("conversion_rate", "新增客户当前签约率", 0, "%", "新增客户中当前已签约人数/本期新增客户数"),
            ("previous_new_customers", "上一等长期间新增客户", 3, "人", "上一等长期间"),
        ], "本周新增客户 5 人，主要来源为官网表单与客服对话。当前未签约意向客户 5 人，"
           "其中王浩然、刘佳琪已进入深度沟通阶段。本周流失客户 2 人，原因分别为预算与时间安排不匹配、"
           "已选择其他机构。建议下周重点跟进到访意向较强的客户，并完善费用说明材料。"),
        ("DAILY_DAY", "日报日汇总（10.16）", 16, 16, [], [
            ("approved_daily", "已通过有效日报", 0, "篇", "每员工每日一份，使用最近通过内容"),
            ("customer", "客户跟进", 5, "次", "日报申报工作量"),
            ("delivery", "学生交付", 4, "次", "日报申报工作量"),
            ("enrollment", "入学跟踪", 4, "次", "日报申报工作量"),
            ("expected_daily", "范围员工自然日应报基数", 4, "篇", "有效员工数×自然日数"),
            ("daily_coverage", "审核通过覆盖率", 0, "%", "已通过日报/自然日应报基数"),
        ], "10 月 16 日共有 4 名员工提交日报，其中 0 篇已通过审核，4 篇待主管审核。"
           "工作内容集中在客户回访、材料核对与班级管理。建议主管尽快完成审核，以便纳入周报统计。"),
        ("DAILY_WEEK", "日报周汇总（10.12-10.16）", 12, 16, [], [
            ("approved_daily", "已通过有效日报", 10, "篇", "每员工每日一份，使用最近通过内容"),
            ("customer", "客户跟进", 12, "次", "日报申报工作量"),
            ("delivery", "学生交付", 9, "次", "日报申报工作量"),
            ("enrollment", "入学跟踪", 8, "次", "日报申报工作量"),
            ("expected_daily", "范围员工自然日应报基数", 20, "篇", "有效员工数×自然日数"),
            ("daily_coverage", "审核通过覆盖率", 50, "%", "已通过日报/自然日应报基数"),
        ], "本周共 10 篇日报通过审核，覆盖率 50%。客户跟进与学生交付是主要工作内容。"
           "部分员工日报仍待审核或已退回补充，建议主管在周一上午完成审核闭环。"),
        ("PSYCH_WEEK", "心理关怀周报（10.12-10.16）", 12, 16, [], [
            ("observed_student_days", "有效观测学生日", 12, "学生日", "同一学生同一自然日取最后有效版本"),
            ("unobserved_student_days", "缺少有效观测的学生日", 18, "学生日", "不将未观测自动判为健康"),
            ("observation_coverage", "有效观测覆盖率", 40, "%", "有效观测学生日/应观测学生日"),
            ("emotion_healthy", "健康", 6, "学生日", "情绪状态统计"),
            ("emotion_negative", "消极", 4, "学生日", "情绪状态统计"),
            ("emotion_very_negative", "极度消极", 2, "学生日", "情绪状态统计"),
            ("high_risk", "高优先级关怀事件", 1, "项", "包括规则直接触发事件"),
        ], "本周共记录 12 个有效观测学生日，覆盖 6 名已授权学生。整体情绪以健康与轻度消极为主，"
           "其中 1 名学生连续出现消极情绪并触发高优先级预警，已进入人工复核流程。"
           "建议班主任持续跟进，并在保护隐私的前提下与家长沟通。"),
        ("COMPLAINT_WEEK", "投诉与售后周报（10.12-10.16）", 12, 16, [], [
            ("open_tickets", "未关闭投诉", 2, "项", "状态非 CLOSED/RESOLVED"),
            ("overdue_tickets", "当前超期未解决投诉", 1, "项", "超过 SLA 且未解决"),
            ("rating_count", "满意度样本", 1, "份", "已评分且评价时间在范围内"),
            ("rating_average", "平均满意度", 5, "分", "仅统计已评分工单"),
            ("reopened", "重开次数", 0, "次", "学生重新打开次数"),
            ("first_response_hours", "平均首次响应时长", 2.5, "小时", "首次响应时间-创建时间"),
            ("resolution_hours", "平均解决时长", 18.0, "小时", "解决时间-创建时间"),
        ], "本周共受理售后 4 件，其中投诉 2 件、建议 1 件、咨询 1 件。已解决并关闭 2 件，"
           "平均满意度 5 分；仍有 2 件投诉处理中，其中 1 件接近 SLA 时限。建议优先处理教材发放与课程通知类问题。"),
        ("MANAGER_WEEK", "部门主管周报（10.12-10.16）", 12, 16, [], [
            ("approved_daily", "已通过有效日报", 10, "篇", "每员工每日一份"),
            ("new_customers", "期间新增客户", 5, "人", "按创建日期与客户 ID 统计"),
            ("enrolled_students", "期间签约客户", 0, "人", "按签约日期统计"),
            ("daily_coverage", "审核通过覆盖率", 50, "%", "已通过日报/自然日应报基数"),
            ("open_tickets", "未关闭投诉", 2, "项", "状态非 CLOSED/RESOLVED"),
        ], "本周部门新增客户 5 人，暂无新签约；完成 10 篇日报审核，覆盖率 50%。"
           "团队重点推进德国双元制项目宣讲与学生材料核对，整体执行正常。"
           "存在的问题是部分日报提交较晚、客户费用顾虑较多。"
           "下周计划：完成待审日报闭环，重点跟进 5 名意向客户，并组织一次项目说明会。"),
    ]
    for kind, title, sd, ed, caps, metrics, narrative in reports:
        mlist = [{"key": k, "label": l, "value": v, "unit": u, "formula": f, "available": True}
                 for k, l, v, u, f in metrics]
        required = ["psych_access_enabled"] if kind == "PSYCH_WEEK" else \
                   ["can_handle_feedback"] if kind == "COMPLAINT_WEEK" else []
        db.execute(text("""
            INSERT INTO m5_report(id,owner_id,dept_id,kind,scope_employee_ids,scope_student_ids,
                title,start_date,end_date,narrative,metrics,scope,ai_status,warnings,status,
                version,created_at,updated_at,required_capabilities,snapshot_id)
            VALUES (:id,:owner,:d,:kind,CAST(:sei AS json),CAST(:ssi AS json),:title,:sd,:ed,
                :narrative,CAST(:metrics AS json),:scope,'MANUAL',CAST(:warnings AS json),'DRAFT',
                1,:ca,:ua,CAST(:caps AS jsonb),NULL)
        """), {"id": str(uuid4()), "owner": HEAD, "d": DEPT, "kind": kind,
               "sei": J([]), "ssi": J([]), "title": title,
               "sd": date(2026, 10, sd), "ed": date(2026, 10, ed),
               "narrative": narrative, "metrics": J(mlist),
               "scope": "本部门 · 国际教育事业部",
               "warnings": J(["来源：正式业务表与 M5 审核通过的日报；客户意向为当前状态，签约不等同于实际入学"]),
               "ca": T(16, 17), "ua": T(16, 17), "caps": J(required)})
    print("reports inserted")

    # ---------------- 通知 ----------------
    notices = [
        (HEAD, "SYSTEM", "有日报待审核", "陈志远、林嘉怡等提交的 4 篇日报等待审核。", "demo:head:daily"),
        (HEAD, "PSYCH_ALERT", "有待复核的关怀事项", "王梓涵连续情绪消极，请及时复核并跟进。", "demo:head:psych"),
        (HEAD, "SYSTEM", "新售后工单", "收到 2 件新的投诉，请安排处理。", "demo:head:ticket"),
        (ADV1, "SYSTEM", "日报审核已通过", "你 10 月 15 日的日报已通过审核。", "demo:adv1:daily"),
        (ADV1, "SYSTEM", "新客户待跟进", "张一诺通过官网留下咨询信息，请及时联系。", "demo:adv1:lead17"),
        (ADV2, "SYSTEM", "日报审核已通过", "你 10 月 15 日的日报已通过审核。", "demo:adv2:daily"),
        (ADV2, "SYSTEM", "新客户待跟进", "李思远通过客服对话留资，请及时联系。", "demo:adv2:lead18"),
        (STU[1], "SYSTEM", "申请进度更新", "你的新加坡院校申请已收到录取通知，请查看详情。", "demo:stu1:case"),
        (STU[2], "SYSTEM", "申请进度更新", "德国双元制项目材料已进入企业审核阶段。", "demo:stu2:case"),
        (STU[3], "SYSTEM", "申请已通过", "你的请假申请已通过。", "demo:stu3:leave"),
        (STU[4], "SERVICE_DECISION", "申请被驳回", "你的外出请假申请被驳回，原因：当天有阶段测评。", "demo:stu4:leave"),
        (STU[5], "SYSTEM", "售后工单已解决", "你的建议已处理完成，感谢反馈。", "demo:stu5:ticket"),
        (STU[6], "SYSTEM", "日程提醒", "德语 B1 模拟考试将在 5 天后开始。", "demo:stu6:sched"),
        (NEWBIE, "SYSTEM", "欢迎使用教育服务平台", "请先完成个人资料确认，再开始客户接待学习。", "demo:newbie:welcome"),
    ]
    for uid, cat, title, content, key in notices:
        notification(db, uid, cat, title, content, key)
    print("notifications inserted")

    # ---------------- 活动报名 ----------------
    db.execute(text("""
        INSERT INTO event_registration(event_id,student_profile_id,lead_id,registrant_name,mobile,
            status,request_key,registered_at,version)
        VALUES (1,:sp,NULL,'王梓涵','13911110002','REGISTERED',CAST(:rk AS uuid),:rt,1)
    """), {"sp": PROFILE[2], "rk": str(uuid4()), "rt": T(16, 11)})
    print("event registration inserted")

print("seed done")
