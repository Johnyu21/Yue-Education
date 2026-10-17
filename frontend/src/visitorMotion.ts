import {nextTick,onBeforeUnmount,onMounted,ref,watch,type Ref} from 'vue'

const targets=[
 '.visitor-hero-inner>div','.visitor-gallery-copy','.visitor-gallery-picture',
 '.visitor-section-title','.visitor-project-card','.visitor-decision>h2','.visitor-decision>div>article',
 '.visitor-policy-card','.visitor-detail-main>.visitor-paper','.visitor-consult>.visitor-paper',
 '.visitor-policy-document>section','.visitor-main>.visitor-paper','.visitor-flow>li',
 '.visitor-nav','.visitor-section-nav','.public-live-detail',
].join(',')

/** Progressive enhancement: content remains visible if motion APIs are unavailable. */
export function useVisitorMotion(root:Ref<HTMLElement|null>,route:()=>string){
 const progress=ref(0)
 let intersection:IntersectionObserver|undefined,mutations:MutationObserver|undefined,resize:ResizeObserver|undefined
 let media:MediaQueryList|undefined,frame=0,generation=0,index=0
 const seen=new Set<HTMLElement>(),timers=new Set<ReturnType<typeof setTimeout>>()
 const ripples=new Set<HTMLElement>()
 function updateProgress(){frame=0;const length=document.documentElement.scrollHeight-window.innerHeight;progress.value=length>0?Math.min(1,Math.max(0,window.scrollY/length)):0}
 function scheduleProgress(){if(!frame)frame=requestAnimationFrame(updateProgress)}
 function show(element:HTMLElement){element.classList.add('visitor-in-view');intersection?.unobserve(element)}
 function register(){
  if(!root.value||!intersection)return
  for(const element of root.value.querySelectorAll<HTMLElement>(targets)){
   if(seen.has(element))continue
   seen.add(element)
   const right=element.matches('.visitor-gallery-picture,.visitor-hero-art')||(!element.matches('.visitor-gallery-copy')&&index%2===1)
   element.dataset.visitorDirection=right?'right':'left'
   element.style.setProperty('--visitor-reveal-delay',Math.min(index%3,2)*65+'ms')
   element.classList.add('visitor-reveal');element.classList.remove('visitor-in-view')
   intersection.observe(element);index++
  }
  scheduleProgress()
 }
 function clear(){intersection?.disconnect();mutations?.disconnect();resize?.disconnect();intersection=undefined;for(const element of seen){element.classList.remove('visitor-reveal','visitor-in-view');element.style.removeProperty('--visitor-reveal-delay');delete element.dataset.visitorDirection}seen.clear();index=0}
 async function setup(){const ticket=++generation;await nextTick();if(ticket!==generation)return;clear();updateProgress();if(!root.value||media?.matches||typeof IntersectionObserver==='undefined')return
  intersection=new IntersectionObserver(entries=>{for(const entry of entries)if(entry.isIntersecting)show(entry.target as HTMLElement)},{threshold:.06,rootMargin:'0px 0px -24px 0px'})
  register()
  mutations=new MutationObserver(records=>{if(records.some(r=>r.type==='childList'))register()});mutations.observe(root.value,{childList:true,subtree:true})
  if(typeof ResizeObserver!=='undefined'){resize=new ResizeObserver(scheduleProgress);resize.observe(root.value)}
 }
 function click(event:MouseEvent){
  if(media?.matches||!(event.target instanceof Element))return
  const button=event.target.closest<HTMLElement>('button,a,summary')
  if(!button||!root.value?.contains(button)||button.matches(':disabled,[aria-disabled=true]')||!button.getClientRects().length)return
  const rect=button.getBoundingClientRect(),ripple=document.createElement('span'),size=Math.max(rect.width,rect.height)*2
  const x=event.detail===0?rect.width/2:event.clientX-rect.left,y=event.detail===0?rect.height/2:event.clientY-rect.top
  ripple.className='visitor-click-wave';ripple.setAttribute('aria-hidden','true');ripple.style.cssText='width:'+size+'px;height:'+size+'px;left:'+x+'px;top:'+y+'px'
  button.classList.add('visitor-click-target');button.append(ripple);ripples.add(ripple)
  const timer=setTimeout(()=>{ripple.remove();ripples.delete(ripple);timers.delete(timer)},650);timers.add(timer)
 }
 function focus(event:FocusEvent){if(event.target instanceof Element){let node=event.target.closest<HTMLElement>('.visitor-reveal');while(node&&root.value?.contains(node)){show(node);node=node.parentElement?.closest<HTMLElement>('.visitor-reveal')||null}}}
 watch(route,()=>{void setup()})
 onMounted(()=>{media=window.matchMedia('(prefers-reduced-motion: reduce)');media.addEventListener('change',setup);root.value?.addEventListener('click',click);root.value?.addEventListener('focusin',focus);window.addEventListener('scroll',scheduleProgress,{passive:true});window.addEventListener('resize',scheduleProgress);void setup()})
 onBeforeUnmount(()=>{generation++;clear();if(frame)cancelAnimationFrame(frame);media?.removeEventListener('change',setup);root.value?.removeEventListener('click',click);root.value?.removeEventListener('focusin',focus);window.removeEventListener('scroll',scheduleProgress);window.removeEventListener('resize',scheduleProgress);for(const timer of timers)clearTimeout(timer);for(const ripple of ripples)ripple.remove()})
 return {progress}
}
