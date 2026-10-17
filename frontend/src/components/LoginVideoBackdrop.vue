<script setup lang="ts">
import {onMounted,onBeforeUnmount,ref} from 'vue'
import {Pause,Play} from 'lucide-vue-next'
const video=ref<HTMLVideoElement|null>(null),paused=ref(false),failed=ref(false),blocked=ref(false)
let motion:MediaQueryList|undefined
async function play(){if(!video.value||paused.value||document.hidden||failed.value)return;video.value.muted=true;try{await video.value.play();blocked.value=false}catch{blocked.value=true}}
function toggle(){if(paused.value||blocked.value){paused.value=false;void play()}else{paused.value=true;video.value?.pause()}}
function visibility(){if(document.hidden)video.value?.pause();else void play()}
function preference(){paused.value=!!motion?.matches;if(paused.value)video.value?.pause();else void play()}
onMounted(()=>{motion=window.matchMedia('(prefers-reduced-motion: reduce)');preference();motion.addEventListener('change',preference);document.addEventListener('visibilitychange',visibility)})
onBeforeUnmount(()=>{document.removeEventListener('visibilitychange',visibility);motion?.removeEventListener('change',preference);video.value?.pause()})
</script>
<template><video v-show="!failed" ref="video" class="login-background-video" src="/visitor-video/intro-video.mp4" muted loop playsinline preload="metadata" aria-hidden="true" tabindex="-1" @loadeddata="play" @error="failed=true"/><div class="login-video-shade" aria-hidden="true"></div><button v-if="!failed" type="button" class="login-video-toggle" :aria-label="paused||blocked?'播放登录页背景视频':'暂停登录页背景视频'" :aria-pressed="paused" @click="toggle"><Play v-if="paused||blocked" :size="14"/><Pause v-else :size="14"/><span>{{paused||blocked?'播放影像':'暂停影像'}}</span></button></template>
<style scoped>
.login-background-video{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;filter:blur(5px) saturate(.72);transform:scale(1.08);opacity:.88;z-index:0;pointer-events:none}.login-video-shade{position:absolute;inset:0;background:linear-gradient(130deg,#4e1e29da,#672735b8 60%,#241a2dcc);z-index:1;pointer-events:none}.login-video-toggle{position:absolute;right:22px;bottom:20px;z-index:4;display:flex;align-items:center;gap:6px;font-size:10px;color:#f6e1e4;border:1px solid #ffffff40;background:#fff1;padding:7px 10px;border-radius:5px;cursor:pointer}.login-video-toggle:hover{background:#fff2}.login-video-toggle:focus-visible{outline:2px solid white;outline-offset:3px}
</style>
