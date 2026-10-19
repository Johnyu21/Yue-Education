<script setup lang="ts">
import {ref,onMounted,onUnmounted,nextTick,watch} from 'vue'
import {MessageSquare, X, Send, Grip, ClipboardCheck, Sparkles, ArrowUpRight, LoaderCircle} from 'lucide-vue-next'
import {dateLocal} from './api'
import {employeeAssistantApi} from './assistants'
import {uuid} from './api/uuid'
const props=defineProps<{user:any}>()
const emit=defineEmits(['draft','proposal','error'])
const open=ref(false),loading=ref(false),sending=ref(false),message=ref(''),chat=ref<any>({messages:[],draft:{},version:1}),students=ref<any[]>([]),student=ref(''),day=ref(dateLocal()),aiMode=ref('UNKNOWN'),pending=ref<any>(null)
const feed=ref<HTMLElement|null>(null),button=ref<HTMLElement|null>(null)
const position=ref({x:window.innerWidth-95,y:window.innerHeight-190})
let start:{x:number,y:number,bx:number,by:number}|null=null,moved=false
const clamp=()=>{position.value.x=Math.max(12,Math.min(window.innerWidth-72,position.value.x));position.value.y=Math.max(12,Math.min(window.innerHeight-72,position.value.y))}
function down(e:PointerEvent){start={x:e.clientX,y:e.clientY,bx:position.value.x,by:position.value.y};moved=false;button.value?.setPointerCapture(e.pointerId)}
function move(e:PointerEvent){if(!start)return;const dx=e.clientX-start.x,dy=e.clientY-start.y;if(Math.abs(dx)+Math.abs(dy)>5)moved=true;position.value={x:start.bx+dx,y:start.by+dy};clamp()}
function up(){if(start&&moved)localStorage.setItem('yue-report-assistant-position:'+props.user.id,JSON.stringify(position.value));start=null}
async function scrollBottom(){await nextTick();feed.value?.scrollTo({top:feed.value.scrollHeight,behavior:'smooth'})}
async function load(){
 loading.value=true
 try{chat.value=await employeeAssistantApi.load();day.value=chat.value.draft.report_date||dateLocal();aiMode.value=chat.value.ai_mode;students.value=props.user.employeeRole==='NEWCOMER'?[]:await employeeAssistantApi.students();await scrollBottom()}
 catch(e:any){emit('error',e.message)}finally{loading.value=false}
}
async function toggle(){if(moved){moved=false;return}open.value=!open.value;if(open.value)await load()}
async function send(value?:string){
 const text=(value||message.value).trim();if(!text||sending.value||loading.value)return;sending.value=true
 try{
  if(!pending.value||pending.value.message!==text||pending.value.student_id!==(student.value||null)||pending.value.report_date!==day.value)pending.value={message:text,request_key:uuid(),expected_version:chat.value.version,student_id:student.value||null,report_date:day.value}
  const result=await employeeAssistantApi.send(pending.value);pending.value=null
  chat.value=await employeeAssistantApi.load();message.value='';await scrollBottom()
  if(result.ai_status==='UNAVAILABLE')emit('error','Dify暂不可用，原内容已保留，可手动填写')
 }catch(e:any){emit('error',e.message);if(e.code==='VERSION_CONFLICT'){pending.value=null;await load()}}finally{sending.value=false}
}
function draft(){emit('draft',{...chat.value.draft});open.value=false}
onMounted(()=>{try{const p=JSON.parse(localStorage.getItem('yue-report-assistant-position:'+props.user.id)||'null');if(p)position.value=p}catch{}clamp();window.addEventListener('resize',clamp)})
onUnmounted(()=>window.removeEventListener('resize',clamp))
watch(()=>props.user?.id,()=>{open.value=false;chat.value={messages:[],draft:{},version:1}})
</script>
<template>
 <button ref="button" class="assistant-launch" :style="{left:position.x+'px',top:position.y+'px'}" aria-label="打开报告助手" @pointerdown="down" @pointermove="move" @pointerup="up" @pointercancel="up" @click="toggle">
  <MessageSquare :size="25"/><span>报告助手</span>
 </button>
 <section v-if="open" class="assistant-panel" aria-label="报告助手对话框">
  <header><div class="assistant-avatar"><Sparkles :size="20"/></div><div><strong>报告智能助手</strong><small>{{aiMode==='DIFY'?'日报收集与报告条件准备':'AI状态以每次回复为准'}}</small></div><button class="icon-btn" aria-label="关闭助手" @click="open=false"><X :size="20"/></button></header>
  <div class="assistant-controls"><label>工作日期<input v-model="day" type="date" :max="dateLocal()"></label><label>关联学生<select v-model="student"><option value="">暂不关联</option><option v-for="s in students" :key="s.id" :value="s.id">{{s.name}} · {{s.class_name}}</option></select></label></div>
  <div ref="feed" class="chat-feed">
   <div class="chat-welcome"><Sparkles :size="25"/><h3>从一句话开始，整理今天的工作</h3><p>可以分几次告诉我。缺少必要信息时，我会接着询问。</p></div>
   <div v-if="loading" class="empty"><LoaderCircle class="spin"/>正在恢复对话</div>
   <div v-for="(m,i) in chat.messages" :key="i" class="chat-line" :class="m.role"><div class="bubble">{{m.content}}<small v-if="m.ai_status==='DEMO'">规则演示</small><button v-if="m.proposal" class="mini-action" @click="emit('proposal',m.proposal);open=false">核对并生成 <ArrowUpRight :size="14"/></button></div></div>
   <div v-if="sending" class="chat-line assistant"><div class="bubble"><LoaderCircle class="spin" :size="15"/> 正在整理…</div></div>
  </div>
  <div v-if="chat.draft.content?.work_summary" class="draft-preview"><ClipboardCheck :size="18"/><span>已收集 {{chat.draft.content.items?.length||0}} 项工作</span><button @click="draft">查看日报草稿 →</button></div>
  <div class="quick-prompts"><button @click="send('今天交付了两个学生，跟踪了三个学生的入学进度')">记录今日工作</button><button @click="send('新增客户有哪些')">新增客户</button><button @click="send('生成周报')">生成周报</button></div>
  <form class="chat-compose" @submit.prevent="send()"><textarea v-model="message" aria-label="给报告助手发送消息" placeholder="告诉我今天完成了哪些工作…" rows="2" @keydown.enter.exact.prevent="send()"></textarea><button class="btn primary square" :disabled="loading||sending||!message.trim()" aria-label="发送消息"><Send :size="18"/></button></form>
  <p class="assistant-note">生成内容需本人确认，助手不会替你提交或办理业务。</p>
 </section>
</template>
