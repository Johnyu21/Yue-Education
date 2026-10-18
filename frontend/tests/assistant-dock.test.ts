import {beforeEach, expect, it, vi} from 'vitest'
import {flushPromises, mount} from '@vue/test-utils'
import {createMemoryHistory, createRouter} from 'vue-router'
import http from '../src/api/client'
import AssistantDock from '../src/components/AssistantDock.vue'

beforeEach(()=>{
 localStorage.clear()
 vi.restoreAllMocks()
 Object.defineProperty(Element.prototype,'scrollTo',{configurable:true,value:vi.fn()})
})

function response(data:any,config:any){return {data:{code:'OK',message:'成功',data,request_id:'synthetic'},status:200,statusText:'OK',headers:{},config}}
async function dock(){
 const router=createRouter({history:createMemoryHistory(),routes:[{path:'/:pathMatch(.*)*',component:{template:'<div />'}}]})
 await router.push('/app/daily')
 await router.isReady()
 const wrapper=mount(AssistantDock,{props:{mode:'employee',user:{id:'71'}},global:{plugins:[router]}})
 await wrapper.find('button[aria-label="打开企业员工助手"]').trigger('click')
 return wrapper
}
async function send(wrapper:any,text:string){
 await wrapper.find('textarea').setValue(text)
 await wrapper.find('form').trigger('submit')
 await flushPromises()
}

it('员工助手日报原文转交给日报页面，不因缺少content字段丢失',async()=>{
 http.defaults.adapter=async config=>response({answer:'请核对日报',messageId:'synthetic',proposal:{operation:'DAILY_DRAFT',preview:{draft:{original_text:'今天回访客户2次'}}}},config)
 const wrapper=await dock()
 await send(wrapper,'帮我整理日报')
 await wrapper.find('.proposal-card button').trigger('click')
 expect(wrapper.emitted('draft')?.[0]).toEqual([{original_text:'今天回访客户2次'}])
 wrapper.unmount()
})

it('继续修改业务请求后旧确认卡不可点击',async()=>{
 let count=0
 const requests:any[]=[]
 http.defaults.adapter=async config=>{
  requests.push(config)
  return response(count++===0?{answer:'请确认',messageId:'one',proposal:{operation:'CREATE_LEAD',requestKey:'synthetic',confirmationToken:'synthetic',preview:{name:'合成客户',mobile:'13912345678'}}}:{answer:'请补充新信息',messageId:'two'},config)
 }
 const wrapper=await dock()
 await send(wrapper,'新增客户')
 expect(wrapper.text()).toContain('已核对，确认办理')
 await send(wrapper,'手机号需要更正')
 expect(wrapper.text()).toContain('草稿已更新，请使用最新确认卡')
 expect(wrapper.text()).not.toContain('已核对，确认办理')
 expect(requests).toHaveLength(2)
 wrapper.unmount()
})

it('确认成功后的新请求使用新会话，避免复用已提交草稿',async()=>{
 const conversations:string[]=[]
 http.defaults.adapter=async config=>{
  const body=JSON.parse(config.data)
  if(config.url?.includes('/assistants/')){
   conversations.push(body.conversation_id)
   return response(conversations.length===1?{answer:'请确认',messageId:'one',proposal:{operation:'CREATE_LEAD',requestKey:crypto.randomUUID(),confirmationToken:'synthetic',preview:{name:'合成客户',mobile:'13912345678'}}}:{answer:'新的业务',messageId:'two'},config)
  }
  return response({id:'synthetic-lead'},config)
 }
 const wrapper=await dock()
 await send(wrapper,'新增合成客户')
 await wrapper.find('.proposal-card .primary').trigger('click')
 await flushPromises()
 expect(wrapper.text()).toContain('已确认提交')
 await send(wrapper,'再办一件业务')
 expect(conversations).toHaveLength(2)
 expect(conversations[1]).not.toBe(conversations[0])
 wrapper.unmount()
})
