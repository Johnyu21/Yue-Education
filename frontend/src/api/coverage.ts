import {contract} from './contract'
import {allConfiguredActions} from './resources'
const featureOperations:[string,string,string][]=[
 ['POST','/api/v1/employees/lead-imports/preview','Excel逐行预检'],['POST','/api/v1/employees/lead-imports/apply','确认批量导入'],
 ['POST','/api/v1/auth/login','正式登录'],['GET','/api/v1/auth/me','会话恢复与权限'],['POST','/api/v1/auth/password-change','首次及自主改密'],['POST','/api/v1/management/users/{user_id}/password-reset','管理员重置员工、学生及管理员密码'],
 ['POST','/api/v1/files','附件上传'],['GET','/api/v1/files/{object_key}','私有附件下载'],['POST','/api/v1/transcriptions','核对语音转写'],['POST','/api/v1/public/leads','访客咨询登记'],
 ['POST','/api/v1/assistants/visitor/messages','访客咨询悬窗'],['POST','/api/v1/assistants/employee/messages','企业员工悬窗'],['POST','/api/v1/assistants/student/messages','学生助手悬窗'],
 ['GET','/api/v1/m5/capabilities','报告类型与岗位能力'],['GET','/api/v1/m5/dailies','分页日报列表'],['PUT','/api/v1/m5/dailies','日报保存'],['GET','/api/v1/m5/dailies/{did}/history','日报通过历史'],['POST','/api/v1/m5/dailies/{did}/action','日报审核与提交'],
 ['POST','/api/v1/m5/reports/preview','生成报告快照'],['POST','/api/v1/reports/preview','报告生成入口'],['GET','/api/v1/m5/reports','已保存报告'],['POST','/api/v1/m5/reports','携快照保存报告'],['GET','/api/v1/m5/reports/{rid}','重开报告'],['POST','/api/v1/m5/reports/{rid}/submit','主管周报提交'],['GET','/api/v1/m5/reports/{rid}/export/{fmt}','Word与PDF导出'],
 ['GET','/api/v1/m5/chat','报告助手恢复会话'],['POST','/api/v1/m5/chat/messages','报告助手悬窗'],
 ['GET','/api/v1/me/daily-reports','本人日报'],['GET','/api/v1/employees/daily-reports','部门日报'],['POST','/api/v1/me/daily-reports/{report_date}/ai-draft','AI整理日报'],
 ['GET','/api/v1/health/live','进程连通检查'],['GET','/api/v1/health/ready','数据库就绪检查']
]
export const aliases:Record<string,string>={
 'PUT /api/v1/me/daily-reports/{report_date}':'PUT /api/v1/m5/dailies',
 'POST /api/v1/me/daily-reports/{report_id}/submit':'POST /api/v1/m5/dailies/{did}/action',
 'POST /api/v1/me/daily-reports/{report_id}/withdraw':'POST /api/v1/m5/dailies/{did}/action',
 'POST /api/v1/employees/daily-reports/{report_id}/approve':'POST /api/v1/m5/dailies/{did}/action',
 'POST /api/v1/employees/daily-reports/{report_id}/return':'POST /api/v1/m5/dailies/{did}/action',
}
export function apiCoverage(){const mapped=new Map(allConfiguredActions.map(a=>[a.method+' '+a.path,a.title]));for(const [m,p,n] of featureOperations)mapped.set(m+' '+p,n);for(const [alias,target] of Object.entries(aliases))if(mapped.has(target))mapped.set(alias,mapped.get(target)+'（兼容别名）');const actual=Object.entries(contract.paths).flatMap(([path,methods]:[string,any])=>Object.keys(methods).filter(m=>['get','post','patch','put','delete'].includes(m)).map(m=>m.toUpperCase()+' '+path));return {total:actual.length,connected:actual.filter(k=>mapped.has(k)).length,missing:actual.filter(k=>!mapped.has(k)),obsolete:[...mapped.keys()].filter(k=>!actual.includes(k)),entries:actual.map(endpoint=>({endpoint,feature:mapped.get(endpoint),alias:!!aliases[endpoint]}))}}
