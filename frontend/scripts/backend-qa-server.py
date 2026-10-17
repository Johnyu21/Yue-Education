"""Temporary UI test server: dedicated *_test database and a fresh random schema only."""
import os
from pathlib import Path
import re
import sys
import tempfile
import threading
from uuid import uuid4
BACKEND=Path(__file__).resolve().parents[2]/'backend'
sys.path.insert(0,str(BACKEND))
from dotenv import dotenv_values
values=dotenv_values(BACKEND/'.env.test')
if values.get('TEST_DATABASE_ENABLED')!='true' or values.get('ENVIRONMENT')!='test' or not values.get('POSTGRES_DB','').endswith('_test'):
    raise SystemExit('Dedicated test database guard rejected')
for key,value in values.items():
    if value is not None:os.environ[key]=value
schema='test_'+uuid4().hex
os.environ.update(POSTGRES_SCHEMA=schema,M5_AI_MODE='DISABLED',DIFY_MODE='mock',SCHEDULER_ENABLED='false')
from sqlalchemy import create_engine,text
from app.core.config import settings
from app.core.security import hash_password
from app.db.migrate import migrate
admin=create_engine(settings.database_url,hide_parameters=True)
server=None
try:
    with admin.begin() as db:db.exec_driver_sql('CREATE SCHEMA "'+schema+'"')
    with admin.begin() as db:migrate(db)
    with tempfile.TemporaryDirectory(prefix='yue-frontend-qa-') as files:
        settings.file_storage_root=files
        password=hash_password('FrontQA-2026!')
        with admin.begin() as db:
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
            profile=insert("INSERT INTO student_profile(user_id,advisor_user_id,dept_id,class_id,converted_lead_id,psych_consent_status,psych_consent_at,psych_consent_version) VALUES (:u,:a,:d,:c,:l,'GRANTED',now(),'v1')",u=student,a=advisor,d=dept,c=cls,l=lead)
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
        import uvicorn
        from app.main import app
        @app.get("/api/v1/__ui_qa__/identity", include_in_schema=False)
        def qa_identity():
            return {"isolated": True, "database_is_test": os.environ["POSTGRES_DB"].endswith("_test")}
        server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=int(os.environ.get('UI_QA_BACKEND_PORT','8001')),log_level='warning'))
        thread=threading.Thread(target=server.run,daemon=True)
        thread.start()
        import time
        deadline=time.monotonic()+20
        while not server.started and thread.is_alive() and time.monotonic()<deadline:time.sleep(.05)
        if not server.started:raise RuntimeError('QA server failed')
        print('UI_QA_READY',flush=True)
        while True:
            command=sys.stdin.readline()
            if not command or command.strip()=='stop':break
        server.should_exit=True
        thread.join(timeout=15)
finally:
    if server is not None:server.should_exit=True
    from app.db.session import engine
    engine.dispose()
    if not re.fullmatch(r'test_[a-f0-9]{32}',schema):raise RuntimeError('Invalid cleanup schema')
    with admin.begin() as db:db.exec_driver_sql('DROP SCHEMA IF EXISTS "'+schema+'" CASCADE')
    admin.dispose()
