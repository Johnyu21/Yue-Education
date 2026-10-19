<script setup lang="ts">
import {ref,computed,onMounted,onUnmounted,watch} from 'vue'
import {useRoute,useRouter} from 'vue-router'
import {ArrowUpRight,ArrowRight,GraduationCap,Globe2,CalendarDays,Users,LayoutDashboard,ContactRound,FileText,ChartNoAxesCombined,Settings,LogOut,Bell,ChevronRight,Search,Plus,Download,Check,RotateCcw,ClipboardList,ShieldCheck,Menu,X,LoaderCircle,BookOpen,MapPin,Clock3,ChevronDown,Sparkles,Building2,LockKeyhole} from 'lucide-vue-next'
import Assistant from './Assistant.vue'
import StudentMultiSelect from './components/StudentMultiSelect.vue'
import VisitorPages from './VisitorPages.vue'
import StudentDetail from './StudentDetail.vue'
import BusinessWorkspace from './components/BusinessWorkspace.vue'
import AccountSettings from './components/AccountSettings.vue'
import LoginVideoBackdrop from './components/LoginVideoBackdrop.vue'
import WorkspaceHeader from './components/WorkspaceHeader.vue'
import PersonalProfile from './components/PersonalProfile.vue'
import OperationForm from './components/OperationForm.vue'
import AccountManagement from './components/AccountManagement.vue'
import AssistantDock from './components/AssistantDock.vue'
import RecordView from './components/RecordView.vue'
import {api,errorText,writeRequest} from './api/client'
import {dailyPayload,reportPayload} from './api/domain'
import {items,normalizeUser,normalizeStudent,getStudents} from './api'
import {reportAssistantApi} from './assistants'
import {reportsApi,tokenStore,reportNames,categoryNames,statusNames,dateLocal} from './api'
const route=useRoute(),router=useRouter()
const user=ref<any>(null),health=ref<any>({ai_mode:'DEMO'}),workspace=ref<any>({students:[],leads:[],daily:[]}),dailies=ref<any[]>([]),reports=ref<any[]>([])
const profileOpen=ref(false),passwordOpen=ref(false)
const savedDigest=ref('')
const dailyDirty=computed(()=>!!editor.value&&JSON.stringify(editor.value.content)!==savedDigest.value)
const toast=ref(''),busy=ref(false),mobileMenu=ref(false),username=ref(''),password=ref(''),loginError=ref('')
const path=computed(()=>route.path),isApp=computed(()=>path.value.startsWith('/app')),isLogin=computed(()=>path.value==='/login')
const studentDetailId=computed(()=>/^\/app\/students\/([^/]+)$/.exec(path.value)?.[1]||'')
const page=computed(()=>studentDetailId.value?'students':path.value.split('/').pop()||'dashboard')
const showAssistant=computed(()=>!!user.value&&user.value.role!=='STUDENT'&&['/app/daily','/app/reports'].includes(path.value))
const visibleReportTypes=computed(()=>Object.entries(reportNames).filter(([kind])=>allowed(kind)))
const dailyPage=ref(0),dailyHistory=ref<any>(null),reviewDaily=ref<any>(null),notifications=ref<any>({unread:0})
const nav=[{key:'dashboard',name:'工作台',icon:LayoutDashboard},{key:'leads',name:'客户管理',icon:ContactRound},{key:'students',name:'学生服务',icon:GraduationCap},{key:'daily',name:'日报管理',icon:ClipboardList},{key:'reports',name:'报告中心',icon:ChartNoAxesCombined},{key:'organization',name:'组织通讯录',icon:Users},{key:'settings',name:'管理设置',icon:Settings}]
const extraNav=[{key:'accounts',name:'账号管理',icon:Users},{key:'services',name:'行政申请',icon:ClipboardList},{key:'feedback',name:'投诉与售后',icon:ShieldCheck},{key:'psych',name:'心理关怀',icon:ShieldCheck},{key:'catalog',name:'项目与活动',icon:BookOpen},{key:'notifications',name:'通知消息',icon:Bell}]
const visibleNav=computed(()=>{if(user.value?.mustChangePassword)return [nav[6]];if(user.value?.role==='STUDENT')return [nav[0],{key:'student',name:'我的服务',icon:GraduationCap},{key:'notifications',name:'通知消息',icon:Bell},nav[6]];return [...nav.slice(0,5).filter(n=>n.key!=='leads'||(['ADVISOR','SENIOR_ADVISOR','ADMIN'].includes(user.value?.employeeRole)&&!(user.value?.classTeacherOfIds?.length&&!user.value?.isAdmin&&!user.value?.isDeptHead))).filter(n=>n.key!=='reports'||user.value?.report_types?.length).filter(n=>n.key!=='students'||user.value?.employeeRole!=='NEWCOMER'),...extraNav.filter(n=>n.key!=='accounts'||user.value?.isAdmin).filter(n=>n.key!=='feedback'||user.value?.canHandleFeedback).filter(n=>n.key!=='psych'||user.value?.psychAccessEnabled),...nav.slice(5)]})
const pageName=computed(()=>visibleNav.value.find(n=>n.key===page.value)?.name||'服务概览')
const search=ref(''),statusFilter=ref('ALL'),editor=ref<any>(null)
const currentReport=ref<any>(null),reportType=ref('CUSTOMER_OPERATION'),end=ref(dateLocal()),start=ref(weekStart()),reportTab=ref('preview'),duplicate=ref<any>(null)
const descriptions:Record<string,string>={CUSTOMER_OPERATION:'从接待到入学，让每一次跟进都有迹可循。',DAILY_DAY:'把一天的工作放在一起，清楚看到进展。',DAILY_WEEK:'回顾一周的工作，梳理成果与待办。',PSYCH_WEEK:'汇总已授权的关怀记录，关注持续跟进。',COMPLAINT_WEEK:'追踪问题与处理结果，推动服务闭环。',MANAGER_WEEK:'结合部门数据，整理本周管理工作。'}
function weekStart(){const d=new Date();d.setDate(d.getDate()-((d.getDay()+6)%7));return String(d.getFullYear())+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0')}
let noticeTimer:ReturnType<typeof setTimeout>|undefined
function notice(message:string){if(noticeTimer)clearTimeout(noticeTimer);toast.value=message;noticeTimer=setTimeout(()=>{toast.value=''},5000)}
function go(p:string){router.push(p);mobileMenu.value=false}
async function establishUser(raw:any){
 if(raw.mustChangePassword){user.value=normalizeUser(raw);go('/app/settings');return}
 const results=await Promise.allSettled([raw.userType==='EMPLOYEE'?api.get('/m5/capabilities'):Promise.resolve({}),api.get('/organization/departments')])
 const cap=results[0].status==='fulfilled'?results[0].value:{}
 const departments=results[1].status==='fulfilled'?items(results[1].value):[]
 user.value=normalizeUser(raw,cap,departments)
 if(!allowed(reportType.value)&&user.value.report_types.length)reportType.value=user.value.report_types[0]
}
async function refresh(){
 if(!user.value||user.value.mustChangePassword)return
 const owner=user.value.id
 const employee=user.value.userType==='EMPLOYEE'
 const jobs:[string,Promise<any>][]=[['notifications',api.get('/me/notifications')]]
 if(employee){jobs.push(['students',user.value.employeeRole==='NEWCOMER'?Promise.resolve([]):getStudents()],['dailies',api.get(user.value.is_dept_head?'/employees/daily-reports':'/me/daily-reports',{offset:dailyPage.value*50,limit:50})],['reports',reportsApi.get('/reports')])}
 else jobs.push(['profile',api.get('/me/student-profile')])
 const results=await Promise.allSettled(jobs.map(j=>j[1]))
 if(user.value?.id!==owner)return
 for(let i=0;i<jobs.length;i++){const r=results[i];if(r.status==='rejected'){notice(errorText(r.reason));continue}const key=jobs[i][0],data=r.value;if(key==='notifications')notifications.value=data;else if(key==='students')workspace.value.students=data;else if(key==='profile')workspace.value.students=[normalizeStudent(data)];else if(key==='dailies')dailies.value=items(data);else if(key==='reports')reports.value=items(data)}
}
async function login(){const u=(username.value||'').trim(),p=password.value||'';if(!u||!p){loginError.value='请输入账号和密码';return}busy.value=true;loginError.value='';try{const data=await api.post('/auth/login',{username:u,password:p});tokenStore.set(data.accessToken);password.value='';await establishUser(data.user);editor.value=null;currentReport.value=null;if(!user.value.mustChangePassword){await refresh();go('/app/dashboard')}}catch(e){loginError.value=errorText(e)}finally{busy.value=false}}
async function logout(){profileOpen.value=false;passwordOpen.value=false;notifications.value={items:[],unread:0};tokenStore.clear();user.value=null;dailies.value=[];reports.value=[];workspace.value={students:[],leads:[],daily:[]};editor.value=null;currentReport.value=null;go('/login')}
async function historyDaily(d:any){try{dailyHistory.value=await reportsApi.get('/dailies/'+d.id+'/history')}catch(e){notice(errorText(e))}}
async function polishDaily(){if(!editor.value)return;busy.value=true;try{const d=await api.post('/me/daily-reports/'+editor.value.report_date+'/ai-draft',{message:editor.value.handoff_text||editor.value.content.work_summary||editor.value.original_text,content:editor.value.content});if(d.ai_status!=='UNAVAILABLE'&&d.draft?.content){editor.value.content=d.draft.content;editor.value.original_text=d.draft.content.work_summary;delete editor.value.handoff_text}notice(d.ai_status==='UNAVAILABLE'?'AI暂不可用，原草稿已保留':d.answer||'草稿已整理，请补齐提示内容并核对')}catch(e){notice(errorText(e))}finally{busy.value=false}}
function checkRoute(){if(user.value?.mustChangePassword&&path.value!=='/app/settings')go('/app/settings');else if(user.value?.role==='STUDENT'&&isApp.value&&!['/app/dashboard','/app/student','/app/settings','/app/notifications'].includes(path.value))go('/app/student')}
async function refreshNotifications(){if(!user.value||user.value.mustChangePassword)return;const owner=user.value.id;try{const data=await api.get('/me/notifications');if(user.value?.id===owner)notifications.value=data}catch(e){notice(errorText(e))}}
function notificationRoute(n:any){if(user.value?.role==='STUDENT')return '/app/student';const map:Record<string,string>={admin_service:'/app/services',feedback_ticket:'/app/feedback',psych_alert:'/app/psych',lead:'/app/leads',application_case:'/app/students',enrollment:'/app/students',report:'/app/daily',event:'/app/catalog'};return map[n.relatedType]||'/app/notifications'}
async function openNotification(n:any){if(!n.read)try{await api.post('/me/notifications/'+n.id+'/read');await refreshNotifications()}catch(e){notice(errorText(e))}go(notificationRoute(n))}
function showPassword(){profileOpen.value=false;passwordOpen.value=true}
function expired(){user.value=null;go('/login');notice('登录已失效，请重新登录')}

function clone(value:any){return JSON.parse(JSON.stringify(value))}
function emptyDaily(){return {report_date:dateLocal(),original_text:'',content:{work_summary:'',items:[],difficulties:'',next_plan:''},version:null,status:'DRAFT'}}
function editDaily(d?:any){editor.value=d?clone(d):emptyDaily();savedDigest.value=d?JSON.stringify(d.content):''}
async function importedDraft(d:any){
 go('/app/daily')
 const reportDate=d.report_date||dateLocal()
 const existing=dailies.value.find(x=>x.employee_user_id===user.value.id&&x.report_date===reportDate)
 if(existing?.status==='SUBMITTED'){notice('该日期日报待审核，请先撤回再导入');return}
 savedDigest.value=existing?JSON.stringify(existing.content):''
 if(!d.content){
  editor.value=existing?clone(existing):emptyDaily()
  editor.value.handoff_text=d.original_text||''
  notice('已载入口述原文，请核对日期并点击“AI 整理草稿”，或手工补入今日工作；原有日报内容已保留')
  return
 }
 editor.value={...(existing?clone(existing):emptyDaily()),report_date:reportDate,content:d.content,original_text:d.content.work_summary}
 notice('已载入助手草稿，请检查并保存')
}
async function saveDaily(){
 if(!editor.value)return
 busy.value=true
 try{const d=await writeRequest('PUT','/m5/dailies',dailyPayload(editor.value));editor.value=d;savedDigest.value=JSON.stringify(d.content);await refresh();notice('日报草稿已保存')}
 catch(e:any){notice(errorText(e))}finally{busy.value=false}
}
async function actionDaily(d:any,action:string){
 if(action==='SUBMIT'&&editor.value?.id===d.id&&dailyDirty.value){notice('请先保存最新修改，再提交审核');return}
 let reason=''
 if(action==='RETURN'){const value=prompt('请填写退回原因');if(value===null)return;reason=value;if(!reason.trim()){notice('退回原因不能为空');return}}
 busy.value=true
 try{const result=await writeRequest('POST','/m5/dailies/'+d.id+'/action',{action,expected_version:d.version,reason});if(editor.value?.id===d.id)editor.value=result;await refresh();notice(action==='APPROVE'?'审核通过':action==='RETURN'?'日报已退回':action==='WITHDRAW'?'已撤回为草稿':'已提交主管审核')}
 catch(e:any){notice(errorText(e))}finally{busy.value=false}
}
function allowed(kind:string){return !!user.value?.report_types?.includes(kind)}
async function generate(){
 busy.value=true;duplicate.value=null
 try{currentReport.value=await reportAssistantApi.generate({type:reportType.value,start_date:start.value,end_date:end.value,employee_user_ids:[]});reportTab.value='preview';notice('报告预览已生成，请核对并保存')}
 catch(e:any){notice(errorText(e))}finally{busy.value=false}
}
async function proposal(p:any){reportType.value=p.type;start.value=p.start_date;end.value=p.end_date;go('/app/reports');await generate()}
function selectType(type:string){if(!allowed(type))return;reportType.value=type;currentReport.value=null;duplicate.value=null;if(type==='DAILY_DAY'){start.value=dateLocal();end.value=dateLocal()}else{start.value=weekStart();end.value=dateLocal()}}
async function saveReport(mode='normal'){
 const r=currentReport.value;if(!r)return
 const same=reports.value.find(x=>x.type===r.type&&x.start_date===r.start_date&&x.end_date===r.end_date&&x.status==='DRAFT'&&x.owner_id===user.value.id)
 // Each new preview is saved as its own immutable metric snapshot.
 const target=mode==='update'?duplicate.value:mode==='copy'?null:r
 busy.value=true
 try{
  currentReport.value=await writeRequest('POST','/m5/reports',reportPayload(r,target))
  duplicate.value=null;await refresh();notice('报告已保存，可在已保存报告中重新打开')
 }catch(e:any){notice(errorText(e))}finally{busy.value=false}
}
async function openReport(r:any){try{currentReport.value=await reportsApi.get('/reports/'+r.id);reportType.value=r.type;start.value=r.start_date;end.value=r.end_date;reportTab.value='preview'}catch(e:any){notice(errorText(e))}}
async function submitWeekly(){const r=currentReport.value;if(!r?.id){notice('请先保存草稿');return}try{currentReport.value=await writeRequest('POST','/m5/reports/'+r.id+'/submit',{expected_version:r.version});await refresh();notice('主管周报已提交生效，无需审核')}catch(e:any){notice(errorText(e))}}
async function exportReport(fmt:string){
 if(!currentReport.value?.id){notice('请先保存报告，再导出');return}
 try{const blob=await reportsApi.export(currentReport.value.id,fmt);const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=currentReport.value.title+'.'+fmt;a.click();URL.revokeObjectURL(url)}
 catch(e:any){notice(errorText(e))}
}
function newItem(){editor.value.content.items.push({category:'OTHER',description:'',student_ids:[],count:1,result:'',source_event_id:null})}
const filteredDailies=computed(()=>dailies.value.filter(d=>(statusFilter.value==='ALL'||d.status===statusFilter.value)&&(!search.value||(d.employee_display_name+d.content.work_summary+d.report_date).includes(search.value))))
const pending=computed(()=>dailies.value.filter(d=>d.status==='SUBMITTED').length)
const approved=computed(()=>dailies.value.filter(d=>d.status==='APPROVED').length)
watch(path,async p=>{checkRoute();if(p.startsWith('/app')&&!user.value&&!tokenStore.get())go('/login');if(p.startsWith('/app')&&user.value)try{await refresh()}catch(e:any){notice(errorText(e))}})
onUnmounted(()=>window.removeEventListener('auth-expired',expired))
onMounted(async()=>{
 window.addEventListener('auth-expired',expired)
 try{health.value=await api.get('/health/live');if(tokenStore.get()){await establishUser(await api.get('/auth/me'));checkRoute();await refresh()}else if(isApp.value)go('/login')}
 catch(e){if(!user.value&&isApp.value)go('/login');notice(errorText(e))}
 api.get('/health/ready').catch(()=>{health.value={...health.value,ready:false}})
})
</script>
<template>
 <div class="app-root">
  <template v-if="!isApp">
   <header class="public-header" :class="{'visitor-public-header':!isLogin}"><a class="brand" href="#/"><span class="brand-mark"><GraduationCap :size="29"/></span><span><strong>粤教服务</strong><small>YUE EDUCATION SERVICE</small></span></a><nav aria-label="主导航"><a :class="{active:path==='/'}" href="#/">首页</a><a href="#/projects" :class="{active:path==='/projects'||path.startsWith('/project/')||path==='/interest'}">留学项目</a><a v-if="!isLogin" href="#/policies" :class="{active:path==='/policies'||path.startsWith('/policy/')}">留学政策</a><a href="#/events" :class="{active:path==='/events'}">活动资讯</a><a href="#/about" :class="{active:path==='/about'}">关于我们</a></nav><button class="btn outline login-entry" @click="go(user?'/app/dashboard':'/login')">{{user?'进入工作台':'系统登录'}} <ArrowUpRight :size="16"/></button></header>
   <template v-if="isLogin">
    <main class="login-layout"><section class="login-story"><LoginVideoBackdrop/><div class="login-story-content"><span class="eyebrow light">YUE EDUCATION · SERVICE PLATFORM</span><h1>让教育服务<br>更有温度，更有效率。</h1><p>连接学生、顾问与服务团队，<br>让每一份努力都有记录，每一步成长都有回应。</p><div class="login-line"></div><div class="story-points"><span><ShieldCheck :size="20"/> 权限清晰</span><span><Sparkles :size="20"/> 智能协作</span><span><Globe2 :size="20"/> 全程服务</span></div><div class="campus-line"><Building2 :size="150" :stroke-width=".6"/><GraduationCap :size="95" :stroke-width=".7"/></div></div></section><section class="login-form"><span class="eyebrow">WELCOME BACK</span><h2>欢迎登录</h2><p class="muted">进入你的教育服务工作空间</p><form @submit.prevent="login"><label>登录账号<input v-model="username" autocomplete="username" required placeholder="请输入正式账号"></label><label>密码<input v-model="password" type="password" autocomplete="current-password"></label><p v-if="loginError" class="error-text">{{loginError}}</p><button class="btn primary full" :disabled="busy">{{busy?'正在登录…':'登录工作空间'}}<ArrowRight :size="18"/></button></form><p class="login-help">首次登录请使用管理员分配的账号，登录后按提示修改初始密码。</p></section></main>
   </template>
   <template v-else>
    <VisitorPages :path="path" @navigate="go"/>
   </template>
   <footer class="public-footer"><div class="brand"><GraduationCap :size="28"/><strong>粤教服务</strong></div><p>连接世界，陪伴成长</p><small>{{isLogin?'粤教教育服务管理平台':'项目资料供咨询参考；虚拟补充资料均单独标注'}}</small></footer>
  </template>
  <template v-else-if="user">
   <WorkspaceHeader :user="user" :notifications="notifications" @navigate="go" @logout="logout" @profile="profileOpen=true" @password="showPassword" @notification="openNotification" @refresh-notifications="refreshNotifications"/>
   <div class="workspace-shell"><aside class="sidebar" :class="{visible:mobileMenu}"><span class="nav-caption">服务管理</span><button v-for="n in visibleNav" :key="n.key" :class="{active:page===n.key}" @click="go('/app/'+n.key)"><component :is="n.icon" :size="19"/>{{n.name}}<span v-if="n.key==='daily'&&pending" class="nav-count">{{pending}}</span></button><div class="sidebar-foot"><ShieldCheck :size="23"/><strong>教育服务工作空间</strong><p>按岗位与负责范围提供服务<br>业务操作均由本人确认</p></div></aside>
   <main class="workspace-main"><div class="workspace-breadcrumb"><button class="icon-btn mobile-only" @click="mobileMenu=!mobileMenu" aria-label="展开菜单"><Menu :size="18"/></button>工作空间<ChevronRight :size="13"/>{{pageName}}<span>{{dateLocal()}}</span></div>
    <AccountSettings v-if="user.mustChangePassword" :user="user" @password-changed="logout"/>
    <template v-else-if="page==='dashboard'">
     <section class="greeting"><div><span class="eyebrow">YOUR WORKSPACE</span><h1>{{user.real_name}}，工作有序，服务有温度。</h1><p>从今天的工作开始，让每一次跟进都留下清晰记录。</p><button v-if="user.role!=='STUDENT'" class="btn primary" @click="go(user.is_dept_head?'/app/reports':'/app/daily')">{{user.is_dept_head?'生成部门周报':'记录今日工作'}}<ArrowRight :size="17"/></button></div><div class="greeting-art"><ClipboardList :size="114" :stroke-width=".8"/><span><Sparkles :size="21"/></span></div></section>
     <div v-if="user.role!=='STUDENT'" class="metric-grid"><article><span>可查看学生</span><strong>{{workspace.students?.length||0}}<small>人</small></strong><p>按本人关系或本部门范围</p></article><article><span>{{user.is_dept_head?'本页部门待审核':'本页我的待审核'}}</span><strong>{{pending}}<small>篇</small></strong><p>提交后等待主管核对</p></article><article><span>本页已通过日报</span><strong>{{approved}}<small>篇</small></strong><p>可用于正式报告汇总</p></article><article><span>已保存报告</span><strong>{{reports.length}}<small>份</small></strong><p>草稿与主管周报</p></article></div>
     <BusinessWorkspace v-if="user.role!=='STUDENT'" page="dashboard" :user="user" @changed="refresh"/><section v-else class="paper student-welcome"><h3>我的学习与服务</h3><p>在我的服务中查看档案、成绩、日程和申请进度；如需请假、咨询或反馈，可核对后直接提交。</p><button class="btn primary" @click="go('/app/student')">进入我的服务</button></section><div v-if="user.role!=='STUDENT'" class="dashboard-columns"><section class="paper"><div class="panel-title"><h3>{{user.is_dept_head?'本部门近期工作':'近期工作记录'}}</h3><button class="text-link" @click="go('/app/daily')">查看全部 <ArrowUpRight :size="15"/></button></div><div v-for="d in dailies.slice(0,4)" :key="d.id" class="activity-row"><span class="activity-icon"><FileText :size="18"/></span><div><strong>{{d.content.work_summary}}</strong><small>{{d.employee_display_name}} · {{d.report_date}}</small></div><span class="status" :class="d.status">{{statusNames[d.status]}}</span></div><p v-if="!dailies.length" class="muted">暂无日报记录。</p></section><section class="paper shortcut-card"><h3>快捷入口</h3><button @click="go('/app/reports')"><ChartNoAxesCombined :size="21"/><div><strong>报告中心</strong><small>生成、保存与导出工作报告</small></div><ArrowUpRight :size="17"/></button><button @click="go('/app/students')"><GraduationCap :size="21"/><div><strong>学生服务</strong><small>查看学生与服务进度</small></div><ArrowUpRight :size="17"/></button><div class="info-box">报告助手仅在日报管理和报告中心显示。拖动悬浮按钮可调整位置。</div></section></div>
    </template>
    <template v-else-if="page==='daily'">
     <div class="page-heading"><div><span class="eyebrow">DAILY JOURNAL</span><h1>{{user.is_dept_head?'部门日报审核':'我的工作日报'}}</h1><p>{{user.is_dept_head?'核对本部门工作记录，通过后纳入汇总。':'零散记录，完整整理。每一天的工作都值得被看见。'}}</p></div><button v-if="!user.is_dept_head" class="btn primary" @click="editDaily()"><Plus :size="17"/>填写日报</button></div>
     <section v-if="editor&&!user.is_dept_head" class="paper daily-editor"><div class="panel-title"><h3>{{editor.id?'编辑工作日报':'新建日报草稿'}}</h3><button class="icon-btn" aria-label="关闭日报编辑器" @click="editor=null"><X :size="18"/></button></div><div v-if="editor.return_reason" class="info-box danger">退回原因：{{editor.return_reason}}</div><div class="form-row"><label>工作日期<input v-model="editor.report_date" :disabled="!!editor.id" type="date" :max="dateLocal()"></label><span class="subtle-tag">明日计划选填 · 支持补写</span></div><label v-if="editor.handoff_text!==undefined">员工助手转入的工作原文<textarea v-model="editor.handoff_text" rows="3" placeholder="请核对口述原文，再整理普通工作"></textarea><small>原文尚未写入日报；请点击 AI 整理，或手工补入下方今日工作。</small></label><label>今日工作概述 <b>*</b><textarea v-model="editor.content.work_summary" rows="3" placeholder="今天完成了哪些工作？"></textarea></label><div class="panel-title small-title"><h4>工作明细</h4><button class="btn secondary sm" :disabled="busy||(!editor.content.work_summary&&!editor.handoff_text)" @click="polishDaily">AI 整理草稿</button><button class="btn secondary sm" @click="newItem"><Plus :size="15"/>添加工作</button></div><div v-for="(item,i) in editor.content.items" :key="i" class="work-item"><select v-model="item.category"><option v-for="(v,k) in categoryNames" :key="k" :value="k">{{v}}</option></select><input v-model="item.description" aria-label="工作描述" placeholder="工作描述"><input v-model.number="item.count" type="number" min="0" aria-label="工作数量" class="count-input"><StudentMultiSelect v-model="item.student_ids" :students="workspace.students"/><button class="icon-btn" aria-label="删除工作项" @click="editor.content.items.splice(i,1)"><X :size="15"/></button></div><div class="form-columns"><label>困难与所需支持 <b>*</b><textarea v-model="editor.content.difficulties" rows="2" placeholder="没有困难可填写“无”"></textarea></label><label>明日计划 <span class="muted">选填</span><textarea v-model="editor.content.next_plan" rows="2" placeholder="可以稍后再安排"></textarea></label></div><div class="form-actions"><span>草稿可修改，提交前请核对事实与数量。</span><button class="btn outline" :disabled="busy||editor.status==='SUBMITTED'" @click="saveDaily">保存草稿</button><button class="btn primary" :disabled="busy||dailyDirty||!editor.id||!['DRAFT','RETURNED'].includes(editor.status)" @click="actionDaily(editor,'SUBMIT')">提交审核 <ArrowRight :size="15"/></button></div></section>
     <section class="paper"><div class="table-toolbar"><div class="filter-tabs"><button v-for="(v,k) in {ALL:'全部',DRAFT:'草稿',SUBMITTED:'待审核',RETURNED:'已退回',APPROVED:'已通过'}" :key="k" :class="{active:statusFilter===k}" @click="statusFilter=k">{{v}}</button></div><div class="search-field"><Search :size="16"/><input v-model="search" placeholder="搜索内容或日期"></div></div><div class="table-scroll"><table><thead><tr><th>工作日期</th><th>员工</th><th>工作概述</th><th>状态</th><th>操作</th></tr></thead><tbody><tr v-for="d in filteredDailies" :key="d.id"><td>{{d.report_date}}</td><td>{{d.employee_display_name}}</td><td class="summary-cell"><strong>{{d.content.work_summary}}</strong><small v-if="d.return_reason">退回原因：{{d.return_reason}}</small></td><td><span class="status" :class="d.status">{{statusNames[d.status]}}</span></td><td><div class="row-actions"><button @click="historyDaily(d)">通过历史</button><template v-if="user.is_dept_head"><button class="btn secondary sm" @click="reviewDaily=d">查看</button><button v-if="d.status==='SUBMITTED'" class="btn primary sm" :disabled="busy" @click="actionDaily(d,'APPROVE')">通过</button><button v-if="d.status==='SUBMITTED'" class="btn danger sm" :disabled="busy" @click="actionDaily(d,'RETURN')">退回</button></template><template v-else><button v-if="d.status!=='SUBMITTED'" @click="editDaily(d)">{{d.status==='APPROVED'?'修改重审':'编辑'}}</button><button v-if="d.status==='SUBMITTED'" :disabled="busy" @click="actionDaily(d,'WITHDRAW')">撤回</button><button v-if="['DRAFT','RETURNED'].includes(d.status)" class="btn primary sm" :disabled="busy" @click="actionDaily(d,'SUBMIT')">提交</button></template></div></td></tr><tr v-if="!filteredDailies.length"><td colspan="5" class="empty">当前筛选下暂无日报</td></tr></tbody></table></div><div class="table-footer pagination"><span>当前页 {{filteredDailies.length}} 篇</span><div><button class="btn outline" :disabled="dailyPage===0" @click="dailyPage--;refresh()">上一页</button><span>第 {{dailyPage+1}} 页</span><button class="btn outline" :disabled="dailies.length<50" @click="dailyPage++;refresh()">下一页</button></div></div></section>
    </template>
    <template v-else-if="page==='reports'">
     <div class="page-heading"><div><span class="eyebrow">INTELLIGENT REPORTS</span><h1>把工作记录，变成清晰洞察。</h1><p>数字来自后端统计，文字由助手整理；生成后可核对、编辑与导出。</p></div><span class="data-scope"><ShieldCheck :size="16"/>{{user.is_dept_head?'本部门数据':reportType==='PSYCH_WEEK'?'本人负责的学生':'本人数据'}}</span></div>
     <div class="report-types"><button v-for="[kind,name] in visibleReportTypes" :key="kind" :class="{active:reportType===kind}" @click="selectType(kind)"><FileText :size="17"/>{{name}}</button></div>
     <section class="paper report-controls"><div><h3>{{reportNames[reportType]}}</h3><p>{{descriptions[reportType]}}</p></div><label>开始日期<input v-model="start" type="date" :max="end"></label><span class="date-separator">—</span><label>结束日期<input v-model="end" type="date" :max="dateLocal()"></label><button class="btn primary" :disabled="busy" @click="generate"><LoaderCircle v-if="busy" class="spin" :size="17"/><Sparkles v-else :size="17"/>{{busy?'正在生成':'生成报告'}}</button></section>
     <div class="report-view-tabs"><button :class="{active:reportTab==='preview'}" @click="reportTab='preview'">报告预览</button><button :class="{active:reportTab==='history'}" @click="reportTab='history'">已保存报告 <span>{{reports.length}}</span></button></div>
     <template v-if="reportTab==='preview'">
      <div v-if="!currentReport" class="report-empty"><div class="empty-report-icon"><ChartNoAxesCombined :size="46" :stroke-width="1"/></div><h3>一份清晰的报告，从这里开始</h3><p>选择报告类型与日期范围，点击“生成报告”。<br>你也可以通过右下角的报告助手提出要求。</p><div><span><Check :size="14"/>范围内数据</span><span><Check :size="14"/>可编辑保存</span><span><Check :size="14"/>Word / PDF</span></div></div>
      <section v-else class="report-document"><div class="report-document-top"><div><span class="eyebrow">YUE EDUCATION · REPORT</span><h2><input v-model="currentReport.title" aria-label="报告标题" :readonly="currentReport.status==='SUBMITTED'"></h2><p>{{currentReport.start_date}} 至 {{currentReport.end_date}}<span>·</span>{{currentReport.scope}}</p></div><span class="status" :class="currentReport.ai_status==='LIVE'?'APPROVED':'DRAFT'">{{currentReport.ai_status==='LIVE'?'Dify 生成':currentReport.ai_status==='UNAVAILABLE'?'AI不可用，保留指标':currentReport.ai_status==='MANUAL'?'已保存内容':'规则演示'}}</span></div><div class="report-metrics"><div v-for="m in currentReport.metrics" :key="m.key" :title="m.formula"><span>{{m.label}}</span><strong>{{m.value}}<small>{{m.unit}}</small></strong></div></div><label class="report-body-label">报告正文<span>可直接修改，提交前请核对</span><textarea v-model="currentReport.narrative" :readonly="currentReport.status==='SUBMITTED'" rows="19" aria-label="报告正文"></textarea></label><div class="report-warnings"><p v-for="(w,i) in currentReport.warnings" :key="i">{{w}}</p></div><div v-if="duplicate" class="duplicate-box"><strong>同一范围已存在草稿</strong><p>请选择更新已有草稿，或保留它并另存一份。</p><button class="btn outline" @click="saveReport('update')">更新已有草稿</button><button class="btn primary" @click="saveReport('copy')">另存一份</button></div><div class="report-actions"><span>{{currentReport.status==='SUBMITTED'?'主管周报已提交生效':'核对后保存，之后可以重新打开'}}</span><button class="btn outline" :disabled="!currentReport.id" @click="exportReport('docx')"><Download :size="15"/>Word</button><button class="btn outline" :disabled="!currentReport.id" @click="exportReport('pdf')"><Download :size="15"/>PDF</button><button v-if="currentReport.status!=='SUBMITTED'" class="btn primary" :disabled="busy" @click="saveReport()">保存草稿</button><button v-if="currentReport.type==='MANAGER_WEEK'&&currentReport.status!=='SUBMITTED'" class="btn dark" :disabled="!currentReport.id" @click="submitWeekly">确认提交</button></div></section>
     </template>
     <section v-else class="paper"><div class="table-scroll"><table><thead><tr><th>报告名称</th><th>统计范围</th><th>状态</th><th>更新时间</th><th></th></tr></thead><tbody><tr v-for="r in reports" :key="r.id"><td><strong>{{r.title}}</strong></td><td>{{r.start_date}} — {{r.end_date}}</td><td><span class="status" :class="r.status">{{r.status==='SUBMITTED'?'已生效':'草稿'}}</span></td><td>{{r.updated_at.slice(0,16).replace('T',' ')}}</td><td><button class="text-link" @click="openReport(r)">打开 <ArrowUpRight :size="15"/></button></td></tr><tr v-if="!reports.length"><td colspan="5" class="empty">尚未保存报告，先生成一份试试。</td></tr></tbody></table></div></section>
    </template>
    <StudentDetail v-else-if="studentDetailId" :key="user.id+':'+studentDetailId" :student-id="studentDetailId" :user="user" @back="go('/app/students')"/>
    <AccountManagement v-else-if="page==='accounts'" :user="user" @self-reset="logout" @changed="refresh"/>
    <AccountSettings v-else-if="page==='settings'" :user="user" @password-changed="logout"/>
    <BusinessWorkspace v-else :key="page+':'+user.id" :page="page" :user="user" @changed="refresh"/>
    <footer class="workspace-footer">粤教服务 · 教育服务管理平台<span>业务数据按当前授权范围展示</span></footer>
   </main></div>
   <PersonalProfile v-if="profileOpen" :user="user" @close="profileOpen=false" @password="showPassword"/>
   <OperationForm v-if="passwordOpen&&!user.mustChangePassword" path="/api/v1/auth/password-change" method="POST" title="修改密码" @close="passwordOpen=false" @saved="logout"/>
   <AssistantDock v-if="!user.mustChangePassword" :user="user" :mode="user.role==='STUDENT'?'student':'employee'" :report-visible="showAssistant" @draft="importedDraft" @error="notice" @changed="refresh"/>
   <Assistant v-if="showAssistant&&!user.mustChangePassword" :key="user.id" :user="user" @draft="importedDraft" @proposal="proposal" @error="notice"/>
  </template>
  <div v-else class="loading-screen"><LoaderCircle class="spin"/>正在恢复工作空间…</div>
  <AssistantDock v-if="!isApp&&!isLogin" mode="visitor" :user="null" @error="notice"/>
  <div v-if="dailyHistory" class="modal-shade" @click.self="dailyHistory=null"><section class="operation-dialog"><div class="panel-title"><h2>日报通过历史</h2><button class="text-link" @click="dailyHistory=null">关闭</button></div><RecordView :value="dailyHistory"/></section></div>
  <div v-if="reviewDaily" class="modal-shade" @click.self="reviewDaily=null"><section class="operation-dialog daily-review-dialog"><div class="panel-title"><h2>{{reviewDaily.employee_display_name}} · {{reviewDaily.report_date}}</h2><button class="text-link" @click="reviewDaily=null">关闭</button></div><p class="review-summary">{{reviewDaily.content.work_summary}}</p><ul class="review-items"><li v-for="(i,index) in reviewDaily.content.items" :key="index">{{categoryNames[i.category]}}：{{i.description}}（{{i.count}}）</li></ul><p class="review-meta">困难与支持：{{reviewDaily.content.difficulties}}</p><p class="review-meta" v-if="reviewDaily.content.next_plan">明日计划：{{reviewDaily.content.next_plan}}</p></section></div>
  <div v-if="toast" role="status" class="toast">{{toast}}</div>
 </div>
</template>
