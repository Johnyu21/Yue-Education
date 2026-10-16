-- PostgreSQL 十九表建表设计稿；仅用于全新业务库，禁止覆盖现存数据。
-- 来源仅为本次三份 Markdown 和模块分工图；未在远端执行。
BEGIN;

CREATE TABLE sys_department (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code VARCHAR(40) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    parent_id BIGINT ,
    head_user_id BIGINT ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    create_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    update_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (parent_id) REFERENCES sys_department (id) ON DELETE RESTRICT,
    CHECK (parent_id IS NULL OR parent_id <> id)
);
COMMENT ON TABLE sys_department IS '部门树与唯一主管事实';
COMMENT ON COLUMN sys_department.id IS '主键';
COMMENT ON COLUMN sys_department.code IS '部门编码';
COMMENT ON COLUMN sys_department.name IS '名称';
COMMENT ON COLUMN sys_department.parent_id IS '上级部门';
COMMENT ON COLUMN sys_department.head_user_id IS '主管账号；账号建立后补外键';
COMMENT ON COLUMN sys_department.is_active IS '是否启用';
COMMENT ON COLUMN sys_department.version IS '并发版本，写入成功加一';
COMMENT ON COLUMN sys_department.create_time IS '创建时间';
COMMENT ON COLUMN sys_department.update_time IS '更新时间，触发器维护';

CREATE TABLE sys_user (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username VARCHAR(80) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    real_name VARCHAR(80) NOT NULL,
    user_type VARCHAR(20) NOT NULL CHECK (user_type IN ('STUDENT','EMPLOYEE')),
    employee_role VARCHAR(30) CHECK (employee_role IN ('NEWCOMER','ADVISOR','SENIOR_ADVISOR','ADMIN')),
    dept_id BIGINT ,
    contact_info VARCHAR(160) ,
    status VARCHAR(20) NOT NULL DEFAULT 'NORMAL' CHECK (status IN ('NORMAL','DISABLED')),
    can_handle_feedback BOOLEAN NOT NULL DEFAULT FALSE,
    psych_access_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    must_change_password BOOLEAN NOT NULL DEFAULT FALSE,
    temporary_password_expires_at TIMESTAMPTZ ,
    token_version INTEGER NOT NULL DEFAULT 0 CHECK (token_version >= 0),
    last_login_at TIMESTAMPTZ ,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    create_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    update_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (dept_id) REFERENCES sys_department (id) ON DELETE RESTRICT,
    CHECK ((user_type='STUDENT' AND employee_role IS NULL AND dept_id IS NULL AND NOT can_handle_feedback AND NOT psych_access_enabled) OR (user_type='EMPLOYEE' AND employee_role IS NOT NULL AND (dept_id IS NOT NULL OR employee_role='ADMIN')))
);
COMMENT ON TABLE sys_user IS '统一身份与独立岗位能力';
COMMENT ON COLUMN sys_user.id IS '主键';
COMMENT ON COLUMN sys_user.username IS '登录名；学生必须为规范手机号';
COMMENT ON COLUMN sys_user.password_hash IS '密码哈希';
COMMENT ON COLUMN sys_user.real_name IS '真实姓名';
COMMENT ON COLUMN sys_user.user_type IS 'STUDENT/EMPLOYEE';
COMMENT ON COLUMN sys_user.employee_role IS 'NEWCOMER/ADVISOR/SENIOR_ADVISOR/ADMIN，主管由部门关系派生';
COMMENT ON COLUMN sys_user.dept_id IS '员工部门，管理员可空';
COMMENT ON COLUMN sys_user.contact_info IS '员工展示联系方式；学生手机号以username为准';
COMMENT ON COLUMN sys_user.status IS 'NORMAL/DISABLED';
COMMENT ON COLUMN sys_user.can_handle_feedback IS '独立售后权限';
COMMENT ON COLUMN sys_user.psych_access_enabled IS '心理敏感数据授权';
COMMENT ON COLUMN sys_user.must_change_password IS '首次强制改密';
COMMENT ON COLUMN sys_user.temporary_password_expires_at IS '临时密码到期时间';
COMMENT ON COLUMN sys_user.token_version IS '改密/禁用/变权时加一';
COMMENT ON COLUMN sys_user.last_login_at IS '最后登录时间';
COMMENT ON COLUMN sys_user.version IS '并发版本，写入成功加一';
COMMENT ON COLUMN sys_user.create_time IS '创建时间';
COMMENT ON COLUMN sys_user.update_time IS '更新时间，触发器维护';

CREATE TABLE sys_class (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code VARCHAR(40) NOT NULL UNIQUE,
    name VARCHAR(80) NOT NULL,
    course_type VARCHAR(80) ,
    head_teacher_id BIGINT ,
    dept_id BIGINT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    create_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    update_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (head_teacher_id) REFERENCES sys_user (id) ON DELETE RESTRICT,
    FOREIGN KEY (dept_id) REFERENCES sys_department (id) ON DELETE RESTRICT,
    UNIQUE(id,dept_id)
);
COMMENT ON TABLE sys_class IS '新增：行政班与班主任，用于权限和审批路由';
COMMENT ON COLUMN sys_class.id IS '主键';
COMMENT ON COLUMN sys_class.code IS '班级编码';
COMMENT ON COLUMN sys_class.name IS '班级名称';
COMMENT ON COLUMN sys_class.course_type IS '课程类型';
COMMENT ON COLUMN sys_class.head_teacher_id IS '当前班主任';
COMMENT ON COLUMN sys_class.dept_id IS '所属部门';
COMMENT ON COLUMN sys_class.is_active IS '是否启用';
COMMENT ON COLUMN sys_class.version IS '并发版本，写入成功加一';
COMMENT ON COLUMN sys_class.create_time IS '创建时间';
COMMENT ON COLUMN sys_class.update_time IS '更新时间，触发器维护';

CREATE TABLE course_project (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code VARCHAR(40) NOT NULL UNIQUE,
    name VARCHAR(120) NOT NULL,
    country VARCHAR(80) ,
    education_level VARCHAR(80) ,
    description TEXT NOT NULL,
    admission_requirements TEXT ,
    admission_rules JSONB ,
    rule_version VARCHAR(40) ,
    rule_approved_at TIMESTAMPTZ ,
    rule_approved_by BIGINT ,
    faculty_summary TEXT ,
    duration_months INTEGER CHECK (duration_months IS NULL OR duration_months > 0),
    fee_amount NUMERIC(12,2) CHECK (fee_amount IS NULL OR fee_amount >= 0),
    fee_currency VARCHAR(3) ,
    default_dept_id BIGINT ,
    is_published BOOLEAN NOT NULL DEFAULT FALSE,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    create_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    update_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (default_dept_id) REFERENCES sys_department (id) ON DELETE RESTRICT,
    FOREIGN KEY (rule_approved_by) REFERENCES sys_user (id) ON DELETE RESTRICT,
    CHECK (admission_rules IS NULL OR jsonb_typeof(admission_rules)='object'),
    CHECK ((fee_amount IS NULL AND fee_currency IS NULL) OR (fee_amount IS NOT NULL AND fee_currency IS NOT NULL))
);
COMMENT ON TABLE course_project IS '项目展示与审核后的匹配条件';
COMMENT ON COLUMN course_project.id IS '主键';
COMMENT ON COLUMN course_project.code IS '项目编码';
COMMENT ON COLUMN course_project.name IS '名称';
COMMENT ON COLUMN course_project.country IS '国家地区';
COMMENT ON COLUMN course_project.education_level IS '学历展示';
COMMENT ON COLUMN course_project.description IS '介绍';
COMMENT ON COLUMN course_project.admission_requirements IS '申请条件文字';
COMMENT ON COLUMN course_project.admission_rules IS '经审核的结构化条件与可选评分规则';
COMMENT ON COLUMN course_project.rule_version IS '规则版本';
COMMENT ON COLUMN course_project.rule_approved_at IS '规则审核时间';
COMMENT ON COLUMN course_project.rule_approved_by IS '规则审核员工';
COMMENT ON COLUMN course_project.faculty_summary IS '师资说明';
COMMENT ON COLUMN course_project.duration_months IS '时长/月';
COMMENT ON COLUMN course_project.fee_amount IS '参考费用，不代表实收';
COMMENT ON COLUMN course_project.fee_currency IS 'ISO币种';
COMMENT ON COLUMN course_project.default_dept_id IS '新线索路由部门';
COMMENT ON COLUMN course_project.is_published IS '是否发布';
COMMENT ON COLUMN course_project.version IS '并发版本，写入成功加一';
COMMENT ON COLUMN course_project.create_time IS '创建时间';
COMMENT ON COLUMN course_project.update_time IS '更新时间，触发器维护';

CREATE TABLE crm_lead (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(80) NOT NULL,
    gender VARCHAR(20) ,
    mobile VARCHAR(32) NOT NULL UNIQUE,
    city VARCHAR(100) ,
    education VARCHAR(80) ,
    date_of_birth DATE ,
    intended_project_id BIGINT ,
    study_purpose VARCHAR(30) ,
    interest_level VARCHAR(30) ,
    source VARCHAR(20) NOT NULL CHECK (source IN ('WEBSITE','CHAT','EVENT','MANUAL')),
    profile_completeness VARCHAR(20) NOT NULL DEFAULT 'MINIMAL' CHECK (profile_completeness IN ('MINIMAL','COMPLETE')),
    dept_id BIGINT ,
    status VARCHAR(20) NOT NULL DEFAULT 'NEW' CHECK (status IN ('NEW','FOLLOWING','SIGNED','LOST')),
    owner_user_id BIGINT ,
    next_follow_up_at TIMESTAMPTZ ,
    resume_object_key VARCHAR(500) ,
    profile_summary JSONB ,
    assessment_report JSONB ,
    latest_score INTEGER CHECK (latest_score BETWEEN 0 AND 100),
    assessment_status VARCHAR(20) NOT NULL DEFAULT 'NONE' CHECK (assessment_status IN ('NONE','RUNNING','SUCCEEDED','FAILED')),
    assessment_request_id UUID ,
    assessment_started_at TIMESTAMPTZ ,
    assessment_error_code VARCHAR(60) ,
    assessed_at TIMESTAMPTZ ,
    signed_at TIMESTAMPTZ ,
    lost_at TIMESTAMPTZ ,
    loss_reason TEXT ,
    contract_ref VARCHAR(100) ,
    contract_amount NUMERIC(12,2) CHECK (contract_amount IS NULL OR contract_amount >= 0),
    contract_currency VARCHAR(3) ,
    request_key UUID NOT NULL UNIQUE,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    create_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    update_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (intended_project_id) REFERENCES course_project (id) ON DELETE RESTRICT,
    FOREIGN KEY (owner_user_id) REFERENCES sys_user (id) ON DELETE RESTRICT,
    FOREIGN KEY (dept_id) REFERENCES sys_department (id) ON DELETE RESTRICT,
    CHECK (status <> 'SIGNED' OR signed_at IS NOT NULL),
    CHECK (status <> 'LOST' OR (lost_at IS NOT NULL AND loss_reason IS NOT NULL)),
    CHECK ((contract_amount IS NULL AND contract_currency IS NULL) OR (contract_amount IS NOT NULL AND contract_currency IS NOT NULL))
);
COMMENT ON TABLE crm_lead IS '客户主档，三渠道统一获客与当前销售状态';
COMMENT ON COLUMN crm_lead.id IS '主键';
COMMENT ON COLUMN crm_lead.name IS '确认后的姓名';
COMMENT ON COLUMN crm_lead.gender IS '性别';
COMMENT ON COLUMN crm_lead.mobile IS '规范手机号，一人一档的建议规则';
COMMENT ON COLUMN crm_lead.city IS '城市';
COMMENT ON COLUMN crm_lead.education IS '学历';
COMMENT ON COLUMN crm_lead.date_of_birth IS '生日，可供规则匹配';
COMMENT ON COLUMN crm_lead.intended_project_id IS '当前意向项目';
COMMENT ON COLUMN crm_lead.study_purpose IS '留学目的';
COMMENT ON COLUMN crm_lead.interest_level IS '本人表达的意愿';
COMMENT ON COLUMN crm_lead.source IS '首次来源，后续来源写跟进';
COMMENT ON COLUMN crm_lead.profile_completeness IS 'MINIMAL/COMPLETE';
COMMENT ON COLUMN crm_lead.dept_id IS '归属部门，未路由时可空';
COMMENT ON COLUMN crm_lead.status IS 'NEW/FOLLOWING/SIGNED/LOST';
COMMENT ON COLUMN crm_lead.owner_user_id IS '负责顾问';
COMMENT ON COLUMN crm_lead.next_follow_up_at IS '最新有效跟进计划的查询缓存';
COMMENT ON COLUMN crm_lead.resume_object_key IS '私有文件标识';
COMMENT ON COLUMN crm_lead.profile_summary IS '核对后的基础事实与证据';
COMMENT ON COLUMN crm_lead.assessment_report IS '最近成功研判，旧请求不能覆盖新请求';
COMMENT ON COLUMN crm_lead.latest_score IS '已批准评分规则下的0~100分，否则NULL';
COMMENT ON COLUMN crm_lead.assessment_status IS 'NONE/RUNNING/SUCCEEDED/FAILED';
COMMENT ON COLUMN crm_lead.assessment_request_id IS '当前研判请求，防止旧任务覆盖';
COMMENT ON COLUMN crm_lead.assessment_started_at IS '当前研判启动时点，超时任务回收';
COMMENT ON COLUMN crm_lead.assessment_error_code IS '最近失败的脱敏错误码';
COMMENT ON COLUMN crm_lead.assessed_at IS '最近成功研判时间';
COMMENT ON COLUMN crm_lead.signed_at IS '签约转化时间';
COMMENT ON COLUMN crm_lead.lost_at IS '最近流失时间';
COMMENT ON COLUMN crm_lead.loss_reason IS '当前流失原因';
COMMENT ON COLUMN crm_lead.contract_ref IS '线下合同参考号，不存合同正文';
COMMENT ON COLUMN crm_lead.contract_amount IS '可选合同金额，非实收收入';
COMMENT ON COLUMN crm_lead.contract_currency IS '金额币种';
COMMENT ON COLUMN crm_lead.request_key IS '首次创建幂等键';
COMMENT ON COLUMN crm_lead.version IS '并发版本，写入成功加一';
COMMENT ON COLUMN crm_lead.create_time IS '创建时间';
COMMENT ON COLUMN crm_lead.update_time IS '更新时间，触发器维护';

CREATE TABLE crm_follow_up (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    lead_id BIGINT NOT NULL,
    actor_user_id BIGINT ,
    follow_up_type VARCHAR(30) NOT NULL,
    content TEXT NOT NULL,
    status_before VARCHAR(20) ,
    status_after VARCHAR(20) ,
    next_follow_up_at TIMESTAMPTZ ,
    details JSONB ,
    request_key UUID NOT NULL UNIQUE,
    create_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (lead_id) REFERENCES crm_lead (id) ON DELETE RESTRICT,
    FOREIGN KEY (actor_user_id) REFERENCES sys_user (id) ON DELETE RESTRICT,
    CHECK (follow_up_type IN ('ACQUIRED','CLAIMED','REASSIGNED','CONTACT','STATUS','ASSESSMENT','SIGNED','UPSELL_INTEREST'))
);
COMMENT ON TABLE crm_follow_up IS '不可删除的客户跟进/状态/分配事件';
COMMENT ON COLUMN crm_follow_up.id IS '主键';
COMMENT ON COLUMN crm_follow_up.lead_id IS '客户';
COMMENT ON COLUMN crm_follow_up.actor_user_id IS '员工；公开获客系统事件可空';
COMMENT ON COLUMN crm_follow_up.follow_up_type IS 'ACQUIRED/CLAIMED/REASSIGNED/CONTACT/STATUS/ASSESSMENT/SIGNED/UPSELL_INTEREST';
COMMENT ON COLUMN crm_follow_up.content IS '跟进说明，不放密码';
COMMENT ON COLUMN crm_follow_up.status_before IS '变前销售状态';
COMMENT ON COLUMN crm_follow_up.status_after IS '变后销售状态';
COMMENT ON COLUMN crm_follow_up.next_follow_up_at IS '本次设定的下一次计划';
COMMENT ON COLUMN crm_follow_up.details IS '项目意向/转派原因等类型化元数据';
COMMENT ON COLUMN crm_follow_up.request_key IS '追加操作幂等键';
COMMENT ON COLUMN crm_follow_up.create_time IS '创建时间';

CREATE TABLE employee_daily_report (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    employee_user_id BIGINT NOT NULL,
    dept_id BIGINT NOT NULL,
    report_date DATE NOT NULL,
    original_text TEXT NOT NULL,
    structured_content JSONB ,
    status VARCHAR(20) NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','SUBMITTED')),
    submitted_at TIMESTAMPTZ ,
    return_reason TEXT ,
    revision_history JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(revision_history)='array'),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    create_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    update_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (employee_user_id) REFERENCES sys_user (id) ON DELETE RESTRICT,
    FOREIGN KEY (dept_id) REFERENCES sys_department (id) ON DELETE RESTRICT,
    UNIQUE(employee_user_id,report_date),
    CHECK (status <> 'SUBMITTED' OR submitted_at IS NOT NULL)
);
COMMENT ON TABLE employee_daily_report IS '员工一日一报，保留原文及AI整理';
COMMENT ON COLUMN employee_daily_report.id IS '主键';
COMMENT ON COLUMN employee_daily_report.employee_user_id IS '员工';
COMMENT ON COLUMN employee_daily_report.dept_id IS '首次提交部门快照；退回/调岗不改归属';
COMMENT ON COLUMN employee_daily_report.report_date IS '业务日期';
COMMENT ON COLUMN employee_daily_report.original_text IS '确认后的原始文字/转写';
COMMENT ON COLUMN employee_daily_report.structured_content IS '进展/产出/风险/下一步';
COMMENT ON COLUMN employee_daily_report.status IS 'DRAFT/SUBMITTED';
COMMENT ON COLUMN employee_daily_report.submitted_at IS '最近提交时间';
COMMENT ON COLUMN employee_daily_report.return_reason IS '主管退回理由';
COMMENT ON COLUMN employee_daily_report.revision_history IS '有限业务修改轨迹，不存音频或对话';
COMMENT ON COLUMN employee_daily_report.version IS '并发版本，写入成功加一';
COMMENT ON COLUMN employee_daily_report.create_time IS '创建时间';
COMMENT ON COLUMN employee_daily_report.update_time IS '更新时间，触发器维护';

CREATE TABLE student_profile (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL UNIQUE,
    converted_lead_id BIGINT UNIQUE,
    advisor_user_id BIGINT ,
    dept_id BIGINT NOT NULL,
    class_id BIGINT ,
    gender VARCHAR(20) ,
    city VARCHAR(100) ,
    education VARCHAR(80) ,
    date_of_birth DATE ,
    enrollment_date DATE ,
    status VARCHAR(20) NOT NULL DEFAULT 'ENROLLED' CHECK (status IN ('ENROLLED','COMPLETED','PAUSED')),
    psych_consent_status VARCHAR(20) NOT NULL DEFAULT 'NOT_GIVEN' CHECK (psych_consent_status IN ('NOT_GIVEN','GRANTED','WITHDRAWN')),
    psych_consent_at TIMESTAMPTZ ,
    psych_consent_version VARCHAR(40) ,
    psych_withdrawn_at TIMESTAMPTZ ,
    is_demo BOOLEAN NOT NULL DEFAULT FALSE,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    create_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    update_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (user_id) REFERENCES sys_user (id) ON DELETE RESTRICT,
    FOREIGN KEY (converted_lead_id) REFERENCES crm_lead (id) ON DELETE RESTRICT,
    FOREIGN KEY (advisor_user_id) REFERENCES sys_user (id) ON DELETE RESTRICT,
    FOREIGN KEY (dept_id) REFERENCES sys_department (id) ON DELETE RESTRICT,
    CHECK (psych_consent_status <> 'GRANTED' OR (psych_consent_at IS NOT NULL AND psych_consent_version IS NOT NULL)),
    FOREIGN KEY (class_id,dept_id) REFERENCES sys_class (id,dept_id) ON DELETE RESTRICT
);
COMMENT ON TABLE student_profile IS '学生档案、主班关系及观测授权';
COMMENT ON COLUMN student_profile.id IS '主键';
COMMENT ON COLUMN student_profile.user_id IS '学生登录账号';
COMMENT ON COLUMN student_profile.converted_lead_id IS '来源客户一对一，可空';
COMMENT ON COLUMN student_profile.advisor_user_id IS '个人顾问';
COMMENT ON COLUMN student_profile.dept_id IS '学生业务部门';
COMMENT ON COLUMN student_profile.class_id IS '当前唯一行政班';
COMMENT ON COLUMN student_profile.gender IS '性别';
COMMENT ON COLUMN student_profile.city IS '城市';
COMMENT ON COLUMN student_profile.education IS '学历';
COMMENT ON COLUMN student_profile.date_of_birth IS '生日';
COMMENT ON COLUMN student_profile.enrollment_date IS '入学日期';
COMMENT ON COLUMN student_profile.status IS 'ENROLLED/COMPLETED/PAUSED';
COMMENT ON COLUMN student_profile.psych_consent_status IS 'NOT_GIVEN/GRANTED/WITHDRAWN';
COMMENT ON COLUMN student_profile.psych_consent_at IS '最近同意时间';
COMMENT ON COLUMN student_profile.psych_consent_version IS '同意文本版本';
COMMENT ON COLUMN student_profile.psych_withdrawn_at IS '撤回时间';
COMMENT ON COLUMN student_profile.is_demo IS '合成演示数据标志';
COMMENT ON COLUMN student_profile.version IS '并发版本，写入成功加一';
COMMENT ON COLUMN student_profile.create_time IS '创建时间';
COMMENT ON COLUMN student_profile.update_time IS '更新时间，触发器维护';

CREATE TABLE student_course_enrollment (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_profile_id BIGINT NOT NULL,
    course_project_id BIGINT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ENROLLED' CHECK (status IN ('ENROLLED','COMPLETED','WITHDRAWN')),
    enrolled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at TIMESTAMPTZ ,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    FOREIGN KEY (student_profile_id) REFERENCES student_profile (id) ON DELETE RESTRICT,
    FOREIGN KEY (course_project_id) REFERENCES course_project (id) ON DELETE RESTRICT,
    UNIQUE(student_profile_id,course_project_id),
    UNIQUE(id,student_profile_id),
    CHECK (ended_at IS NULL OR ended_at >= enrolled_at)
);
COMMENT ON TABLE student_course_enrollment IS '学生多项目关联';
COMMENT ON COLUMN student_course_enrollment.id IS '主键';
COMMENT ON COLUMN student_course_enrollment.student_profile_id IS '学生';
COMMENT ON COLUMN student_course_enrollment.course_project_id IS '项目';
COMMENT ON COLUMN student_course_enrollment.status IS 'ENROLLED/COMPLETED/WITHDRAWN';
COMMENT ON COLUMN student_course_enrollment.enrolled_at IS '加入时间';
COMMENT ON COLUMN student_course_enrollment.ended_at IS '结束时间';
COMMENT ON COLUMN student_course_enrollment.version IS '并发版本，写入成功加一';

CREATE TABLE student_admin_service (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_profile_id BIGINT NOT NULL,
    dept_id BIGINT NOT NULL,
    service_type VARCHAR(20) NOT NULL CHECK (service_type IN ('LEAVE','EXAM','INFO_CHANGE','OTHER')),
    title VARCHAR(160) NOT NULL,
    description TEXT NOT NULL,
    start_at TIMESTAMPTZ ,
    end_at TIMESTAMPTZ ,
    change_request JSONB ,
    submitted_by_user_id BIGINT NOT NULL,
    assignee_user_id BIGINT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','APPROVED','REJECTED','CANCELLED')),
    decision_note TEXT ,
    decided_at TIMESTAMPTZ ,
    handling_history JSONB NOT NULL DEFAULT '[]'::jsonb CHECK(jsonb_typeof(handling_history)='array'),
    request_key UUID NOT NULL UNIQUE,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    create_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    update_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (student_profile_id) REFERENCES student_profile (id) ON DELETE RESTRICT,
    FOREIGN KEY (dept_id) REFERENCES sys_department (id) ON DELETE RESTRICT,
    FOREIGN KEY (submitted_by_user_id) REFERENCES sys_user (id) ON DELETE RESTRICT,
    FOREIGN KEY (assignee_user_id) REFERENCES sys_user (id) ON DELETE RESTRICT,
    CHECK (service_type <> 'LEAVE' OR (start_at IS NOT NULL AND end_at IS NOT NULL AND end_at > start_at)),
    CHECK (end_at IS NULL OR start_at IS NULL OR end_at > start_at),
    CHECK (service_type <> 'INFO_CHANGE' OR (change_request IS NOT NULL AND jsonb_typeof(change_request)='object')),
    CHECK (status NOT IN ('APPROVED','REJECTED') OR decided_at IS NOT NULL)
);
COMMENT ON TABLE student_admin_service IS '请假/考务/资料修改申请与审批';
COMMENT ON COLUMN student_admin_service.id IS '主键';
COMMENT ON COLUMN student_admin_service.student_profile_id IS '学生';
COMMENT ON COLUMN student_admin_service.dept_id IS '提交时业务部门快照';
COMMENT ON COLUMN student_admin_service.service_type IS 'LEAVE/EXAM/INFO_CHANGE/OTHER';
COMMENT ON COLUMN student_admin_service.title IS '标题';
COMMENT ON COLUMN student_admin_service.description IS '理由';
COMMENT ON COLUMN student_admin_service.start_at IS '开始';
COMMENT ON COLUMN student_admin_service.end_at IS '结束';
COMMENT ON COLUMN student_admin_service.change_request IS 'INFO_CHANGE的旧值/新值/核验材料标识';
COMMENT ON COLUMN student_admin_service.submitted_by_user_id IS '实际提交学生';
COMMENT ON COLUMN student_admin_service.assignee_user_id IS '审批人';
COMMENT ON COLUMN student_admin_service.status IS 'PENDING/APPROVED/REJECTED/CANCELLED';
COMMENT ON COLUMN student_admin_service.decision_note IS '处理理由';
COMMENT ON COLUMN student_admin_service.decided_at IS '处理时间';
COMMENT ON COLUMN student_admin_service.handling_history IS '转派/取消/处理摘要，固定事件结构';
COMMENT ON COLUMN student_admin_service.request_key IS '提交幂等键';
COMMENT ON COLUMN student_admin_service.version IS '并发版本，写入成功加一';
COMMENT ON COLUMN student_admin_service.create_time IS '创建时间';
COMMENT ON COLUMN student_admin_service.update_time IS '更新时间，触发器维护';

CREATE TABLE student_academic_schedule (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_profile_id BIGINT NOT NULL,
    enrollment_id BIGINT ,
    schedule_type VARCHAR(20) NOT NULL CHECK (schedule_type IN ('EXAM','DEADLINE','CLASS','APPLICATION','OTHER')),
    title VARCHAR(160) NOT NULL,
    description TEXT ,
    start_at TIMESTAMPTZ NOT NULL,
    end_at TIMESTAMPTZ ,
    location VARCHAR(200) ,
    remind_at TIMESTAMPTZ ,
    reminder_revision INTEGER NOT NULL DEFAULT 1 CHECK (reminder_revision > 0),
    status VARCHAR(20) NOT NULL DEFAULT 'SCHEDULED' CHECK (status IN ('SCHEDULED','COMPLETED','CANCELLED')),
    data_source VARCHAR(20) NOT NULL DEFAULT 'TEST' CHECK (data_source IN ('TEST','MANUAL')),
    created_by_user_id BIGINT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    create_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    update_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (student_profile_id) REFERENCES student_profile (id) ON DELETE RESTRICT,
    FOREIGN KEY (enrollment_id,student_profile_id) REFERENCES student_course_enrollment (id,student_profile_id) ON DELETE RESTRICT,
    FOREIGN KEY (created_by_user_id) REFERENCES sys_user (id) ON DELETE RESTRICT,
    UNIQUE(id,student_profile_id),
    CHECK (end_at IS NULL OR end_at >= start_at),
    CHECK (remind_at IS NULL OR remind_at <= start_at)
);
COMMENT ON TABLE student_academic_schedule IS '合成教务节点与学生单次提醒';
COMMENT ON COLUMN student_academic_schedule.id IS '主键';
COMMENT ON COLUMN student_academic_schedule.student_profile_id IS '学生';
COMMENT ON COLUMN student_academic_schedule.enrollment_id IS '相关项目关联';
COMMENT ON COLUMN student_academic_schedule.schedule_type IS 'EXAM/DEADLINE/CLASS/APPLICATION/OTHER';
COMMENT ON COLUMN student_academic_schedule.title IS '标题';
COMMENT ON COLUMN student_academic_schedule.description IS '说明';
COMMENT ON COLUMN student_academic_schedule.start_at IS '考试开始/DDL/申请开始';
COMMENT ON COLUMN student_academic_schedule.end_at IS '结束/申请截止';
COMMENT ON COLUMN student_academic_schedule.location IS '地点';
COMMENT ON COLUMN student_academic_schedule.remind_at IS '学生设置的提醒时间';
COMMENT ON COLUMN student_academic_schedule.reminder_revision IS '提醒时间变更时递增';
COMMENT ON COLUMN student_academic_schedule.status IS 'SCHEDULED/COMPLETED/CANCELLED';
COMMENT ON COLUMN student_academic_schedule.data_source IS 'TEST/MANUAL，界面标识';
COMMENT ON COLUMN student_academic_schedule.created_by_user_id IS '登记员工';
COMMENT ON COLUMN student_academic_schedule.version IS '并发版本，写入成功加一';
COMMENT ON COLUMN student_academic_schedule.create_time IS '创建时间';
COMMENT ON COLUMN student_academic_schedule.update_time IS '更新时间，触发器维护';

CREATE TABLE student_score (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_profile_id BIGINT NOT NULL,
    enrollment_id BIGINT ,
    schedule_id BIGINT ,
    subject VARCHAR(120) NOT NULL,
    score_type VARCHAR(20) NOT NULL CHECK (score_type IN ('NUMERIC','GRADE','PASS_FAIL')),
    score_text VARCHAR(80) NOT NULL,
    score_numeric NUMERIC(8,2) ,
    max_score NUMERIC(8,2) ,
    graded_at DATE ,
    recorded_by_user_id BIGINT NOT NULL,
    remark TEXT ,
    data_source VARCHAR(20) NOT NULL DEFAULT 'TEST' CHECK (data_source='TEST'),
    create_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (student_profile_id) REFERENCES student_profile (id) ON DELETE RESTRICT,
    FOREIGN KEY (enrollment_id,student_profile_id) REFERENCES student_course_enrollment (id,student_profile_id) ON DELETE RESTRICT,
    FOREIGN KEY (schedule_id,student_profile_id) REFERENCES student_academic_schedule (id,student_profile_id) ON DELETE RESTRICT,
    FOREIGN KEY (recorded_by_user_id) REFERENCES sys_user (id) ON DELETE RESTRICT,
    CHECK ((score_type='NUMERIC' AND score_numeric IS NOT NULL AND max_score IS NOT NULL AND max_score > 0 AND score_numeric >= 0 AND score_numeric <= max_score) OR (score_type IN ('GRADE','PASS_FAIL') AND score_numeric IS NULL AND max_score IS NULL))
);
COMMENT ON TABLE student_score IS '合成成绩只读，不提供业务写接口';
COMMENT ON COLUMN student_score.id IS '主键';
COMMENT ON COLUMN student_score.student_profile_id IS '学生';
COMMENT ON COLUMN student_score.enrollment_id IS '关联项目';
COMMENT ON COLUMN student_score.schedule_id IS '考试节点';
COMMENT ON COLUMN student_score.subject IS '科目';
COMMENT ON COLUMN student_score.score_type IS 'NUMERIC/GRADE/PASS_FAIL';
COMMENT ON COLUMN student_score.score_text IS '原始显示成绩';
COMMENT ON COLUMN student_score.score_numeric IS '数字成绩';
COMMENT ON COLUMN student_score.max_score IS '数字满分';
COMMENT ON COLUMN student_score.graded_at IS '出分日';
COMMENT ON COLUMN student_score.recorded_by_user_id IS '种子生成对应员工';
COMMENT ON COLUMN student_score.remark IS '备注';
COMMENT ON COLUMN student_score.data_source IS '本轮固定TEST';
COMMENT ON COLUMN student_score.create_time IS '创建时间';

CREATE TABLE student_feedback_ticket (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_profile_id BIGINT NOT NULL,
    dept_id BIGINT NOT NULL,
    assignee_user_id BIGINT ,
    category VARCHAR(20) NOT NULL CHECK (category IN ('COMPLAINT','SUGGESTION','CONSULTATION')),
    subject VARCHAR(160) NOT NULL,
    teacher_name VARCHAR(80) NOT NULL,
    project_category VARCHAR(80) NOT NULL,
    course_project_id BIGINT ,
    content TEXT NOT NULL,
    priority VARCHAR(20) NOT NULL CHECK (priority IN ('HIGH','NORMAL')),
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','PROCESSING','RESOLVED','CLOSED')),
    resolution TEXT ,
    first_response_at TIMESTAMPTZ ,
    first_resolved_at TIMESTAMPTZ ,
    resolved_at TIMESTAMPTZ ,
    closed_at TIMESTAMPTZ ,
    due_at TIMESTAMPTZ ,
    is_notified BOOLEAN NOT NULL DEFAULT FALSE,
    reopened_count INTEGER NOT NULL DEFAULT 0 CHECK (reopened_count >= 0),
    satisfaction_rating SMALLINT CHECK(satisfaction_rating BETWEEN 1 AND 5),
    satisfaction_comment TEXT ,
    rated_at TIMESTAMPTZ ,
    handling_history JSONB NOT NULL DEFAULT '[]'::jsonb CHECK(jsonb_typeof(handling_history)='array'),
    request_key UUID NOT NULL UNIQUE,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    create_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    update_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (student_profile_id) REFERENCES student_profile (id) ON DELETE RESTRICT,
    FOREIGN KEY (dept_id) REFERENCES sys_department (id) ON DELETE RESTRICT,
    FOREIGN KEY (assignee_user_id) REFERENCES sys_user (id) ON DELETE RESTRICT,
    FOREIGN KEY (course_project_id) REFERENCES course_project (id) ON DELETE RESTRICT,
    CHECK ((category='COMPLAINT' AND priority='HIGH') OR (category IN ('SUGGESTION','CONSULTATION') AND priority='NORMAL')),
    CHECK (status NOT IN ('RESOLVED','CLOSED') OR (resolved_at IS NOT NULL AND resolution IS NOT NULL AND is_notified)),
    CHECK (status <> 'CLOSED' OR closed_at IS NOT NULL)
);
COMMENT ON TABLE student_feedback_ticket IS '保密售后及完整处理/满意度闭环';
COMMENT ON COLUMN student_feedback_ticket.id IS '主键';
COMMENT ON COLUMN student_feedback_ticket.student_profile_id IS '提交学生';
COMMENT ON COLUMN student_feedback_ticket.dept_id IS '受理部门快照';
COMMENT ON COLUMN student_feedback_ticket.assignee_user_id IS '被授权的售后处理人';
COMMENT ON COLUMN student_feedback_ticket.category IS 'COMPLAINT/SUGGESTION/CONSULTATION';
COMMENT ON COLUMN student_feedback_ticket.subject IS '标题；修正原文断开的subje ct';
COMMENT ON COLUMN student_feedback_ticket.teacher_name IS '涉事老师文字；未知可明确填写';
COMMENT ON COLUMN student_feedback_ticket.project_category IS '涉及业务/项目类别';
COMMENT ON COLUMN student_feedback_ticket.course_project_id IS '可选具体项目';
COMMENT ON COLUMN student_feedback_ticket.content IS '内容';
COMMENT ON COLUMN student_feedback_ticket.priority IS 'HIGH/NORMAL，不在学生DTO返回';
COMMENT ON COLUMN student_feedback_ticket.status IS 'PENDING/PROCESSING/RESOLVED/CLOSED';
COMMENT ON COLUMN student_feedback_ticket.resolution IS '最近解决结果';
COMMENT ON COLUMN student_feedback_ticket.first_response_at IS '首次响应';
COMMENT ON COLUMN student_feedback_ticket.first_resolved_at IS '首次解决，周报统计';
COMMENT ON COLUMN student_feedback_ticket.resolved_at IS '最近处理完毕时间';
COMMENT ON COLUMN student_feedback_ticket.closed_at IS '学生确认关闭时间';
COMMENT ON COLUMN student_feedback_ticket.due_at IS '有明确SLA后才填写，否则空';
COMMENT ON COLUMN student_feedback_ticket.is_notified IS '当前解决轮的站内结果通知已落库';
COMMENT ON COLUMN student_feedback_ticket.reopened_count IS '学生退回次数';
COMMENT ON COLUMN student_feedback_ticket.satisfaction_rating IS '学生1~5评分';
COMMENT ON COLUMN student_feedback_ticket.satisfaction_comment IS '学生评价';
COMMENT ON COLUMN student_feedback_ticket.rated_at IS '评价时间';
COMMENT ON COLUMN student_feedback_ticket.handling_history IS '固定结构处理事件，不存完整聊天';
COMMENT ON COLUMN student_feedback_ticket.request_key IS '学生提交幂等键';
COMMENT ON COLUMN student_feedback_ticket.version IS '并发版本，写入成功加一';
COMMENT ON COLUMN student_feedback_ticket.create_time IS '创建时间';
COMMENT ON COLUMN student_feedback_ticket.update_time IS '更新时间，触发器维护';

CREATE TABLE student_psych_profile (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_profile_id BIGINT NOT NULL,
    version_no INTEGER NOT NULL CHECK(version_no>0),
    assessment_date DATE NOT NULL,
    business_timezone VARCHAR(64) NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    source_event_key UUID NOT NULL UNIQUE,
    assessment_source VARCHAR(20) NOT NULL CHECK(assessment_source IN ('DIFY','RULE','MANUAL')),
    emotion_state VARCHAR(20) NOT NULL CHECK(emotion_state IN ('HEALTHY','NEGATIVE','VERY_NEGATIVE','UNKNOWN')),
    assessment_data JSONB NOT NULL CHECK(jsonb_typeof(assessment_data)='object'),
    summary TEXT ,
    consent_at TIMESTAMPTZ NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'AUTO_RECORDED' CHECK(status IN ('AUTO_RECORDED','VERIFIED','CORRECTED')),
    is_valid BOOLEAN NOT NULL DEFAULT TRUE,
    invalidated_reason TEXT ,
    replaces_profile_id BIGINT ,
    created_by_user_id BIGINT ,
    verified_by_user_id BIGINT ,
    verified_at TIMESTAMPTZ ,
    create_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (student_profile_id) REFERENCES student_profile (id) ON DELETE RESTRICT,
    FOREIGN KEY (created_by_user_id) REFERENCES sys_user (id) ON DELETE RESTRICT,
    FOREIGN KEY (verified_by_user_id) REFERENCES sys_user (id) ON DELETE RESTRICT,
    UNIQUE(student_profile_id,version_no),
    UNIQUE(id,student_profile_id),
    FOREIGN KEY (replaces_profile_id,student_profile_id) REFERENCES student_psych_profile (id,student_profile_id) ON DELETE RESTRICT,
    CHECK (emotion_state <> 'UNKNOWN' OR NOT is_valid)
);
COMMENT ON TABLE student_psych_profile IS '逐条版本化情绪观测；按日取最后有效版本';
COMMENT ON COLUMN student_psych_profile.id IS '主键';
COMMENT ON COLUMN student_psych_profile.student_profile_id IS '学生';
COMMENT ON COLUMN student_psych_profile.version_no IS '该学生递增版本';
COMMENT ON COLUMN student_psych_profile.assessment_date IS '业务时区自然日';
COMMENT ON COLUMN student_psych_profile.business_timezone IS '当时业务时区';
COMMENT ON COLUMN student_psych_profile.observed_at IS '消息收到/人工观测时间，防乱序';
COMMENT ON COLUMN student_psych_profile.source_event_key IS '源消息/表单事件幂等键';
COMMENT ON COLUMN student_psych_profile.assessment_source IS 'DIFY/RULE/MANUAL';
COMMENT ON COLUMN student_psych_profile.emotion_state IS 'HEALTHY/NEGATIVE/VERY_NEGATIVE/UNKNOWN';
COMMENT ON COLUMN student_psych_profile.assessment_data IS '置信度/规则版本/最小证据摘要，不存完整对话';
COMMENT ON COLUMN student_psych_profile.summary IS '受限摘要';
COMMENT ON COLUMN student_psych_profile.consent_at IS '当时有效的授权时间';
COMMENT ON COLUMN student_psych_profile.status IS 'AUTO_RECORDED/VERIFIED/CORRECTED';
COMMENT ON COLUMN student_psych_profile.is_valid IS '是否纳入日状态';
COMMENT ON COLUMN student_psych_profile.invalidated_reason IS '主管修正理由';
COMMENT ON COLUMN student_psych_profile.replaces_profile_id IS '被人工修正的同学生版本';
COMMENT ON COLUMN student_psych_profile.created_by_user_id IS '触发者；系统产生可空';
COMMENT ON COLUMN student_psych_profile.verified_by_user_id IS '人工核验主管';
COMMENT ON COLUMN student_psych_profile.verified_at IS '人工核验时间';
COMMENT ON COLUMN student_psych_profile.create_time IS '创建时间';

CREATE TABLE student_psych_alert (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_profile_id BIGINT NOT NULL,
    psych_profile_id BIGINT NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK(severity IN ('HIGH','MEDIUM','LOW')),
    signal_code VARCHAR(40) NOT NULL,
    trigger_summary TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING_REVIEW' CHECK(status IN ('PENDING_REVIEW','CONFIRMED','HANDLING','DISMISSED','CLOSED')),
    follow_up_user_id BIGINT ,
    created_by_user_id BIGINT ,
    reviewed_by_user_id BIGINT ,
    reviewed_at TIMESTAMPTZ ,
    action_note TEXT ,
    handling_history JSONB NOT NULL DEFAULT '[]'::jsonb CHECK(jsonb_typeof(handling_history)='array'),
    trigger_key VARCHAR(160) NOT NULL UNIQUE,
    repeat_count INTEGER NOT NULL DEFAULT 1 CHECK(repeat_count>0),
    last_triggered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at TIMESTAMPTZ ,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    create_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    update_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (student_profile_id) REFERENCES student_profile (id) ON DELETE RESTRICT,
    FOREIGN KEY (psych_profile_id,student_profile_id) REFERENCES student_psych_profile (id,student_profile_id) ON DELETE RESTRICT,
    FOREIGN KEY (follow_up_user_id) REFERENCES sys_user (id) ON DELETE RESTRICT,
    FOREIGN KEY (created_by_user_id) REFERENCES sys_user (id) ON DELETE RESTRICT,
    FOREIGN KEY (reviewed_by_user_id) REFERENCES sys_user (id) ON DELETE RESTRICT,
    CHECK (status NOT IN ('DISMISSED','CLOSED') OR (closed_at IS NOT NULL AND action_note IS NOT NULL))
);
COMMENT ON TABLE student_psych_alert IS '需人工复核的关怀事件及跟进';
COMMENT ON COLUMN student_psych_alert.id IS '主键';
COMMENT ON COLUMN student_psych_alert.student_profile_id IS '学生，供活动事件唯一约束';
COMMENT ON COLUMN student_psych_alert.psych_profile_id IS '最近触发的同学生观测';
COMMENT ON COLUMN student_psych_alert.severity IS 'HIGH/MEDIUM/LOW';
COMMENT ON COLUMN student_psych_alert.signal_code IS '最近规则编码';
COMMENT ON COLUMN student_psych_alert.trigger_summary IS '规则与事实摘要，不传播敏感原话';
COMMENT ON COLUMN student_psych_alert.status IS 'PENDING_REVIEW/CONFIRMED/HANDLING/DISMISSED/CLOSED';
COMMENT ON COLUMN student_psych_alert.follow_up_user_id IS '负责跟进人，无配置时进入受限池';
COMMENT ON COLUMN student_psych_alert.created_by_user_id IS '系统触发可空';
COMMENT ON COLUMN student_psych_alert.reviewed_by_user_id IS '授权主管复核';
COMMENT ON COLUMN student_psych_alert.reviewed_at IS '复核时间';
COMMENT ON COLUMN student_psych_alert.action_note IS '最近处置说明';
COMMENT ON COLUMN student_psych_alert.handling_history IS '处置事件摘要';
COMMENT ON COLUMN student_psych_alert.trigger_key IS '首次触发去重键';
COMMENT ON COLUMN student_psych_alert.repeat_count IS '本事件触发次数';
COMMENT ON COLUMN student_psych_alert.last_triggered_at IS '最近触发';
COMMENT ON COLUMN student_psych_alert.closed_at IS '终止时间';
COMMENT ON COLUMN student_psych_alert.version IS '并发版本，写入成功加一';
COMMENT ON COLUMN student_psych_alert.create_time IS '创建时间';
COMMENT ON COLUMN student_psych_alert.update_time IS '更新时间，触发器维护';

CREATE TABLE student_application_progress (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    case_no UUID NOT NULL,
    student_profile_id BIGINT NOT NULL,
    enrollment_id BIGINT ,
    sequence_no INTEGER NOT NULL CHECK(sequence_no>0),
    previous_id BIGINT UNIQUE,
    item_type VARCHAR(20) NOT NULL CHECK(item_type IN ('DOCUMENT','SCHOOL','VISA')),
    title VARCHAR(160) NOT NULL,
    target_country VARCHAR(80) ,
    target_school VARCHAR(160) ,
    target_program VARCHAR(160) ,
    stage VARCHAR(20) NOT NULL CHECK(stage IN ('SUBMITTED','PROCESSING','COMPLETED','NOTIFIED')),
    event_kind VARCHAR(20) NOT NULL DEFAULT 'STAGE' CHECK(event_kind IN ('STAGE','DETAIL','ASSIGNMENT')),
    detail TEXT ,
    assignee_user_id BIGINT NOT NULL,
    recorded_by_user_id BIGINT NOT NULL,
    data_source VARCHAR(20) NOT NULL DEFAULT 'MANUAL' CHECK(data_source IN ('TEST','MANUAL')),
    occurred_at TIMESTAMPTZ NOT NULL,
    request_key UUID NOT NULL UNIQUE,
    create_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (student_profile_id) REFERENCES student_profile (id) ON DELETE RESTRICT,
    FOREIGN KEY (enrollment_id,student_profile_id) REFERENCES student_course_enrollment (id,student_profile_id) ON DELETE RESTRICT,
    FOREIGN KEY (assignee_user_id) REFERENCES sys_user (id) ON DELETE RESTRICT,
    FOREIGN KEY (recorded_by_user_id) REFERENCES sys_user (id) ON DELETE RESTRICT,
    UNIQUE(case_no,sequence_no),
    UNIQUE(id,case_no,student_profile_id),
    FOREIGN KEY (previous_id,case_no,student_profile_id) REFERENCES student_application_progress (id,case_no,student_profile_id) ON DELETE RESTRICT,
    CHECK ((sequence_no=1 AND previous_id IS NULL) OR (sequence_no>1 AND previous_id IS NOT NULL))
);
COMMENT ON TABLE student_application_progress IS '新增：同表分组保存独立事项及追加进度历史';
COMMENT ON COLUMN student_application_progress.id IS '主键';
COMMENT ON COLUMN student_application_progress.case_no IS '同一事项固定UUID，首次生成';
COMMENT ON COLUMN student_application_progress.student_profile_id IS '所属学生';
COMMENT ON COLUMN student_application_progress.enrollment_id IS '可选相关项目关联';
COMMENT ON COLUMN student_application_progress.sequence_no IS '事项内递增事件序号';
COMMENT ON COLUMN student_application_progress.previous_id IS '同事项上一事件，防分叉';
COMMENT ON COLUMN student_application_progress.item_type IS 'DOCUMENT/SCHOOL/VISA';
COMMENT ON COLUMN student_application_progress.title IS '事项名，每事件保存快照';
COMMENT ON COLUMN student_application_progress.target_country IS '国家快照';
COMMENT ON COLUMN student_application_progress.target_school IS '院校快照';
COMMENT ON COLUMN student_application_progress.target_program IS '专业快照';
COMMENT ON COLUMN student_application_progress.stage IS 'SUBMITTED/PROCESSING/COMPLETED/NOTIFIED';
COMMENT ON COLUMN student_application_progress.event_kind IS 'STAGE/DETAIL/ASSIGNMENT';
COMMENT ON COLUMN student_application_progress.detail IS '补料/结果/解释';
COMMENT ON COLUMN student_application_progress.assignee_user_id IS '跟进员工';
COMMENT ON COLUMN student_application_progress.recorded_by_user_id IS '实际录入员工';
COMMENT ON COLUMN student_application_progress.data_source IS 'TEST/MANUAL';
COMMENT ON COLUMN student_application_progress.occurred_at IS '内部登记的业务发生时点';
COMMENT ON COLUMN student_application_progress.request_key IS '本事件幂等键';
COMMENT ON COLUMN student_application_progress.create_time IS '创建时间';

CREATE TABLE event_lecture (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title VARCHAR(160) NOT NULL,
    course_project_id BIGINT ,
    host_department_id BIGINT ,
    organizer_user_id BIGINT NOT NULL,
    description TEXT NOT NULL,
    start_at TIMESTAMPTZ NOT NULL,
    end_at TIMESTAMPTZ NOT NULL,
    signup_deadline TIMESTAMPTZ NOT NULL,
    capacity INTEGER NOT NULL CHECK(capacity>0),
    location VARCHAR(200) ,
    status VARCHAR(20) NOT NULL DEFAULT 'DRAFT' CHECK(status IN ('DRAFT','OPEN','ENDED','CANCELLED')),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    create_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    update_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (course_project_id) REFERENCES course_project (id) ON DELETE RESTRICT,
    FOREIGN KEY (host_department_id) REFERENCES sys_department (id) ON DELETE RESTRICT,
    FOREIGN KEY (organizer_user_id) REFERENCES sys_user (id) ON DELETE RESTRICT,
    CHECK(end_at>start_at),
    CHECK(signup_deadline<=start_at)
);
COMMENT ON TABLE event_lecture IS '活动/讲座发布与名额';
COMMENT ON COLUMN event_lecture.id IS '主键';
COMMENT ON COLUMN event_lecture.title IS '标题';
COMMENT ON COLUMN event_lecture.course_project_id IS '关联项目';
COMMENT ON COLUMN event_lecture.host_department_id IS '主办部门';
COMMENT ON COLUMN event_lecture.organizer_user_id IS '组织员工';
COMMENT ON COLUMN event_lecture.description IS '介绍';
COMMENT ON COLUMN event_lecture.start_at IS '开始';
COMMENT ON COLUMN event_lecture.end_at IS '结束';
COMMENT ON COLUMN event_lecture.signup_deadline IS '报名截止';
COMMENT ON COLUMN event_lecture.capacity IS '名额';
COMMENT ON COLUMN event_lecture.location IS '地点';
COMMENT ON COLUMN event_lecture.status IS 'DRAFT/OPEN/ENDED/CANCELLED';
COMMENT ON COLUMN event_lecture.version IS '并发版本，写入成功加一';
COMMENT ON COLUMN event_lecture.create_time IS '创建时间';
COMMENT ON COLUMN event_lecture.update_time IS '更新时间，触发器维护';

CREATE TABLE event_registration (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_id BIGINT NOT NULL,
    student_profile_id BIGINT ,
    lead_id BIGINT ,
    registrant_name VARCHAR(80) NOT NULL,
    mobile VARCHAR(32) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'REGISTERED' CHECK(status IN ('REGISTERED','CANCELLED','CHECKED_IN')),
    cancel_token_hash VARCHAR(255) ,
    request_key UUID NOT NULL UNIQUE,
    registered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    canceled_at TIMESTAMPTZ ,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    FOREIGN KEY (event_id) REFERENCES event_lecture (id) ON DELETE RESTRICT,
    FOREIGN KEY (student_profile_id) REFERENCES student_profile (id) ON DELETE RESTRICT,
    FOREIGN KEY (lead_id) REFERENCES crm_lead (id) ON DELETE RESTRICT,
    UNIQUE(event_id,mobile),
    CHECK(num_nonnulls(student_profile_id,lead_id)=1),
    CHECK(lead_id IS NULL OR cancel_token_hash IS NOT NULL),
    CHECK(status<>'CANCELLED' OR canceled_at IS NOT NULL)
);
COMMENT ON TABLE event_registration IS '活动报名，学生或访客其一';
COMMENT ON COLUMN event_registration.id IS '主键';
COMMENT ON COLUMN event_registration.event_id IS '活动';
COMMENT ON COLUMN event_registration.student_profile_id IS '学生';
COMMENT ON COLUMN event_registration.lead_id IS '访客客户';
COMMENT ON COLUMN event_registration.registrant_name IS '姓名快照';
COMMENT ON COLUMN event_registration.mobile IS '规范手机号快照';
COMMENT ON COLUMN event_registration.status IS 'REGISTERED/CANCELLED/CHECKED_IN';
COMMENT ON COLUMN event_registration.cancel_token_hash IS '访客取消凭据哈希，不存原token';
COMMENT ON COLUMN event_registration.request_key IS '创建幂等键';
COMMENT ON COLUMN event_registration.registered_at IS '报名时间';
COMMENT ON COLUMN event_registration.canceled_at IS '取消时间';
COMMENT ON COLUMN event_registration.version IS '并发版本，写入成功加一';

CREATE TABLE notification (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    recipient_user_id BIGINT NOT NULL,
    category VARCHAR(40) NOT NULL,
    title VARCHAR(160) NOT NULL,
    content VARCHAR(1000) NOT NULL,
    related_type VARCHAR(40) ,
    related_id BIGINT ,
    business_event_key VARCHAR(180) NOT NULL,
    read_at TIMESTAMPTZ ,
    create_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (recipient_user_id) REFERENCES sys_user (id) ON DELETE RESTRICT,
    UNIQUE(recipient_user_id,business_event_key),
    CHECK((related_type IS NULL)=(related_id IS NULL))
);
COMMENT ON TABLE notification IS '站内通知与提醒去重';
COMMENT ON COLUMN notification.id IS '主键';
COMMENT ON COLUMN notification.recipient_user_id IS '接收用户';
COMMENT ON COLUMN notification.category IS '通知类型字典';
COMMENT ON COLUMN notification.title IS '无敏感正文的标题';
COMMENT ON COLUMN notification.content IS '简要提示';
COMMENT ON COLUMN notification.related_type IS 'LEAD/SERVICE/TICKET/PSYCH_ALERT/APPLICATION_CASE/SCHEDULE/DAILY_REPORT/ACCOUNT';
COMMENT ON COLUMN notification.related_id IS '业务行主键，申请事项使用根事件id';
COMMENT ON COLUMN notification.business_event_key IS '业务事件+版本，接收者内唯一';
COMMENT ON COLUMN notification.read_at IS '阅读时间';
COMMENT ON COLUMN notification.create_time IS '创建时间';

ALTER TABLE sys_department ADD CONSTRAINT fk_department_head FOREIGN KEY(head_user_id) REFERENCES sys_user(id) ON DELETE RESTRICT;

CREATE INDEX ix_department_parent ON sys_department(parent_id);
CREATE INDEX ix_class_dept_teacher ON sys_class(dept_id,head_teacher_id);
CREATE INDEX ix_lead_dept_owner_status ON crm_lead(dept_id,owner_user_id,status);
CREATE INDEX ix_lead_score ON crm_lead(latest_score DESC NULLS LAST);
CREATE INDEX ix_lead_next_followup ON crm_lead(next_follow_up_at) WHERE status IN ('NEW','FOLLOWING');
CREATE INDEX ix_followup_lead_time ON crm_follow_up(lead_id,create_time DESC,id DESC);
CREATE INDEX ix_daily_dept_date ON employee_daily_report(dept_id,report_date);
CREATE INDEX ix_student_dept_class_advisor ON student_profile(dept_id,class_id,advisor_user_id);
CREATE INDEX ix_service_student_status ON student_admin_service(student_profile_id,status);
CREATE INDEX ix_service_assignee_status ON student_admin_service(assignee_user_id,status);
CREATE INDEX ix_schedule_student_time ON student_academic_schedule(student_profile_id,start_at);
CREATE INDEX ix_schedule_reminder ON student_academic_schedule(remind_at) WHERE status='SCHEDULED';
CREATE INDEX ix_score_student_subject ON student_score(student_profile_id,subject);
CREATE INDEX ix_ticket_scope_status ON student_feedback_ticket(dept_id,assignee_user_id,status);
CREATE INDEX ix_ticket_student ON student_feedback_ticket(student_profile_id,create_time DESC);
CREATE INDEX ix_psych_daily_latest ON student_psych_profile(student_profile_id,assessment_date,observed_at DESC,version_no DESC) WHERE is_valid;
CREATE UNIQUE INDEX uq_psych_open_student ON student_psych_alert(student_profile_id) WHERE status IN ('PENDING_REVIEW','CONFIRMED','HANDLING');
CREATE INDEX ix_progress_student_case ON student_application_progress(student_profile_id,case_no,sequence_no DESC);
CREATE INDEX ix_event_status_start ON event_lecture(status,start_at);
CREATE INDEX ix_registration_student ON event_registration(student_profile_id);
CREATE INDEX ix_notification_recipient_read ON notification(recipient_user_id,read_at,create_time DESC);

CREATE FUNCTION yue_set_update_time() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.update_time = now();
    RETURN NEW;
END;
$$;
CREATE TRIGGER trg_sys_department_updated BEFORE UPDATE ON sys_department FOR EACH ROW EXECUTE FUNCTION yue_set_update_time();
CREATE TRIGGER trg_sys_user_updated BEFORE UPDATE ON sys_user FOR EACH ROW EXECUTE FUNCTION yue_set_update_time();
CREATE TRIGGER trg_sys_class_updated BEFORE UPDATE ON sys_class FOR EACH ROW EXECUTE FUNCTION yue_set_update_time();
CREATE TRIGGER trg_course_project_updated BEFORE UPDATE ON course_project FOR EACH ROW EXECUTE FUNCTION yue_set_update_time();
CREATE TRIGGER trg_crm_lead_updated BEFORE UPDATE ON crm_lead FOR EACH ROW EXECUTE FUNCTION yue_set_update_time();
CREATE TRIGGER trg_employee_daily_report_updated BEFORE UPDATE ON employee_daily_report FOR EACH ROW EXECUTE FUNCTION yue_set_update_time();
CREATE TRIGGER trg_student_profile_updated BEFORE UPDATE ON student_profile FOR EACH ROW EXECUTE FUNCTION yue_set_update_time();
CREATE TRIGGER trg_student_admin_service_updated BEFORE UPDATE ON student_admin_service FOR EACH ROW EXECUTE FUNCTION yue_set_update_time();
CREATE TRIGGER trg_student_academic_schedule_updated BEFORE UPDATE ON student_academic_schedule FOR EACH ROW EXECUTE FUNCTION yue_set_update_time();
CREATE TRIGGER trg_student_feedback_ticket_updated BEFORE UPDATE ON student_feedback_ticket FOR EACH ROW EXECUTE FUNCTION yue_set_update_time();
CREATE TRIGGER trg_student_psych_alert_updated BEFORE UPDATE ON student_psych_alert FOR EACH ROW EXECUTE FUNCTION yue_set_update_time();
CREATE TRIGGER trg_event_lecture_updated BEFORE UPDATE ON event_lecture FOR EACH ROW EXECUTE FUNCTION yue_set_update_time();

COMMIT;
