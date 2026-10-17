<script setup lang="ts">
import {ref,nextTick,watch,onMounted,onUnmounted} from 'vue'
import {ArrowRight,ArrowUpRight,ChevronUp,Play,Pause,Volume2,VolumeX,Maximize2} from 'lucide-vue-next'
import {promoVideoSession} from './promoVideoSession'
const props=defineProps<{active:boolean,title:string,subtitle:string}>()
const emit=defineEmits(['projects','policies','login'])
const video=ref<HTMLVideoElement|null>(null),expanded=ref(false),muted=ref(true),playing=ref(false),loaded=ref(props.active&&(window.location.hash.replace(/^#/,'')||'/').split('?')[0]==='/'),ready=ref(false),failed=ref(false),blocked=ref(false)
async function play(){
 if(!props.active||!video.value||!loaded.value)return
 video.value.muted=muted.value
 try{await video.value.play();blocked.value=false}catch{blocked.value=true}
}
async function expand(){expanded.value=true;await nextTick();window.scrollTo({top:0,behavior:'auto'});await play()}
async function collapse(){expanded.value=false;muted.value=true;if(video.value)video.value.muted=true;await play()}
async function toggleSound(){muted.value=!muted.value;if(video.value)video.value.muted=muted.value;await play()}
async function togglePlay(){if(!video.value)return;if(playing.value)video.value.pause();else await play()}
function finishResize(event:TransitionEvent){if(event.target===event.currentTarget&&event.propertyName==='height'&&props.active)window.scrollTo({top:0,behavior:'auto'})}
function escape(event:KeyboardEvent){if(props.active&&expanded.value&&event.key==='Escape')void collapse()}
watch(()=>props.active,async active=>{
 if(!active){expanded.value=false;muted.value=true;if(video.value){video.value.muted=true;video.value.pause()}return}
 loaded.value=true;await nextTick();await play()
})
onMounted(async()=>{
 if(props.active&&promoVideoSession.autoExpandPending){expanded.value=true;promoVideoSession.autoExpandPending=false;await nextTick();window.requestAnimationFrame(()=>window.scrollTo({top:0,behavior:'auto'}))}
 window.addEventListener('keydown',escape);await play()
})
onUnmounted(()=>{window.removeEventListener('keydown',escape);video.value?.pause();promoVideoSession.restoreScroll()})
</script>
<template>
 <section v-show="active" class="visitor-promo" :class="{'is-expanded':expanded,'is-ready':ready}" aria-label="留学宣传视频" :aria-expanded="expanded" @transitionend="finishResize">
  <video ref="video" class="visitor-promo-media" :src="loaded?'/visitor-video/intro-video.mp4':undefined" :muted="muted" :autoplay="active" loop playsinline preload="metadata" :aria-hidden="!expanded" aria-label="粤教留学宣传视频" @loadeddata="ready=true;play()" @play="playing=true" @pause="playing=false" @error="failed=true"/>
  <div class="visitor-promo-shade"></div>
  <template v-if="!expanded">
   <button class="visitor-promo-hit" aria-label="展开观看宣传视频" @click="expand"></button>
   <div class="visitor-promo-copy"><span class="eyebrow light">YUE EDUCATION · STUDY ABROAD</span><h1>{{title}}</h1><p>{{subtitle}}</p><div class="visitor-promo-actions"><button class="btn hero-btn" @click="emit('projects')">浏览留学项目 <ArrowRight :size="17"/></button><button class="visitor-promo-policy" @click="emit('policies')">阅读留学政策 <ArrowUpRight :size="16"/></button><button class="visitor-promo-watch" @click="expand"><Play :size="15" fill="currentColor"/>观看宣传视频</button></div></div>
   <span class="visitor-promo-badge"><Maximize2 :size="16"/>点击展开视频</span>
  </template>
  <template v-else>
   <div class="visitor-promo-heading"><span>YUE EDUCATION</span><strong>留学宣传视频</strong></div>
   <div v-if="!failed" class="visitor-promo-welcome"><span class="visitor-promo-kicker">YUE EDUCATION · STUDY ABROAD</span><h1>以专业服务，<br>陪伴国际求学之路</h1><p>了解国际教育项目，连接学生与服务团队。</p><div class="visitor-promo-entry"><button class="btn visitor-video-primary" @click="emit('projects')">了解留学项目 <ArrowRight :size="18"/></button><button class="btn visitor-video-secondary" @click="emit('login')">进入服务系统 <ArrowUpRight :size="18"/></button></div><span class="visitor-promo-welcome-note">国际教育 · 项目咨询 · 全程服务</span></div>
   <div v-if="failed" class="visitor-promo-status" role="status"><p>宣传视频暂时无法播放，可收起后继续浏览项目。</p></div>
   <div v-else-if="!ready" class="visitor-promo-status visitor-promo-loading" role="status">正在加载宣传视频…</div>
   <button v-else-if="blocked" class="visitor-promo-start" @click="play"><Play :size="26"/>播放宣传视频</button>
   <div class="visitor-promo-controls"><button :aria-label="playing?'暂停宣传视频':'播放宣传视频'" @click="togglePlay"><Pause v-if="playing" :size="17"/><Play v-else :size="17"/></button><button :aria-label="muted?'开启视频声音':'关闭视频声音'" :aria-pressed="!muted" @click="toggleSound"><VolumeX v-if="muted" :size="18"/><Volume2 v-else :size="18"/><span>{{muted?'开启声音':'关闭声音'}}</span></button></div>
   <button class="visitor-promo-collapse" aria-label="收起宣传视频" @click="collapse"><ChevronUp :size="22" fill="currentColor"/><span>收起视频</span></button>
  </template>
 </section>
</template>
<style scoped>
.visitor-promo{position:relative;isolation:isolate;overflow:hidden;height:360px;background:#612b30;color:white;transition:height .6s cubic-bezier(.22,.68,.2,1)}
.visitor-promo.is-expanded{height:80vh;background:#10181c}
.visitor-promo-media{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;filter:blur(7px);transform:scale(1.04);opacity:.65;transition:filter .5s,transform .5s,opacity .5s}
.is-expanded .visitor-promo-media{object-fit:contain;filter:none;transform:none;opacity:1}
.visitor-promo-shade{position:absolute;inset:0;background:linear-gradient(100deg,#542126df,#70262eaa 58%,#742e3566);pointer-events:none}
.is-expanded .visitor-promo-shade{background:radial-gradient(ellipse at 50% 46%,#101c2a70,transparent 76%),linear-gradient(#0b151d55,#0b151d24 30%,#0b151d40 75%,#0b151d8c)}
.visitor-promo-hit{position:absolute;inset:0;z-index:1;background:none;border:0;width:100%;height:100%;cursor:pointer}
.visitor-promo-copy{position:relative;z-index:2;pointer-events:none;width:90%;max-width:1320px;height:100%;margin:auto;display:flex;flex-direction:column;align-items:flex-start;justify-content:center}
.visitor-promo-copy h1{font-family:var(--serif);font-size:36px;font-weight:500;line-height:1.6;margin:0 0 17px;letter-spacing:.04em;max-width:950px;text-shadow:0 2px 12px #21101625}
.visitor-promo-copy p{font-size:15px;color:#f2dfdf;line-height:1.9;max-width:800px;margin:0}.visitor-promo-copy .eyebrow{margin-bottom:15px}
.visitor-promo-actions{display:flex;align-items:center;gap:24px;margin-top:28px;pointer-events:auto}.visitor-promo-policy{display:inline-flex;align-items:center;gap:7px;padding:8px 0;background:none;border:0;color:white;font-size:13px}.visitor-promo-watch{display:inline-flex;align-items:center;gap:8px;padding:10px 14px;border:1px solid #ffffff55;border-radius:5px;background:#ffffff12;color:white;font-size:13px}.visitor-promo-watch:hover{background:#ffffff25}
.visitor-promo-badge{position:absolute;right:5%;bottom:27px;z-index:2;pointer-events:none;display:flex;align-items:center;gap:8px;color:#f0dcdc;font-size:12px}
.visitor-promo-heading{position:absolute;top:24px;left:5%;display:flex;align-items:center;gap:14px;text-shadow:0 1px 6px #0008}.visitor-promo-heading span{font-size:10px;letter-spacing:.15em;color:#d8e0e4}.visitor-promo-heading strong{font-size:15px;font-weight:400}
.visitor-promo-controls{position:absolute;right:5%;bottom:25px;display:flex;gap:9px}.visitor-promo-controls button{display:flex;align-items:center;gap:8px;justify-content:center;min-height:38px;padding:9px 13px;color:white;background:#162028a6;border:1px solid #ffffff55;border-radius:5px;font-size:12px}.visitor-promo-controls button:hover{background:#33424ecc}
.visitor-promo-collapse{position:absolute;left:50%;bottom:12px;transform:translateX(-50%);display:flex;flex-direction:column;align-items:center;gap:2px;min-width:84px;padding:5px 12px 7px;border:1px solid #ffffff55;border-radius:8px;background:#18242ac9;color:white;font-size:11px}.visitor-promo-collapse:hover{background:#3a4851e8}
.visitor-promo-status{position:absolute;inset:0;display:grid;place-items:center;padding:35px;color:#d4dce0;font-size:14px;text-align:center;pointer-events:none}.visitor-promo-start{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);display:flex;align-items:center;gap:12px;padding:16px 22px;background:#16242abb;border:1px solid #fff8;border-radius:7px;color:white;font-size:16px}.visitor-promo button:focus-visible{outline:2px solid white;outline-offset:-5px}
.visitor-promo-welcome{position:absolute;left:50%;top:46%;transform:translate(-50%,-50%);width:min(700px,88%);text-align:center;color:#fff;animation:visitor-video-welcome .85s ease both;text-shadow:0 3px 24px #00121ca8}.visitor-promo-kicker{display:inline-block;font-size:11px;letter-spacing:.25em;margin-bottom:20px;color:#fff0e7}.visitor-promo-welcome h1{font-family:var(--serif);font-weight:500;font-size:47px;letter-spacing:.08em;line-height:1.65;margin:0 0 18px}.visitor-promo-welcome p{font-size:15px;line-height:1.9;color:#f0eded;margin:0}.visitor-promo-entry{display:flex;justify-content:center;gap:16px;margin:31px 0 22px}.visitor-promo-entry .btn{font-size:14px;min-height:48px;padding:13px 24px;border-radius:5px;display:inline-flex;gap:12px;align-items:center;transition:transform .2s,background .25s,box-shadow .25s}.visitor-video-primary{color:#9e2935;background:#fff;border:1px solid #fff;box-shadow:0 7px 25px #00132224}.visitor-video-primary:hover{background:#fff4ee;box-shadow:0 10px 30px #00132238;transform:translateY(-3px)}.visitor-video-secondary{color:white;border:1px solid #ffffffb3;background:#14212a47;backdrop-filter:blur(5px)}.visitor-video-secondary:hover{background:#ffffff24;transform:translateY(-3px)}.visitor-promo-welcome-note{font-size:10px;letter-spacing:.2em;color:#f4e6dcbd}.visitor-promo-loading{inset:60px 5% auto auto;display:block;padding:0;font-size:11px}.visitor-promo-start{top:77%;font-size:13px;padding:10px 16px}.visitor-promo-heading,.visitor-promo-controls,.visitor-promo-collapse{z-index:2}@keyframes visitor-video-welcome{from{opacity:0;translate:0 18px}to{opacity:1;translate:0 0}}
@media(max-width:760px){.visitor-promo{height:360px}.visitor-promo-copy h1{font-size:27px}.visitor-promo-copy p{font-size:13px}.visitor-promo-actions{gap:13px;flex-wrap:wrap}.visitor-promo-badge{display:none}.visitor-promo-controls{right:16px;bottom:23px}.visitor-promo-controls button span{display:none}.visitor-promo-heading{top:18px}.visitor-promo.is-expanded{height:80vh}}
@media(prefers-reduced-motion:reduce){.visitor-promo,.visitor-promo-media{transition:none}.visitor-promo-welcome{animation:none}.visitor-promo-entry .btn{transition:none}}
</style>
