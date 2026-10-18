<script setup lang="ts">
import {computed} from 'vue'
import {fieldLabel,displayValue} from '../api/contract'
const props=defineProps<{value:any}>()
const report=computed(()=>props.value?.report||{})
const projects=computed(()=>report.value.projects||[])
const facts=computed(()=>Object.entries(report.value.facts||{}).filter(([,v])=>v!=null&&v!==''))
const evidence=computed(()=>(report.value.evidence||[]).filter((e:any)=>e&&e.field))
const missing=computed(()=>report.value.missingFields||[])
const decided=(d:string)=>({MATCH:'符合',NO_MATCH:'不符合',NEEDS_INFO:'待补充'}[d]||displayValue(d))
</script>
<template>
 <div class="asm-report">
  <p class="asm-meta">研判状态：{{displayValue(value.assessmentStatus)}}<template v-if="value.assessedAt">｜研判时间：{{displayValue(value.assessedAt)}}</template><template v-if="value.isPreviousReport">｜<em>以下为最近一次成功报告</em></template></p>
  <section class="asm-projects">
   <div v-for="p in projects" :key="p.projectId" class="asm-project">
    <div class="asm-head"><strong>{{p.projectName}}</strong><span class="asm-badge" :class="p.decision">{{decided(p.decision)}}</span></div>
    <p v-if="p.failedRules?.length" class="asm-note">未满足：{{p.failedRules.join('、')}}</p>
    <p v-if="p.missingFields?.length" class="asm-note">待补充：{{p.missingFields.map((k:string)=>fieldLabel(k)).join('、')}}</p>
   </div>
   <p v-if="!projects.length" class="muted">暂无项目匹配结果。</p>
  </section>
  <p class="asm-score">综合匹配度：<strong>{{report.score??'—'}}</strong><small v-if="report.score==null">（存在待补充项目时不评分）</small></p>
  <section v-if="facts.length" class="asm-block"><h4>已核对事实</h4><p>{{facts.map(([k,v])=>fieldLabel(String(k))+'：'+displayValue(v)).join('｜')}}</p></section>
  <section v-if="missing.length" class="asm-block"><h4>待补充字段</h4><p class="asm-note">{{missing.map((k:string)=>fieldLabel(String(k))).join('、')}}</p></section>
  <details v-if="evidence.length" class="asm-evidence"><summary>提取证据（{{evidence.length}} 条）</summary><ul><li v-for="(e,i) in evidence" :key="i"><b>{{fieldLabel(String(e.field))}}</b>：{{e.snippet}}<small>（{{e.source_ref}}）</small></li></ul></details>
 </div>
</template>
<style scoped>
.asm-report{display:flex;flex-direction:column;gap:12px}
.asm-meta{margin:0;color:#68707c;font-size:13px}
.asm-project{border:1px solid var(--line,#e3e8ef);border-radius:8px;padding:10px 12px;display:flex;flex-direction:column;gap:4px}
.asm-head{display:flex;align-items:center;justify-content:space-between;gap:12px}
.asm-badge{padding:2px 10px;border-radius:999px;font-size:13px;white-space:nowrap}
.asm-badge.MATCH{background:#e6f6ec;color:#1d7a3d}
.asm-badge.NO_MATCH{background:#fdeaea;color:#b3261e}
.asm-badge.NEEDS_INFO{background:#fff6e0;color:#8a6100}
.asm-note{margin:0;color:#68707c;font-size:13px}
.asm-score{margin:0;font-size:14px}
.asm-block h4,.asm-projects h4{margin:0 0 6px;font-size:13px;color:#3a4250}
.asm-block p{margin:0;font-size:13px;line-height:1.6}
.asm-evidence summary{cursor:pointer;font-size:13px;color:#3a4250}
.asm-evidence ul{margin:8px 0 0;padding-left:18px;font-size:13px}
.asm-evidence li{margin-bottom:4px}
.asm-evidence small{color:#98a1ac;margin-left:6px}
</style>
