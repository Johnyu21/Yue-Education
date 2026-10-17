import http,{api,tokenStore,download} from './api/client'
export {tokenStore}
export const dateLocal=()=>{const d=new Date();return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0')}
export const reportNames:Record<string,string>={CUSTOMER_OPERATION:'客户经营报告',DAILY_DAY:'日报日汇总',DAILY_WEEK:'日报周汇总',PSYCH_WEEK:'心理周报',COMPLAINT_WEEK:'投诉周报',MANAGER_WEEK:'主管周报'}
export const categoryNames:Record<string,string>={CUSTOMER:'客户跟进',DELIVERY:'学生交付',ENROLLMENT:'入学跟进',LEAVE:'请假工作',OTHER:'其他普通工作'}
export const statusNames:Record<string,string>={DRAFT:'草稿',SUBMITTED:'待审核',RETURNED:'已退回',APPROVED:'已通过'}
export const items=(d:any):any[]=>Array.isArray(d)?d:(d?.items||[])
export function normalizeUser(u:any,cap:any={},departments:any[]=[]){return {...u,id:String(u.id),real_name:u.realName,role:u.userType==='STUDENT'?'STUDENT':u.classTeacherOfIds?.length?'TEACHER':u.employeeRole,role_name:u.userType==='STUDENT'?'学生':u.isAdmin?'管理员':u.isDeptHead?'部门主管':u.classTeacherOfIds?.length?'班主任':({ADVISOR:'顾问',SENIOR_ADVISOR:'高级顾问',NEWCOMER:'新员工'} as any)[u.employeeRole]||'员工',dept_name:departments.find(d=>d.id===u.deptId)?.name||'服务团队',is_dept_head:!!(cap.is_dept_head||u.isDeptHead||u.isAdmin),report_types:cap.report_types||[],capabilities:cap}}
export function normalizeStudent(s:any){return {...s,id:String(s.id),name:s.realName||s.user?.realName||s.name,class_name:s.className||s.classInfo?.name||'未分班',project:s.enrollments?.map((e:any)=>e.projectName).join('、')||'暂无项目关联',progress:s.status,advisor_name:s.advisor?.realName,teacher_name:s.classInfo?.headTeacher?.realName}}
export async function getStudents(){return items(await api.get('/employees/students',{page:1,page_size:100})).map(normalizeStudent)}
export const reportsApi={
 get:<T=any>(path:string,params?:any)=>api.get<T>('/m5'+path,params),
 post:<T=any>(path:string,data?:any)=>api.post<T>('/m5'+path,data),
 put:<T=any>(path:string,data?:any)=>api.put<T>('/m5'+path,data),
 export:async(id:string,format:string)=>{const r=await http.get('/m5/reports/'+id+'/export/'+format,{responseType:'blob'});return r.data as Blob}
}
export {api,download}
