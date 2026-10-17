<script setup lang="ts">
import {computed,ref,onMounted,onUnmounted,watch} from 'vue'
import {ArrowLeft,ArrowRight,Pause,Play,Images} from 'lucide-vue-next'
import galleries from './visitorGallery.json'
const props=defineProps<{group:keyof typeof galleries}>()
const gallery=computed(()=>galleries[props.group])
const index=ref(0),paused=ref(false),hovering=ref(false),focused=ref(false),reduced=ref(false)
const current=computed(()=>gallery.value.slides[index.value]||gallery.value.slides[0])
let timer:number|undefined
let motion:MediaQueryList|undefined
function stopTimer(){if(timer!==undefined){window.clearInterval(timer);timer=undefined}}
function startTimer(){stopTimer();timer=window.setInterval(()=>{if(!paused.value&&!hovering.value&&!focused.value&&!reduced.value&&!document.hidden)index.value=(index.value+1)%gallery.value.slides.length},6000)}
function select(next:number){index.value=(next+gallery.value.slides.length)%gallery.value.slides.length;startTimer()}
function focusOut(event:FocusEvent){if(!(event.currentTarget as HTMLElement).contains(event.relatedTarget as Node|null))focused.value=false}
function updateMotion(){reduced.value=!!motion?.matches}
watch(()=>props.group,()=>{index.value=0})
onMounted(()=>{motion=window.matchMedia('(prefers-reduced-motion: reduce)');updateMotion();motion.addEventListener('change',updateMotion);startTimer()})
onUnmounted(()=>{stopTimer();motion?.removeEventListener('change',updateMotion)})
</script>
<template>
 <section class="visitor-gallery" role="region" aria-roledescription="轮播" :aria-label="gallery.title" @mouseenter="hovering=true" @mouseleave="hovering=false" @focusin="focused=true" @focusout="focusOut">
  <div class="visitor-gallery-copy"><span class="eyebrow">{{gallery.eyebrow}}</span><h2>{{gallery.title}}</h2><p>{{gallery.description}}</p><div class="visitor-gallery-controls"><div class="visitor-gallery-dots" aria-label="轮播图片选择"><button v-for="(slide,i) in gallery.slides" :key="slide.src" :class="{active:i===index}" :aria-label="'显示第'+(i+1)+'张：'+slide.caption" :aria-pressed="i===index" @click="select(i)"></button></div><button class="visitor-gallery-toggle" :aria-label="paused?'播放轮播':'暂停轮播'" :aria-pressed="paused" @click="paused=!paused"><Play v-if="paused" :size="15"/><Pause v-else :size="15"/></button></div><small><Images :size="13"/>校园与学习场景示意</small></div>
  <figure class="visitor-gallery-picture"><Transition name="visitor-gallery-frame"><img :key="current.src" :src="current.src" :alt="current.alt" :style="{objectPosition:current.position}" width="736" height="420" decoding="async"></Transition><div class="visitor-gallery-shade"></div><figcaption><span>{{current.caption}}</span><small>{{String(index+1).padStart(2,'0')}} / {{String(gallery.slides.length).padStart(2,'0')}}</small></figcaption><div class="visitor-gallery-arrows"><button :aria-label="gallery.title+'：上一张'" @click="select(index-1)"><ArrowLeft :size="18"/></button><button :aria-label="gallery.title+'：下一张'" @click="select(index+1)"><ArrowRight :size="18"/></button></div></figure>
 </section>
</template>
<style scoped>
.visitor-gallery{display:grid;grid-template-columns:minmax(0,.85fr) minmax(0,1.15fr);overflow:hidden;border:1px solid #e3e6ea;border-radius:8px;background:#f0f2f4;margin:0 0 36px;min-height:320px}
.visitor-gallery-copy{padding:35px 40px;display:flex;flex-direction:column;align-items:flex-start;justify-content:center;background:linear-gradient(130deg,#f1f2f4,#f8f8f9)}
.visitor-gallery-copy .eyebrow{font-size:10px;margin-bottom:15px;letter-spacing:.16em}.visitor-gallery-copy h2{font-size:27px;line-height:1.5;margin:0 0 16px;color:#2c353e;font-weight:500;letter-spacing:.04em}.visitor-gallery-copy p{font-size:14px;line-height:1.95;color:#6f7a85;max-width:27em;margin:0 0 25px}.visitor-gallery-copy>small{display:flex;align-items:center;gap:6px;font-size:10px;color:#9299a1;margin-top:15px}.visitor-gallery-controls{display:flex;align-items:center;gap:18px}.visitor-gallery-dots{display:flex;align-items:center;gap:8px}.visitor-gallery-dots button{display:block;width:9px;height:9px;border-radius:9px;border:0;background:#c9cdd2;padding:0;position:relative;transition:width .2s,background .2s}.visitor-gallery-dots button:before{content:'';position:absolute;inset:-8px -3px}.visitor-gallery-dots button.active{width:27px;background:#a42a36}.visitor-gallery-toggle{display:grid;place-items:center;width:29px;height:29px;border:1px solid #dce0e5;border-radius:50%;background:#fff;color:#7b858e;padding:0}.visitor-gallery-picture{position:relative;margin:0;min-width:0;overflow:hidden;background:#dce2e2;min-height:320px;height:100%}.visitor-gallery-picture>img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}.visitor-gallery-shade{position:absolute;inset:0;background:linear-gradient(transparent 65%,#172522a8)}.visitor-gallery-picture figcaption{position:absolute;left:24px;bottom:20px;right:108px;color:#fff;display:flex;align-items:center;gap:20px;font-size:13px;line-height:1.8;text-shadow:0 1px 3px #0003}.visitor-gallery-picture figcaption small{font-size:11px;color:#e9eeee;white-space:nowrap;margin-left:auto}.visitor-gallery-arrows{position:absolute;display:flex;gap:7px;right:19px;bottom:19px}.visitor-gallery-arrows button{display:grid;place-items:center;width:32px;height:32px;border:1px solid #ffffff70;border-radius:4px;background:#ffffffed;color:#485760;padding:0}.visitor-gallery-arrows button:hover{background:#fff;color:#a12632}.visitor-gallery button:focus-visible{outline:2px solid #a22b37;outline-offset:4px}.visitor-gallery-picture button:focus-visible{outline-color:white}
.visitor-gallery-frame-enter-active,.visitor-gallery-frame-leave-active{transition:opacity .55s ease,transform .75s cubic-bezier(.2,.75,.2,1)}.visitor-gallery-frame-enter-from{opacity:0;transform:scale(1.035) translateX(12px)}.visitor-gallery-frame-leave-to{opacity:0;transform:scale(1.015) translateX(-10px)}
@media(min-width:1200px){.visitor-gallery{min-height:335px}.visitor-gallery-picture{min-height:335px}.visitor-gallery-copy{padding:36px 44px}}
@media(max-width:760px){.visitor-gallery{grid-template-columns:1fr}.visitor-gallery-copy{padding:25px}.visitor-gallery-copy h2{font-size:23px}.visitor-gallery-copy p{margin-bottom:18px}.visitor-gallery-picture{height:240px;min-height:240px}.visitor-gallery-picture figcaption{left:16px;bottom:15px;right:95px;font-size:12px;gap:10px}.visitor-gallery-arrows{bottom:14px;right:14px}}
@media(prefers-reduced-motion:reduce){.visitor-gallery-dots button,.visitor-gallery-frame-enter-active,.visitor-gallery-frame-leave-active{transition:none}}
</style>
