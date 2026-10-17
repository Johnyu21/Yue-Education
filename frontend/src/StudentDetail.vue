<script setup lang="ts">
import {ref,watch} from 'vue'
import {ArrowLeft,GraduationCap,LoaderCircle} from 'lucide-vue-next'
import {api,normalizeStudent} from './api'
import BusinessWorkspace from './components/BusinessWorkspace.vue'
const props=defineProps<{studentId:string;user:any}>()
defineEmits(['back'])
const student=ref<any>(null),loading=ref(false),error=ref('')
watch(()=>props.studentId,async(id,_,onCleanup)=>{
 let active=true;onCleanup(()=>{active=false});loading.value=true;student.value=null;error.value=''
 try{const data=await api.get('/employees/students/'+encodeURIComponent(id));if(active)student.value=normalizeStudent(data)}
 catch(e:any){if(active)error.value=e.message||'学生资料暂时无法加载'}
 finally{if(active)loading.value=false}
},{immediate:true})
</script>
<template>
 <section class="student-detail">
  <button class="text-link" @click="$emit('back')"><ArrowLeft :size="16"/>返回学生列表</button>
  <div class="page-heading"><div><span class="eyebrow">STUDENT PROFILE</span><h1>学生详细信息</h1><p>查看学生基本资料、所属班级与服务进度。</p></div><span class="subtle-tag">学生档案</span></div>
  <div v-if="loading" class="paper empty" role="status"><LoaderCircle class="spin"/>正在加载学生资料…</div>
  <div v-else-if="error" class="paper" role="alert"><h3>无法查看学生资料</h3><p>{{error}}</p><button class="btn outline" @click="$emit('back')">返回学生列表</button></div>
  <template v-else-if="student">
   <div class="student-detail-grid">
    <article class="paper"><div class="student-heading"><span class="student-avatar"><GraduationCap :size="25"/></span><div><h2>{{student.name}}</h2><p>学生编号：{{student.id}}</p></div><span class="pill">{{student.status||'未提供'}}</span></div><h3>基本资料</h3><dl class="student-detail-fields"><dt>所属部门</dt><dd>{{student.dept_name||'未提供'}}</dd><dt>所属班级</dt><dd>{{student.class_name||'未提供'}}</dd><dt>申请项目</dt><dd>{{student.project||'未提供'}}</dd></dl></article>
    <article class="paper"><h3>服务与跟进</h3><dl class="student-detail-fields"><dt>负责顾问</dt><dd>{{student.advisor_name||'未提供'}}</dd><dt>负责班主任</dt><dd>{{student.teacher_name||'未提供'}}</dd><dt>当前状态</dt><dd>{{student.status||'未提供'}}</dd><dt>当前进度</dt><dd>{{student.progress||'未提供'}}</dd></dl><p class="info-box">以下服务直接使用已授权的学生业务记录，变更前请核对。</p></article>
   </div>
   <BusinessWorkspace page="students" :user="user" :student-id="studentId" :resource-ids="['enrollments','scores','schedules','cases']"/>
  </template>
 </section>
</template>
