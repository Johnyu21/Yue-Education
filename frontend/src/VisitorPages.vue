<script setup lang="ts">
import {computed,ref,watch} from 'vue'
import {ArrowRight,ArrowUpRight,ArrowLeft,GraduationCap,Building2,Globe2,BookOpen,Check,ChevronRight,Clock3,Users} from 'lucide-vue-next'
import {projects,policies,findProject} from './visitorContent'
import demo from './visitorDemo.json'
import VisitorGallery from './VisitorGallery.vue'
import PublicInquiry from './components/PublicInquiry.vue'
import PublicServices from './components/PublicServices.vue'
import VisitorPromoVideo from './VisitorPromoVideo.vue'
import {useVisitorMotion} from './visitorMotion'
import './visitor-motion.css'
const props=defineProps<{path:string}>()
const emit=defineEmits<{navigate:[path:string]}>()
const motionRoot=ref<HTMLElement|null>(null)
const {progress}=useVisitorMotion(motionRoot,()=>props.path)
const project=computed(()=>findProject(props.path.split('/')[2]||''))
const policy=computed(()=>policies.find(p=>p.id===props.path.split('/')[2]))
const policyProjects=computed(()=>projects.filter(p=>p.policyId===policy.value?.id))
const detail=computed(()=>props.path.startsWith('/project/'))
const policyDetail=computed(()=>props.path.startsWith('/policy/'))
const listing=computed(()=>['/','/projects','/interest'].includes(props.path))
const relatedPolicy=computed(()=>policies.find(p=>p.id===project.value?.policyId))
const demoInfo=computed(()=>project.value?demo.projects[project.value.id as keyof typeof demo.projects]:null)
const inquiryOpen=ref(false)
const inquiry=ref({name:'',mobile:'',track:'',message:''})
const title=computed(()=>detail.value?(project.value?.name||'暂未找到这个项目'):policyDetail.value?(policy.value?.title||'暂未找到这篇指南'):props.path==='/policies'?'留学政策与申请资讯':props.path==='/about'?'专业教育服务，陪伴国际求学':props.path==='/events'?'项目交流与升学资讯':props.path==='/'?'以专业服务，陪伴国际求学之路':'国际教育项目与培养方案')
const subtitle=computed(()=>detail.value?(project.value?.intro||'请返回项目列表选择项目。'):policyDetail.value?(policy.value?.intro||'请返回政策列表查看。'):props.path==='/policies'?'涵盖院校资质、语言准备、签证申请与实习安排等留学资讯。':'德国职业培训与新加坡升学项目，涵盖培养安排、申请指导及海外衔接等服务。')
function go(path:string){emit('navigate',path)}
function jump(id:string){document.getElementById('visitor-'+id)?.scrollIntoView({behavior:'smooth',block:'start'})}
watch(()=>props.path,()=>{inquiryOpen.value=false;inquiry.value={name:'',mobile:'',track:'',message:''};window.scrollTo({top:0,behavior:'auto'})})
</script>
<template>
 <div ref="motionRoot" class="visitor-pages">
  <div class="visitor-reading-progress" aria-hidden="true" :style="{transform:'scaleX('+progress+')'}"></div>
  <VisitorPromoVideo :active="path==='/'" :title="title" :subtitle="subtitle" @projects="jump('projects')" @policies="go('/policies')" @login="go('/login')"/>
  <section v-if="path!=='/'" class="visitor-hero" :class="{home:path==='/'}"><div class="visitor-hero-inner"><div><span class="eyebrow light">{{detail?project?.en:policyDetail?'STUDY ABROAD GUIDE':'YUE EDUCATION · STUDY ABROAD'}}</span><h1>{{title}}</h1><p>{{subtitle}}</p><div class="visitor-hero-actions"><button v-if="listing" class="btn hero-btn" @click="jump('projects')">浏览留学项目 <ArrowRight :size="17"/></button><button v-else-if="detail&&project" class="btn hero-btn" @click="jump('overview')">项目介绍 <ArrowRight :size="17"/></button><button v-if="listing||detail" class="visitor-light-link" @click="detail&&project?jump('policy'):go('/policies')">{{detail?'查看相关政策':'阅读留学政策'}} <ArrowUpRight :size="16"/></button></div></div><div class="visitor-hero-art" aria-hidden="true"><Globe2 :size="185" :stroke-width=".6"/><span>GERMANY / SINGAPORE</span><strong>YOUR NEXT CHAPTER</strong></div></div></section>
  <div class="visitor-nav"><div class="visitor-location"><button @click="go('/')">首页</button><ChevronRight :size="13"/><span>{{detail?'项目详情':policyDetail?'政策指南':path==='/policies'?'留学政策':path==='/about'?'关于我们':path==='/events'?'活动资讯':'留学项目'}}</span></div><nav class="visitor-quick-links" aria-label="访客快捷入口"><a href="#/projects" :class="{active:path==='/projects'||detail}"><BookOpen :size="19" aria-hidden="true"/><span>项目一览</span><ArrowUpRight :size="17" aria-hidden="true"/></a><a href="#/policies" :class="{active:path==='/policies'||policyDetail}"><Globe2 :size="19" aria-hidden="true"/><span>政策指南</span><ArrowUpRight :size="17" aria-hidden="true"/></a></nav></div>
  <main class="visitor-main">
   <template v-if="listing">
    <VisitorGallery group="campus"/><PublicServices mode="projects"/>
    <section id="visitor-projects"><div class="visitor-section-title"><div><span class="eyebrow">OUR PROGRAMMES</span><h2>{{path==='/interest'?'项目咨询与服务':'国际教育项目资料导览'}}</h2><p>提供德国职业培训与新加坡升学项目的培养方案、申请条件、费用参考及政策资讯。</p></div><span class="visitor-source-tag">根据公司项目资料整理</span></div>
     <div class="visitor-project-grid"><article v-for="(p,i) in projects" :key="p.id" class="visitor-project-card"><div class="visitor-project-cover" :class="p.policyId"><span>{{p.en}}</span><Building2 :size="110" :stroke-width=".7"/><b>0{{i+1}}</b></div><div class="visitor-project-content"><span class="pill">{{p.subtitle}}</span><h3>{{p.name}}</h3><p>{{p.intro}}</p><dl><dt>适合人群</dt><dd>{{p.audience}}</dd><dt>培养安排</dt><dd>{{p.duration}}</dd></dl><div class="visitor-card-bottom"><span><BookOpen :size="15"/>项目与政策介绍</span><a class="btn outline" :href="'#/project/'+p.id">了解项目 <ArrowUpRight :size="16"/></a></div></div></article></div>
    </section>
    <section class="visitor-decision"><span class="eyebrow">PLANNING & SUPPORT</span><h2>升学规划与配套服务</h2><div><article><span>01</span><h3>培养方案咨询</h3><p>结合不同教育背景与学习目标，提供职业培训、本科衔接及后续硕士申请等方向的咨询。</p></article><article><span>02</span><h3>申请准备与指导</h3><p>围绕语言学习、入学测试、申请材料与签证安排，提供相应信息与准备指导。</p></article><article><span>03</span><h3>费用与政策咨询</h3><p>提供项目费用构成与相关政策说明，支持留学预算与申请安排。</p></article></div></section>
    <VisitorGallery group="community"/>
    <section class="visitor-policy-overview"><div class="visitor-section-title"><div><span class="eyebrow">COUNTRY GUIDES</span><h2>留学政策与申请资讯</h2></div><a class="text-link" href="#/policies">查看政策指南 <ArrowRight :size="16"/></a></div><div class="visitor-policy-grid"><a v-for="p in policies" :key="p.id" class="visitor-policy-card" :href="'#/policy/'+p.id"><Globe2 :size="26"/><h3>{{p.title}}</h3><p>{{p.intro}}</p><span>阅读指南 <ArrowUpRight :size="16"/></span></a></div></section>
   </template>
   <template v-else-if="detail&&project">
    <nav class="visitor-section-nav" aria-label="项目内容导航"><button @click="jump('overview')">项目简介</button><button @click="jump('routes')">培养路线</button><button @click="jump('costs')">费用参考</button><button @click="jump('policy')">政策简介</button><button @click="jump('faq')">常见问题</button></nav>
    <div class="visitor-detail-layout"><div class="visitor-detail-main">
     <section id="visitor-overview" class="visitor-paper"><span class="eyebrow">PROGRAMME OVERVIEW</span><h2>项目介绍与培养特色</h2><p v-for="text in project.overview" :key="text">{{text}}</p><div class="visitor-facts"><div><Users :size="20"/><small>适合人群</small><strong>{{project.audience}}</strong></div><div><BookOpen :size="20"/><small>语言准备</small><strong>{{project.language}}</strong></div><div><Clock3 :size="20"/><small>培养时间</small><strong>{{project.duration}}</strong></div></div><h3>专业与培养方向</h3><div class="visitor-tags"><span v-for="f in project.focus" :key="f">{{f}}</span></div><h3>申请条件与入学要求</h3><ul class="visitor-check-list"><li v-for="r in project.requirements" :key="r"><Check :size="16"/><span>{{r}}</span></li></ul></section>
     <section id="visitor-routes" class="visitor-paper"><span class="eyebrow">LEARNING PATHWAYS</span><h2>培养路线与学习安排</h2><article v-for="(r,i) in project.routes" :key="r.title" class="visitor-route"><div><span>0{{i+1}}</span><h3>{{r.title}}</h3></div><p>{{r.audience}}</p><small><Clock3 :size="14"/>{{r.time}}</small><ol><li v-for="step in r.steps" :key="step">{{step}}</li></ol></article></section>
     <section id="visitor-costs" class="visitor-paper"><span class="eyebrow">COST PLANNING</span><h2>项目费用与预算参考</h2><p>以下费用根据项目资料整理，供规划参考；实际收费及适用批次以正式方案为准。</p><details v-for="cost in project.costs" :key="cost.title" class="visitor-accordion"><summary>{{cost.title}}<span>展开查看</span></summary><div class="visitor-table-wrap"><table><caption>{{cost.title}}明细</caption><thead><tr><th>阶段</th><th>金额或安排</th><th>说明</th></tr></thead><tbody><tr v-for="r in cost.rows" :key="r.stage"><td>{{r.stage}}</td><td>{{r.amount}}</td><td>{{r.note}}</td></tr></tbody></table></div><p class="visitor-cost-note">{{cost.note}}</p></details></section>
     <section id="visitor-policy" class="visitor-paper" v-if="relatedPolicy"><span class="eyebrow">POLICY ESSENTIALS</span><h2>{{relatedPolicy.title}}</h2><p>{{relatedPolicy.intro}}</p><div v-for="t in relatedPolicy.topics" :key="t.title" class="visitor-policy-topic"><h3>{{t.title}}</h3><p>{{t.text}}</p></div><a class="text-link" :href="'#/policy/'+relatedPolicy.id">阅读完整政策简介与官方入口 <ArrowRight :size="16"/></a><p class="visitor-source">项目说明与通用政策分别适用。政策资料为项目介绍参考，具体办理要求以主管机关当期公布的信息为准。</p></section>
     <section class="visitor-paper"><span class="eyebrow">APPLICATION & SUPPORT</span><h2>申请与服务安排</h2><ol class="visitor-flow"><li v-for="(step,i) in project.flow" :key="step"><b>0{{i+1}}</b><span>{{step}}</span></li></ol><h3>项目配套服务</h3><ul class="visitor-check-list"><li v-for="s in project.services" :key="s"><Check :size="16"/><span>{{s}}</span></li></ul></section>
     <section id="visitor-faq" class="visitor-paper"><span class="eyebrow">COMMON QUESTIONS</span><h2>常见问题解答</h2><details v-for="f in project.faqs" :key="f.q" class="visitor-accordion"><summary>{{f.q}}</summary><p>{{f.a}}</p></details></section>
     <section v-if="demoInfo" class="visitor-paper visitor-demo"><span class="visitor-demo-badge">虚拟补充 · 课程演示</span><h2>示例开班与合作单位</h2><p>{{demo.notice}}</p><dl class="visitor-demo-fields"><dt>示例开班</dt><dd>{{demoInfo.batch}}</dd><dt>示例名额</dt><dd>{{demoInfo.capacity}}</dd><dt>示例培养单位</dt><dd>{{demoInfo.provider}}</dd><dt>示例衔接单位</dt><dd>{{demoInfo.partner}}</dd><dt>示例方向</dt><dd>{{demoInfo.course}}</dd></dl><details v-if="demoInfo.costs.length" class="visitor-accordion"><summary>虚拟补充费用<span>仅用于演示</span></summary><div v-for="c in demoInfo.costs" :key="c.stage"><h3>{{c.stage}}：{{c.amount}}</h3><p>{{c.note}}</p></div></details></section>
     <p class="visitor-source">项目来源：《{{project.sourceName}}》；政策整理参考《{{relatedPolicy?.sourceName}}》，相关官方入口另列。虚拟补充单独标注。</p>
    </div><aside class="visitor-consult" aria-label="项目咨询"><div class="visitor-paper"><span class="eyebrow">PROJECT CONSULTATION</span><h2>项目咨询服务</h2><p>如您希望进一步了解培养安排、申请条件或服务内容，可通过咨询表单留下意向。</p><div class="visitor-consult-topic"><GraduationCap :size="24"/><strong>{{project.name}}</strong></div><button class="btn primary full" :aria-expanded="inquiryOpen" @click="inquiryOpen=!inquiryOpen">{{inquiryOpen?'收起咨询表单':'咨询项目详情'}}<ArrowRight :size="16"/></button><p v-if="!inquiryOpen" class="visitor-small">浏览项目不需要填写个人信息。</p><PublicInquiry v-else :suggested-name="project.name"/><div class="visitor-side-links"><button @click="jump('routes')">培养路线介绍 <ChevronRight :size="14"/></button><button @click="jump('policy')">相关政策简介 <ChevronRight :size="14"/></button></div></div></aside></div>
   </template>
   <template v-else-if="path==='/policies'">
    <VisitorGallery group="community"/><div class="visitor-section-title"><div><span class="eyebrow">COUNTRY GUIDES</span><h2>目的地政策与申请服务资讯</h2><p>汇集德国与新加坡的留学申请要点，涵盖院校、课程、签证与实习等事项。</p></div></div><div class="visitor-policy-grid"><a v-for="p in policies" :key="p.id" class="visitor-policy-card" :href="'#/policy/'+p.id"><Globe2 :size="28"/><h3>{{p.title}}</h3><p>{{p.intro}}</p><span>查看申请要点 <ArrowUpRight :size="16"/></span></a></div></template>
   <template v-else-if="policyDetail&&policy"><article class="visitor-policy-document visitor-paper"><span class="eyebrow">APPLICATION INFORMATION</span><h2>留学申请政策概览</h2><section v-for="t in policy.topics" :key="t.title"><h3>{{t.title}}</h3><p>{{t.text}}</p></section><section><h3>官方政策查询</h3><a v-for="link in policy.links" :key="link.url" :href="link.url" target="_blank" rel="noopener noreferrer" class="visitor-official-link">{{link.label}} <ArrowUpRight :size="16"/></a><p class="visitor-source">参考材料：《{{policy.sourceName}}》。费用、时限与适用条件请以办理时信息为准。</p></section><section><h3>了解对应项目</h3><a v-for="p in policyProjects" :key="p.id" class="btn outline" :href="'#/project/'+p.id">{{p.name}} <ArrowRight :size="16"/></a></section></article></template>
   <template v-else-if="path==='/about'"><section class="visitor-about visitor-paper"><span class="eyebrow">ABOUT YUE EDUCATION</span><h2>广东省教育服务有限公司</h2><p>公司项目材料介绍，粤教服务创办于1981年，通过整合教育资源，搭建文化教育综合服务平台，服务广东教育事业。</p><p>本页面介绍中德精英人才共建计划与新加坡国际本硕升学计划。相关项目的培养方案、申请要求与政策资讯可供不同教育背景的学生及家庭了解与咨询。</p><h3>项目服务流程</h3><ol class="visitor-flow"><li v-for="(s,i) in ['了解项目与目标沟通','资料准备与申请安排','语言或入学准备','行前指导与海外衔接','学习与服务情况跟进','后续升学或职业规划']" :key="s"><b>0{{i+1}}</b><span>{{s}}</span></li></ol><a class="btn primary" href="#/projects">了解公司项目 <ArrowRight :size="16"/></a></section></template>
   <template v-else-if="path==='/events'"><PublicServices mode="events"/><section class="visitor-paper"><span class="eyebrow">PROJECT INFORMATION</span><h2>项目交流与申请准备</h2><p>项目交流活动的具体安排将另行公布，相关项目介绍与申请资讯可通过以下专题了解。</p><div class="visitor-policy-grid"><a class="visitor-policy-card" href="#/project/germany-talent"><h3>了解德国职业培训</h3><p>提供适用人群、德语准备、企业匹配及职业培训安排等项目说明。</p><span>查看项目 <ArrowRight :size="15"/></span></a><a class="visitor-policy-card" href="#/project/singapore-pathways"><h3>比较新加坡升学路线</h3><p>介绍不同学历起点的培养方案、本科衔接及后续硕士申请安排。</p><span>查看项目 <ArrowRight :size="15"/></span></a></div></section></template>
   <section v-else class="visitor-paper"><h2>暂未找到这个内容</h2><p>项目或指南可能已经调整，请回到项目列表继续了解。</p><a class="btn outline" href="#/projects"><ArrowLeft :size="16"/>返回项目列表</a></section>
  </main>
 </div>
</template>
<style src="./visitor.css"></style>
