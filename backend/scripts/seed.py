"""
种子数据脚本（M1-10）

作用：一键初始化开发环境 —— 建账号、部门、班级、项目、活动。
新人 clone 代码后跑这个，就能**直接登录**。

用法：
    cd backend && source .venv/bin/activate
    python -m scripts.seed

⚠️ 幂等：重复跑不会重复建（已存在的跳过）。
⚠️ 这些是**开发测试账号**，上线前必须删掉或改密码。
"""
import sys
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select, text

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.academic_schedule import StudentAcademicSchedule
from app.models.application_progress import StudentApplicationProgress
from app.models.enrollment import StudentCourseEnrollment
from app.models.organization import SysClass, SysDepartment
from app.models.score import StudentScore
from app.models.student import StudentProfile
from app.models.user import SysUser

# ---------------- 测试账号 ----------------
# 账号 / 明文密码 / 角色 / 说明
ACCOUNTS = [
    ("admin",      "admin123",   "EMPLOYEE", "ADMIN",          "管理员 · 全域"),
    ("heada",      "test123",    "EMPLOYEE", "SENIOR_ADVISOR", "A部门主管"),
    ("advisor01",  "test123",    "EMPLOYEE", "ADVISOR",        "顾问 · 带学生"),
    ("newcomer01", "test123",    "EMPLOYEE", "NEWCOMER",       "新人 · 受限"),
    ("student01",  "test123",    "STUDENT",  None,             "测试学生"),
]

DEPARTMENTS = [
    ("TECH", "双元制事业部"),
    ("SMART", "智能装备事业部"),
    ("AFTER", "课后服务事业部"),
    ("STUDY", "研学服务事业部"),
    ("EVENT", "科技赛事事业部"),
    ("HR", "人事行政部"),
]

CLASSES = [
    ("CLS_A", "2026春季A班", "TECH", "德语+专业"),
]

PROJECTS = [
    ("SG_222", "新加坡 2+2 定向培养本科班", "新加坡", "初中毕业生", "本科"),
    ("SG_0512", "新加坡 0.5/1+2 定向培养本科班", "新加坡", "高二/高中毕业", "本科"),
    ("SG_HOTEL", "新加坡 6+6 酒店运营大专就业班", "新加坡", "职高中专", "大专"),
    ("DE_DUAL", "中德精英人才共建计划（德国双元制）", "德国", "高中及以上", "职业资格"),
]

# (标题, 地点/线上链接, 几日后, 名额)
EVENTS = [
    ("新加坡项目说明会", "腾讯会议：xxx-xxx-xxx", 7, 100),
    ("德国双元制招生官见面会", "广州市越秀区东风东路723号", 14, 50),
]


def seed() -> None:
    db = SessionLocal()
    try:
        print("=" * 60)
        print("开始初始化种子数据")
        print("=" * 60)

        # ---------- 部门 ----------
        print("\n[1/5] 部门")
        for code, name in DEPARTMENTS:
            if not db.scalar(select(SysDepartment.id).where(SysDepartment.code == code)):
                db.add(SysDepartment(code=code, name=name, is_active=True))
                print(f"  + {code} {name}")
        db.commit()
        dept_id = {c: db.scalar(select(SysDepartment.id).where(SysDepartment.code == c))
                   for c, _ in DEPARTMENTS}

        # ---------- 账号 ----------
        print("\n[2/5] 账号")
        created_creds = []
        for username, pwd, utype, role, desc in ACCOUNTS:
            if db.scalar(select(SysUser.id).where(SysUser.username == username)):
                print(f"  = {username}（已存在，跳过）")
                continue
            user = SysUser(
                username=username,
                password_hash=hash_password(pwd),
                real_name=desc,
                user_type=utype,
                employee_role=role,
                # ⚠️ 学生不能有 dept_id（数据库约束）
                dept_id=None if utype == "STUDENT" else dept_id["TECH"],
                status="NORMAL",
                must_change_password=False,   # 开发账号不强制改密，方便测试
                token_version=0,
            )
            db.add(user)
            created_creds.append((username, pwd, desc))
            print(f"  + {username} / {pwd}   ({desc})")
        db.commit()

        # 指定 A 部门主管（唯一事实源）
        head = db.scalar(select(SysUser.id).where(SysUser.username == "heada"))
        if head:
            db.execute(text("UPDATE sys_department SET head_user_id=:h WHERE code='TECH'"),
                       {"h": head})
            db.commit()
            print(f"  · 已指定 heada 为 TECH 部门主管")

        # ---------- 班级 ----------
        print("\n[3/5] 班级")
        for code, name, dept_code, course_type in CLASSES:
            if not db.scalar(select(SysClass.id).where(SysClass.code == code)):
                teacher = db.scalar(select(SysUser.id).where(SysUser.username == "advisor01"))
                db.add(SysClass(code=code, name=name, dept_id=dept_id[dept_code],
                                course_type=course_type, head_teacher_id=teacher))
                print(f"  + {name}（班主任：advisor01）")
        db.commit()

        # ---------- 学生档案 ----------
        print("\n[4/5] 学生档案")
        stu = db.scalar(select(SysUser.id).where(SysUser.username == "student01"))
        advisor = db.scalar(select(SysUser.id).where(SysUser.username == "advisor01"))
        cls = db.scalar(select(SysClass.id).where(SysClass.name == "2026春季A班"))
        if stu:
            exists = db.scalar(text("SELECT id FROM student_profile WHERE user_id=:u"), {"u": stu})
            if not exists:
                db.execute(text("""
                    INSERT INTO student_profile(user_id, advisor_user_id, dept_id, class_id, status)
                    VALUES (:u, :a, :d, :c, 'ENROLLED')
                """), {"u": stu, "a": advisor, "d": dept_id["TECH"], "c": cls})
                db.commit()
                print(f"  + student01 的档案（顾问：advisor01，班级：2026春季A班）")

        # ---------- 课程项目 / 活动 ----------
        print("\n[5/5] 课程项目 / 活动")
        for code, name, country, aud, level in PROJECTS:
            if not db.scalar(text("SELECT id FROM course_project WHERE code=:c"), {"c": code}):
                db.execute(text("""
                    INSERT INTO course_project(code,name,country,education_level,description,is_published)
                    VALUES (:c,:n,:co,:a,:d,true)
                """), {"c": code, "n": name, "co": country, "a": aud,
                       "d": f"{name} —— 面向{aud}"})
                print(f"  + {name}")
        db.commit()

        organizer = db.scalar(select(SysUser.id).where(SysUser.username == "advisor01"))
        now = datetime.now(timezone.utc)
        for title, loc, days, cap in EVENTS:
            if not db.scalar(text("SELECT id FROM event_lecture WHERE title=:t"), {"t": title}):
                db.execute(text("""
                    INSERT INTO event_lecture(title,organizer_user_id,description,location,
                                              start_at,end_at,signup_deadline,capacity,status)
                    VALUES (:t,:o,:d,:loc,:s,:e,:sd,:c,'OPEN')
                """), {"t": title, "o": organizer, "d": f"{title}", "loc": loc,
                       "s": now + timedelta(days=days),
                       "e": now + timedelta(days=days, hours=2),
                       "sd": now + timedelta(days=days - 1), "c": cap})
                print(f"  + {title}")
        db.commit()

        # ---------- 学生课程 / 成绩 / 日程 / 申请进度（M4 测试数据）----------
        print("\n[6/6] 学生课程 / 成绩 / 日程 / 申请进度")
        prof = db.scalar(select(StudentProfile.id).where(StudentProfile.user_id == stu))
        if prof:
            now = datetime.now(timezone.utc)
            proj_sg = db.scalar(text("SELECT id FROM course_project WHERE code='SG_222'"))
            proj_de = db.scalar(text("SELECT id FROM course_project WHERE code='DE_DUAL'"))

            # 课程关联（一名学生多项目）
            for pid in (proj_sg, proj_de):
                if pid and not db.scalar(
                    select(StudentCourseEnrollment.id).where(
                        StudentCourseEnrollment.student_profile_id == prof,
                        StudentCourseEnrollment.course_project_id == pid,
                    )
                ):
                    db.add(StudentCourseEnrollment(
                        student_profile_id=prof, course_project_id=pid, status="ENROLLED"))
                    print(f"  + 课程关联 course_project_id={pid}")

            # 成绩（TEST，只读，不提供业务写接口）
            if not db.scalar(select(func.count()).select_from(StudentScore)
                             .where(StudentScore.student_profile_id == prof)):
                today = now.date()
                db.add_all([
                    StudentScore(student_profile_id=prof, subject="数学", score_type="NUMERIC",
                                 score_text="85", score_numeric=Decimal("85"),
                                 max_score=Decimal("100"), graded_at=today,
                                 recorded_by_user_id=advisor, remark="合成测试数据"),
                    StudentScore(student_profile_id=prof, subject="英语", score_type="NUMERIC",
                                 score_text="92", score_numeric=Decimal("92"),
                                 max_score=Decimal("100"), graded_at=today,
                                 recorded_by_user_id=advisor, remark="合成测试数据"),
                    StudentScore(student_profile_id=prof, subject="德语", score_type="GRADE",
                                 score_text="B+", graded_at=today,
                                 recorded_by_user_id=advisor, remark="合成测试数据"),
                    StudentScore(student_profile_id=prof, subject="体育", score_type="PASS_FAIL",
                                 score_text="PASS", graded_at=today,
                                 recorded_by_user_id=advisor, remark="合成测试数据"),
                ])
                print("  + 4 条合成成绩（TEST）")

            # 教务日程（TEST）
            if not db.scalar(select(func.count()).select_from(StudentAcademicSchedule)
                             .where(StudentAcademicSchedule.student_profile_id == prof)):
                db.add_all([
                    StudentAcademicSchedule(
                        student_profile_id=prof, schedule_type="EXAM", title="德语期中考试",
                        description="合成测试数据", start_at=now + timedelta(days=7),
                        end_at=now + timedelta(days=7, hours=2), location="A栋301",
                        data_source="TEST", created_by_user_id=advisor),
                    StudentAcademicSchedule(
                        student_profile_id=prof, schedule_type="DEADLINE",
                        title="新加坡项目申请材料截止", description="合成测试数据",
                        start_at=now + timedelta(days=20), data_source="TEST",
                        created_by_user_id=advisor),
                    StudentAcademicSchedule(
                        student_profile_id=prof, schedule_type="CLASS", title="德语专业课",
                        description="合成测试数据", start_at=now + timedelta(days=1),
                        end_at=now + timedelta(days=1, hours=2), location="B栋205",
                        data_source="TEST", created_by_user_id=advisor),
                ])
                print("  + 3 条合成日程（TEST）")

            # 申请进度（TEST，同 case_no 多事件时间线）
            if not db.scalar(select(func.count()).select_from(StudentApplicationProgress)
                             .where(StudentApplicationProgress.student_profile_id == prof)):
                case = uuid.UUID("11111111-1111-1111-1111-111111111111")
                ev1 = StudentApplicationProgress(
                    case_no=case, student_profile_id=prof, sequence_no=1, previous_id=None,
                    item_type="SCHOOL", title="新加坡 2+2 定向培养本科班申请",
                    target_country="新加坡", target_school="新加坡示范学院",
                    target_program="本科", stage="SUBMITTED", event_kind="STAGE",
                    assignee_user_id=advisor, recorded_by_user_id=advisor,
                    data_source="TEST", occurred_at=now - timedelta(days=30),
                    request_key=uuid.uuid4())
                db.add(ev1)
                db.flush()
                db.add(StudentApplicationProgress(
                    case_no=case, student_profile_id=prof, sequence_no=2, previous_id=ev1.id,
                    item_type="SCHOOL", title="新加坡 2+2 定向培养本科班申请",
                    target_country="新加坡", target_school="新加坡示范学院",
                    target_program="本科", stage="PROCESSING", event_kind="STAGE",
                    assignee_user_id=advisor, recorded_by_user_id=advisor,
                    data_source="TEST", occurred_at=now - timedelta(days=10),
                    request_key=uuid.uuid4()))
                print("  + 申请进度 2 条事件（TEST）")

        db.commit()

        # ---------- 汇总 ----------
        print("\n" + "=" * 60)
        print("完成！测试账号：")
        print("=" * 60)
        print(f"{'账号':<12} {'密码':<10} {'说明'}")
        print("-" * 60)
        for username, pwd, desc in created_creds:
            print(f"{username:<12} {pwd:<10} {desc}")
        if not created_creds:
            print("（账号都已存在，未新建）")
        print("-" * 60)
        print("\n登录测试：")
        print('  curl -X POST http://localhost:8000/api/v1/auth/login \\')
        print('    -H "Content-Type: application/json" \\')
        print('    -d \'{"username":"admin","password":"admin123"}\'')
        print()

    finally:
        db.close()


if __name__ == "__main__":
    seed()
