from app.core.errors import ForbiddenError,NotFoundError
REPORT_NAMES={'CUSTOMER_OPERATION':'客户经营报告','DAILY_DAY':'日报日汇总','DAILY_WEEK':'日报周汇总','PSYCH_WEEK':'心理周报','COMPLAINT_WEEK':'投诉周报','MANAGER_WEEK':'部门主管周报'}

def employee(user):
    if user['role']=='STUDENT':raise ForbiddenError()

def report_access(user,kind):
    employee(user)
    if kind not in REPORT_NAMES:raise ForbiddenError('未知报告类型')
    if kind in {'COMPLAINT_WEEK','MANAGER_WEEK'} and not user['is_dept_head']:raise ForbiddenError('仅主管或管理员可用')
    if kind=='PSYCH_WEEK' and not user['psych_access_enabled']:raise ForbiddenError('需要心理授权')
    if kind=='COMPLAINT_WEEK' and not user['can_handle_feedback']:raise ForbiddenError('需要售后授权')

def visible_students(user):return user['_students']
def own_daily(user,daily):
    if not daily or daily.user_id!=user['id']:raise NotFoundError('日报不存在')
def manager_daily(user,daily):
    if not user['is_dept_head']:raise ForbiddenError('仅主管可审核')
    if not daily or (not user['is_admin'] and daily.dept_id not in user['dept_ids']):raise NotFoundError('日报不存在')
def required_access(user,required):
    return all(bool(user.get(key)) for key in required or [])
def report_record_access(user,report):
    if not report:raise NotFoundError('报告不存在')
    report_access(user,report.kind)
    if not user['is_admin'] and (report.dept_id not in user['dept_ids'] or (not user['is_dept_head'] and report.owner_id!=user['id'])):raise NotFoundError()
    if not required_access(user,report.required_capabilities):raise ForbiddenError('专项权限已变化')
    allowed={s['id'] for s in user['_students'] if report.kind!='PSYCH_WEEK' or s['consent']=='GRANTED'}
    if not set(report.scope_student_ids or [])<=allowed:raise NotFoundError('学生范围或授权已变化，请重新生成')
def capabilities(user):
    result=[]
    for kind in REPORT_NAMES:
        try:report_access(user,kind);result.append(kind)
        except ForbiddenError:pass
    return {'report_types':result,'is_dept_head':user['is_dept_head'],'is_admin':user['is_admin'],
        'can_write_daily':not user['is_dept_head'],'scope':'GLOBAL' if user['is_admin'] else 'DEPARTMENT' if user['is_dept_head'] else 'SELF',
        'assistant_endpoint':'/api/v1/m5/chat/messages','generation_endpoint':'/api/v1/reports/preview'}
