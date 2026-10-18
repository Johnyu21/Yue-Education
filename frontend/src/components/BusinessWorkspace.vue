<script setup lang="ts">
import {computed,onBeforeUnmount,ref,watch} from 'vue'
import {useRouter,useRoute} from 'vue-router'
import {api,errorText} from '../api/client'
import {items} from '../api'
import {resources,pageResources,can,type Action} from '../api/resources'
import {operation,invoke,resolveSchema,fieldLabel,displayValue} from '../api/contract'
import SchemaField from './SchemaField.vue'
import RecordView from './RecordView.vue'
import {employeeTitle} from '../api/employee-labels'
import OperationForm from './OperationForm.vue'
import ImportPanel from './ImportPanel.vue'
import AssessmentReport from './AssessmentReport.vue'
const props=defineProps<{page:string;user:any;studentId?:string;resourceIds?:string[]}>()
const emit=defineEmits(['changed'])
let active=true,loadTicket=0,detailTicket=0,contextTicket=0
onBeforeUnmount(()=>{active=false;loadTicket++;detailTicket++;contextTicket++})
const route=useRoute(),router=useRouter(),tab=ref(''),rows=ref<any[]>([]),selected=ref<any>(null),detail=ref<any>(null),busy=ref(false),error=ref(''),query=ref<any>({page:1,page_size:20}),total=ref(0),student=ref(props.studentId||''),studentVersion=ref<number|undefined>(),contextProfile=ref<any>(null),readResult=ref<any>(undefined),readTitle=ref(''),action=ref<Action|null>(null),formParams=ref<any>({}),formOmit=ref<string[]>([]),choices=ref<Record<string,any[]>>({})
const available=computed(()=>(props.resourceIds||pageResources[props.page]||[]).map(k=>resources[k]).filter(r=>r&&can(r.gate,props.user)))
const resource=computed(()=>available.value.find(r=>r.id===tab.value)||available.value[0])
const columns=computed(()=>(resource.value?.columns||[]).filter(k=>props.user?.isAdmin||resource.value?.id!=='users'||k!=='username'))
const shownDetail=computed(()=>resource.value?.id==='users'&&detail.value?{...detail.value,employeeRole:employeeTitle(detail.value,choices.value.classes,choices.value.departments)}:detail.value)
const detailOmit=computed(()=>{const base=resource.value?.id==='users'&&!props.user.isAdmin?['username']:[];return resource.value?.id==='services'?[...base,'studentProfileId','version']:base})
const filters=computed(()=>(resource.value?operation(resource.value.path,'GET').parameters||[]:[]).filter((p:any)=>p.in==='query'&&!['page','page_size','offset','limit'].includes(p.name)))
const creates=computed(()=>(resource.value?.create||[]).filter(a=>actionAllowed(a)))
const actions=computed(()=>(resource.value?.actions||[]).filter(a=>actionAllowed(a)))
function actionAllowed(a:Action){if(!can(a.gate,props.user))return false;if(/\/enrollments(?:\/|$)|\/relationships$/.test(a.path)){
 const s=resource.value?.requiresStudent?contextProfile.value:selected.value
 if(!s)return false
 return !!(props.user?.isAdmin||s.advisor?.id===props.user?.id||s.advisorUserId===props.user?.id||props.user?.headOfDepartmentIds?.includes(s.classInfo?.deptId))
 }return true}
function params(row:any=selected.value){const r=resource.value;const p:any={student_id:props.studentId||student.value,user_id:row?.userId};if(r?.idParam){const value=r.idParam==='case_no'?row?.caseNo:r.idParam==='student_id'?row?.studentProfileId||row?.studentId||row?.id:row?.id;p[r.idParam]=value}return p}
function reset(){rows.value=[];selected.value=null;detail.value=null;readResult.value=undefined;error.value='';query.value={page:1,page_size:20};for(const p of (resource.value?operation(resource.value.path,'GET').parameters||[]:[])){if(p.in==='query'&&p.schema.default!==undefined)query.value[p.name]=p.schema.default}}
async function load(){if(!active||!resource.value)return;if(resource.value.requiresStudent&&!student.value&&!props.studentId){rows.value=[];return}busy.value=true;error.value='';const ticket=++loadTicket;const r=resource.value;const studentSnapshot=student.value;try{
 const result=await invoke('GET',r.path,params(),undefined,{...query.value})
 if(ticket!==loadTicket||resource.value?.id!==r.id||student.value!==studentSnapshot)return
 if(r.local){rows.value=result[r.local]||[];studentVersion.value=result.version;contextProfile.value=result}
 else if(r.id==='profile'||r.id==='assessment'){rows.value=[];selected.value=result;detail.value=result;studentVersion.value=result.version}
 else rows.value=items(result)
 if(r.id==='notifications'&&route.query.notification){const notice=rows.value.find(n=>String(n.id)===String(route.query.notification));if(notice){selected.value=notice;detail.value=notice}}
 total.value=result?.total??rows.value.length
 if(selected.value&&r.id!=='profile'&&r.id!=='assessment'){const replacement=rows.value.find(x=>(x.id||x.caseNo)===(selected.value.id||selected.value.caseNo));if(replacement)selected.value=replacement}
 }catch(e){if(ticket===loadTicket&&resource.value?.id===r.id)error.value=errorText(e)}finally{if(ticket===loadTicket)busy.value=false}}
async function choose(row:any){const resourceId=resource.value?.id;const ticket=++detailTicket;selected.value=row;detail.value=row;error.value='';if(resource.value?.detail){busy.value=true;try{const data=await invoke('GET',resource.value.detail,params(row));if(resource.value?.id!==resourceId||ticket!==detailTicket)return;detail.value=data;if(!Array.isArray(data)&&!data?.items)selected.value={...row,...data}}catch(e){error.value=errorText(e)}finally{busy.value=false}}}
async function operate(a:Action){error.value='';if(a.path.endsWith('/read')){busy.value=true;try{await invoke(a.method,a.path,params());await load();emit('changed')}catch(e){error.value=errorText(e)}finally{busy.value=false};return}if(a.path.endsWith('/psych-corrections')){try{const out=await invoke('GET','/api/v1/employees/students/{student_id}/psych-observations',params(),undefined,{page:1,page_size:100});const list=items(out);const latest=list.reduce((best:any,row:any)=>!best||row.versionNo>best.versionNo?row:best,null);if(!latest)throw new Error('当前没有可修正的观测');a={...a,preset:{...a.preset,replaces_profile_id:latest.id,expected_latest_version:latest.versionNo}}}catch(e){error.value=errorText(e);return}}if(a.read){busy.value=true;try{readResult.value=await invoke('GET',a.path,params(),undefined,{page:1,page_size:100});readTitle.value=a.title}catch(e){error.value=errorText(e)}finally{busy.value=false};return}if(a.path.endsWith('/handling')&&a.preset?.action==='ASSIGN')a={...a,preset:{...a.preset,assignee_user_id:props.user.id}}
formOmit.value=(a.path.endsWith('/decision')&&selected.value?.serviceType&&selected.value.serviceType!=='INFO_CHANGE')?['identity_verification']:[];formParams.value=params();action.value=a}
async function saved(result:any){const resourceId=resource.value?.id;if(result?.id){rows.value=rows.value.map(row=>row.id===result.id?{...row,...result}:row);if(selected.value?.id===result.id){selected.value={...selected.value,...result};detail.value=selected.value}}emit('changed');await load();if(resource.value?.id!==resourceId)return;if(result?.id&&selected.value?.id===result.id&&!resource.value?.detail){selected.value={...selected.value,...result};detail.value=selected.value}if(result?.id&&resource.value?.detail){const row={...result,id:result.id};await choose(row)}}
async function loadChoices(){
 const jobs:any[]=[['projects','/public/projects']]
 if(props.user?.userType==='EMPLOYEE')jobs.push(['users','/organization/users'],['departments','/organization/departments'],['classes','/organization/classes'],...(props.user.employeeRole!=='NEWCOMER'?[['students','/employees/students']]:[]))
 const settled=await Promise.allSettled(jobs.map(async([key,path])=>[key,items(await api.get(path,{page:1,page_size:100}))]))
 const collected:any={};for(const r of settled)if(r.status==='fulfilled')collected[r.value[0] as string]=r.value[1]
 if(active)choices.value=collected
}
function todoRoute(row:any){const t=String(row.type||'');router.push(t.includes('DAILY')?'/app/daily':t.includes('FOLLOW')?'/app/leads':t.includes('PSYCH')?'/app/psych':t.includes('FEEDBACK')?'/app/feedback':t.includes('APPLICATION')?'/app/students':'/app/services')}
watch(()=>[props.page,props.studentId,props.user?.id],async()=>{const ticket=++contextTicket;tab.value='';student.value=props.studentId||'';reset();await loadChoices();if(active&&ticket===contextTicket)await load()},{immediate:true})
watch(tab,async()=>{reset();await load()})
watch(()=>route.query.notification,()=>{if(resource.value?.id==='notifications'){const row=rows.value.find(n=>String(n.id)===String(route.query.notification));if(row)choose(row)}})
watch(student,async()=>{selected.value=null;detail.value=null;query.value.page=1;await load()})
</script>
<template>
 <section class="business-workspace">
  <div v-if="available.length>1" class="business-tabs"><button v-for="r in available" :key="r.id" :class="{active:resource?.id===r.id}" @click="tab=r.id">{{r.title}}</button></div>
  <template v-if="resource"><div class="page-heading"><div><span class="eyebrow">YUE EDUCATION · SERVICES</span><h1>{{resource.title}}</h1><p>{{resource.description}}</p></div><div class="business-actions"><button v-for="a in creates" :key="a.path" class="btn primary" @click="operate(a)">＋ {{a.title}}</button><button class="btn outline" :disabled="busy" @click="load">刷新</button></div></div>
   <section v-if="resource.requiresStudent&&!studentId" class="paper context-picker"><label>选择学生<select v-model="student"><option value="">请选择负责范围内的学生</option><option v-for="s in choices.students||[]" :key="s.id" :value="s.id">{{s.realName}} · {{s.className||'未分班'}}</option></select></label></section>
   <form v-if="filters.length" class="paper business-filters" @submit.prevent="query.page=1;load()"><SchemaField v-for="p in filters" :key="p.name" :schema="p.schema" :name="p.name" :model-value="query[p.name]" :choices="choices" @update:model-value="query[p.name]=$event"/><button class="btn outline">查询</button></form>
   <p v-if="error" class="error-callout" role="alert">{{error}}</p><p v-if="busy" class="loading-callout" role="status">正在加载…</p>
   <section v-if="columns.length" class="paper business-table"><div class="table-scroll"><table><thead><tr><th v-for="k in columns" :key="k">{{fieldLabel(k)}}</th><th>办理</th></tr></thead><tbody><tr v-for="(row,i) in rows" :key="row.id||row.key||row.caseNo||i" :class="{selected:selected===row}"><td v-for="(k,j) in columns" :key="k"><a v-if="j===0&&resource.id==='students'" class="text-link" :href="'#/app/students/'+row.id">{{displayValue(row[k])}}</a><button v-else-if="j===0" class="text-link" :disabled="busy" @click="choose(row)">{{typeof row[k]==='object'?row[k]?.title||row[k]?.name||'查看':displayValue(row[k])}}</button><span v-else>{{resource.id==='users'&&k==='employeeRole'?employeeTitle(row,choices.classes,choices.departments):typeof row[k]==='object'?row[k]?.title||row[k]?.name||'—':displayValue(row[k])}}</span></td><td><button v-if="resource.id==='todos'" class="text-link" @click="todoRoute(row)">前往办理</button><button v-else class="text-link" @click="choose(row)">查看详情</button><a v-if="resource.id==='students'" class="text-link" :href="'#/app/students/'+row.id">学生服务</a></td></tr><tr v-if="!rows.length&&!busy"><td :colspan="columns.length+1" class="empty">{{resource.requiresStudent&&!student&&!studentId?'请先选择学生':'当前范围暂无记录'}}</td></tr></tbody></table></div><div class="table-footer pagination"><span>当前页 {{rows.length}} 条 · 总计 {{total}} 条</span><div><button class="btn outline" :disabled="query.page<=1||busy" @click="query.page--;load()">上一页</button><span>第 {{query.page}} 页</span><button class="btn outline" :disabled="query.page*(query.page_size||20)>=total||busy" @click="query.page++;load()">下一页</button></div></div></section>
   <div v-if="selected&&columns.length" class="modal-shade" @click.self="selected=null;detail=null"><section class="operation-dialog" role="dialog" aria-modal="true" aria-label="资料详情"><div class="panel-title"><h3>资料详情</h3><button type="button" class="icon-btn" aria-label="关闭详情" @click="selected=null;detail=null">×</button></div><div class="business-actions"><button v-for="a in actions" :key="a.title" class="btn outline" :disabled="busy" @click="operate(a)">{{a.title}}</button><button v-if="resource.id==='students'&&user?.isAdmin" class="btn outline" @click="operate({title:'重置学生初始密码',method:'POST',path:'/api/v1/management/users/{user_id}/password-reset'})">重置学生密码</button></div><RecordView :value="shownDetail" :omit-keys="detailOmit" :hide-empty="true"/></section></div>
   <section v-else-if="selected" class="paper business-detail"><div class="panel-title"><h3>资料详情</h3></div><div class="business-actions"><template v-if="resource.id==='profile'"><span v-if="shownDetail?.psychConsentStatus==='GRANTED'" class="success-callout">已同意心理关怀：老师可在授权范围内关注你的状态并及时提供帮助。</span><button v-else class="btn primary" :disabled="busy" @click="operate(actions[0])">同意心理关怀</button></template><template v-else><button v-for="a in actions" :key="a.title" class="btn outline" :disabled="busy" @click="operate(a)">{{a.title}}</button></template></div><RecordView :value="shownDetail" :omit-keys="detailOmit" :hide-empty="true"/></section>
   <section v-if="readResult!==undefined" class="paper business-detail"><div class="panel-title"><h3>{{readTitle}}</h3><button class="text-link" @click="readResult=undefined">收起</button></div><AssessmentReport v-if="readResult?.report" :value="readResult"/><RecordView v-else :value="readResult"/></section>
   <ImportPanel v-if="page==='leads'&&can('advisor',user)" @changed="load"/>
  </template><section v-else class="paper empty"><h3>当前身份没有该板块的访问权限</h3><p>可从左侧菜单选择已授权的服务。</p></section>
  <OperationForm v-if="action" :key="action.method+action.path" :path="action.path" :method="action.method" :title="action.title" :params="formParams" :record="selected" :preset="{...action.preset,expected_student_version:studentVersion||selected?.version}" :choices="choices" :hide-login-account="resource?.id==='users'&&!user.isAdmin" :omit-fields="formOmit" @close="action=null" @saved="saved"/>
 </section>
</template>
