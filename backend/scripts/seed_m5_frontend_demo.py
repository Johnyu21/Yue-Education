"""Initialize the explicitly requested frontend demo accounts without overwriting data.

Default: read-only plan. Use --apply --database <expected database> to insert.
Existing account passwords are never reset. All new rows commit together.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from sqlalchemy import bindparam, text
from app.core.config import settings
from app.core.security import hash_password
from app.db.session import engine

DEMO_PASSWORD = 'FrontQA-2026!'
USERNAMES = ['ui_first','ui_advisor','ui_teacher','ui_head','ui_admin','ui_advisor2','ui_teacher2'] + [f'139111100{i:02d}' for i in range(1,8)]
CODES = {'sys_department': ['UI_QA'], 'sys_class': ['UI_CLASS','UI_CLASS_B'], 'course_project': ['UI_PROJECT','UI_GERMANY']}


def in_rows(db, sql, key, values):
    statement = text(sql).bindparams(bindparam(key, expanding=True))
    return db.execute(statement, {key: values}).mappings().all()


def inspect(db):
    accounts = in_rows(db, 'SELECT id,username,real_name,user_type,employee_role,dept_id FROM sys_user WHERE username IN :names ORDER BY username', 'names', USERNAMES)
    conflicts = {table: [dict(row) for row in in_rows(db, 'SELECT id,code FROM '+table+' WHERE code IN :codes', 'codes', codes)] for table,codes in CODES.items()}
    lead_mobiles = ['13811110001'] + [f'139111100{i:02d}' for i in range(2,8)]
    leads = in_rows(db, 'SELECT id,mobile FROM crm_lead WHERE mobile IN :mobiles','mobiles',lead_mobiles)
    result = {'database':settings.postgres_db,'schema':settings.postgres_schema,'account_count':len(accounts),'existing_accounts':[dict(r) for r in accounts],'code_matches':conflicts,'lead_matches':[dict(r) for r in leads]}
    if not accounts and not any(conflicts.values()) and not leads:
        result['state']='READY_TO_INSERT'
    elif len(accounts)==len(USERNAMES) and all(len(conflicts[t])==len(CODES[t]) for t in CODES):
        dept_id=conflicts['sys_department'][0]['id']
        employees=[r for r in accounts if r['username'].startswith('ui_')]
        student_accounts=[r for r in accounts if r['username'].startswith('139')]
        profiles=in_rows(db,'SELECT user_id,dept_id,is_demo FROM student_profile WHERE user_id IN :ids','ids',[r['id'] for r in student_accounts])
        if (all(r['user_type']=='EMPLOYEE' and r['dept_id']==dept_id for r in employees)
            and all(r['user_type']=='STUDENT' for r in student_accounts)
            and len(profiles)==7 and all(r['dept_id']==dept_id and r['is_demo'] for r in profiles)):
            result['state']='ALREADY_INITIALIZED'
        else:
            result['state']='CONFLICT'
    else:
        result['state']='CONFLICT'
    return result


def create_demo(db):
    password=hash_password(DEMO_PASSWORD)
    def insert(sql,**params):return db.execute(text(sql+' RETURNING id'),params).scalar_one()
    dept=insert("INSERT INTO sys_department(code,name) VALUES ('UI_QA','界面联调部门')")
    def employee(username,name,role='ADVISOR',psych=False,feedback=False):
        return insert("INSERT INTO sys_user(username,password_hash,real_name,user_type,employee_role,dept_id,psych_access_enabled,can_handle_feedback,must_change_password) VALUES (:u,:p,:n,'EMPLOYEE',:r,:d,:psy,:fb,false)",u=username,p=password,n=name,r=role,d=dept,psy=psych,fb=feedback)
    newcomer=employee('ui_first','首次联调员工',role='NEWCOMER')
    db.execute(text('UPDATE sys_user SET must_change_password=true WHERE id=:u'), {'u':newcomer})
    advisor=employee('ui_advisor','联调顾问')
    teacher=employee('ui_teacher','联调班主任',psych=True)
    head=employee('ui_head','联调主管',psych=True,feedback=True)
    administrator=employee('ui_admin','联调管理员',role='ADMIN',psych=True,feedback=True)
    db.execute(text('UPDATE sys_department SET head_user_id=:u WHERE id=:d'),{'u':head,'d':dept})
    cls=insert("INSERT INTO sys_class(code,name,dept_id,head_teacher_id) VALUES ('UI_CLASS','界面联调班',:d,:t)",d=dept,t=teacher)
    student=insert("INSERT INTO sys_user(username,password_hash,real_name,user_type,must_change_password) VALUES ('13911110001',:p,'联调学生','STUDENT',false)",p=password)
    lead=insert("INSERT INTO crm_lead(name,mobile,source,status,dept_id,owner_user_id,interest_level,request_key) VALUES ('联调客户','13811110001','MANUAL','NEW',:d,:a,'HIGH',:k)",d=dept,a=advisor,k=uuid4())
    project=insert("INSERT INTO course_project(code,name,country,description,default_dept_id,is_published) VALUES ('UI_PROJECT','界面联调升学项目','新加坡','仅用于隔离界面联调的合成项目资料。',:d,true)",d=dept)
    profile=insert("INSERT INTO student_profile(user_id,advisor_user_id,dept_id,class_id,converted_lead_id,psych_consent_status,psych_consent_at,psych_consent_version,is_demo) VALUES (:u,:a,:d,:c,:l,'GRANTED',now(),'v1',true)",u=student,a=advisor,d=dept,c=cls,l=lead)
    insert("INSERT INTO student_course_enrollment(student_profile_id,course_project_id,status,enrolled_at) VALUES (:s,:p,'ENROLLED',now())",s=profile,p=project)
    insert("INSERT INTO student_score(student_profile_id,subject,score_type,score_text,score_numeric,max_score,graded_at,data_source,recorded_by_user_id) VALUES (:s,'界面联调英语','NUMERIC','88','88','100',current_date,'MANUAL',:u)",s=profile,u=teacher)
    insert("INSERT INTO student_academic_schedule(student_profile_id,schedule_type,title,start_at,status,data_source,created_by_user_id) VALUES (:s,'EXAM','界面联调考试',now()+interval '7 days','SCHEDULED','MANUAL',:u)",s=profile,u=teacher)
    insert("INSERT INTO event_lecture(title,description,organizer_user_id,host_department_id,course_project_id,start_at,end_at,signup_deadline,capacity,status) VALUES ('界面联调开放日','隔离测试活动',:o,:d,:p,now()+interval '10 days',now()+interval '10 days 2 hours',now()+interval '9 days',20,'OPEN')",o=head,d=dept,p=project)
    advisor2=employee('ui_advisor2','林顾问（演示）')
    teacher2=employee('ui_teacher2','陈老师（演示）',psych=True)
    cls2=insert("INSERT INTO sys_class(code,name,dept_id,head_teacher_id) VALUES ('UI_CLASS_B','德国项目二班（演示）',:d,:t)",d=dept,t=teacher2)
    project2=insert("INSERT INTO course_project(code,name,country,description,default_dept_id,is_published) VALUES ('UI_GERMANY','德国职业教育体验项目（演示）','德国','课程演示资料，非真实招生承诺。',:d,true)",d=dept)
    extra_students=[]
    for index,name in enumerate(['王梓涵','赵沐晴','刘星宇','周思远','黄雨桐','何嘉宁'],start=2):
        mobile='139111100'+str(index).zfill(2)
        advisor_id=advisor if index<=4 else advisor2
        teacher_id=teacher if index<=4 else teacher2
        class_id=cls if index<=4 else cls2
        project_id=project if index<=4 else project2
        student_id=insert("INSERT INTO sys_user(username,password_hash,real_name,user_type,must_change_password,contact_info) VALUES (:u,:p,:n,'STUDENT',false,:u)",u=mobile,p=password,n=name+'（演示）')
        source_id=insert("INSERT INTO crm_lead(name,mobile,source,status,dept_id,owner_user_id,interest_level,request_key,signed_at) VALUES (:n,:m,'MANUAL','SIGNED',:d,:a,'HIGH',:k,now())",n=name+'（演示）',m=mobile,d=dept,a=advisor_id,k=uuid4())
        student_profile=insert("INSERT INTO student_profile(user_id,advisor_user_id,dept_id,class_id,converted_lead_id,gender,city,education,enrollment_date,is_demo) VALUES (:u,:a,:d,:c,:l,:g,'广州','高中',current_date,true)",u=student_id,a=advisor_id,d=dept,c=class_id,l=source_id,g='女' if index%2==0 else '男')
        insert("INSERT INTO student_course_enrollment(student_profile_id,course_project_id,status,enrolled_at) VALUES (:s,:p,'ENROLLED',now())",s=student_profile,p=project_id)
        insert("INSERT INTO student_score(student_profile_id,subject,score_type,score_text,score_numeric,max_score,graded_at,data_source,recorded_by_user_id) VALUES (:s,'英语阶段测评','NUMERIC',:v,:numeric,'100',current_date,'MANUAL',:u)",s=student_profile,v=str(75+index*2),numeric=75+index*2,u=teacher_id)
        insert("INSERT INTO student_academic_schedule(student_profile_id,schedule_type,title,start_at,status,data_source,created_by_user_id) VALUES (:s,'EXAM','英语阶段测评（演示）',now()+interval '5 days','SCHEDULED','MANUAL',:u)",s=student_profile,u=teacher_id)
        extra_students.append(student_id)
    for user_id in [newcomer,advisor,teacher,head,administrator,advisor2,teacher2,student]+extra_students:
        insert("INSERT INTO notification(recipient_user_id,category,title,content,business_event_key) VALUES (:u,'SYSTEM','欢迎使用教育服务平台','这是演示通知。点击消息可进入通知中心查看详情。',:k)",u=user_id,k='ui-demo-welcome:'+str(user_id))
    for index,user_id in enumerate([advisor,teacher,head,administrator,student]):
        insert("INSERT INTO notification(recipient_user_id,category,title,content,business_event_key) VALUES (:u,'SYSTEM','本周服务安排已更新','请关注学生阶段测评与入学材料准备安排。此消息为课程演示资料。',:k)",u=user_id,k='ui-demo-schedule:'+str(user_id))
    db.execute(text("UPDATE sys_user SET contact_info='020-88880001' WHERE id=:u"),{'u':advisor})
    db.execute(text("UPDATE sys_user SET contact_info='020-88880002' WHERE id=:u"),{'u':teacher})



def initialize(db):
    db.execute(text('SELECT pg_advisory_xact_lock(9102026)'))
    before=inspect(db)
    if before['state']=='ALREADY_INITIALIZED':
        return {**before,'action':'SKIPPED_EXISTING','passwords_reset':False}
    if before['state']!='READY_TO_INSERT':
        raise RuntimeError('Demo identifiers conflict with existing records; no data was overwritten')
    create_demo(db)
    after=inspect(db)
    if after['state']!='ALREADY_INITIALIZED':
        raise RuntimeError('Demo initialization validation failed; transaction will roll back')
    return {**after,'action':'CREATED','created_accounts':14,'created_students':7,'created_advisors':2,'created_teachers':2,'passwords_reset':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--database',help='Explicitly name the database being initialized')
    args=parser.parse_args()
    if settings.environment not in {'dev','test'}:
        raise SystemExit('Demo data initialization is only enabled for local development/test environments')
    if args.apply and args.database!=settings.postgres_db:
        raise SystemExit('--database must exactly match the configured database')
    if not args.apply:
        with engine.connect() as db:
            result=inspect(db)
        print(json.dumps(result,ensure_ascii=False,default=str))
        return
    with engine.begin() as db:
        result=initialize(db)
    report=Path(__file__).resolve().parents[1]/'logs'/('frontend-demo-init-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')
    report.parent.mkdir(parents=True,exist_ok=True)
    report.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    print(json.dumps({'database':settings.postgres_db,'schema':settings.postgres_schema,'action':result['action'],'accounts':result['account_count'],'report':str(report),'passwords_reset':False},ensure_ascii=False))


if __name__=='__main__':
    main()
