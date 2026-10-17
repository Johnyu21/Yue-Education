<script setup lang="ts">
import {computed,ref} from 'vue'
import SchemaField from './SchemaField.vue'
import RecordView from './RecordView.vue'
import {bodySchema,operation,invoke,resolveSchema,systemFields,camel,fieldLabel} from '../api/contract'
import {errorText} from '../api/client'
const props=defineProps<{path:string;method:string;title:string;params?:Record<string,any>;record?:any;choices?:Record<string,any[]>;preset?:any;hideLoginAccount?:boolean}>()
const emit=defineEmits(['close','saved'])
const schema=computed(()=>bodySchema(props.path,props.method)),values=ref<any>({}),initial=ref<any>({}),busy=ref(false),error=ref(''),result=ref<any>(undefined),confirmed=ref(false)
const pathFields=computed(()=>(operation(props.path,props.method).parameters||[]).filter((p:any)=>p.in==='path'&&props.params?.[p.name]==null))
const paths=ref<any>({...props.params})
for(const [k,s0] of Object.entries(schema.value.properties||{})){
 if(props.hideLoginAccount&&k==='username')continue
 const s:any=resolveSchema(s0)
 let v=props.preset?.[k]
 if(v===undefined&&props.method==='PATCH')v=props.record?.[camel(k)]??props.record?.[k]
 if(v===undefined&&props.method!=='PATCH'&&s.default!==undefined)v=s.default
 if(s.const!==undefined)v=s.const
 if(k==='expected_version')v=props.record?.version??props.preset?.expected_version
 if(k==='expected_student_version')v=props.preset?.expected_student_version??props.record?.version
 if(k==='expected_sequence')v=props.record?.latestSequence??props.record?.sequenceNo??props.preset?.expected_sequence
 if(k==='request_key')v=crypto.randomUUID()
 if(v!==undefined)values.value[k]=v
}
initial.value=JSON.parse(JSON.stringify(values.value))
const fields=computed(()=>Object.entries(schema.value.properties||{}).filter(([k])=>!systemFields.has(k)&&k!=='confirmed'&&!(props.hideLoginAccount&&k==='username')).map(([k,s])=>[k,k==='action'&&props.preset?.action?{...resolveSchema(s),const:props.preset.action}:s] as [string,any]))
async function submit(){
 if(busy.value||!confirmed.value)return
 busy.value=true;error.value=''
 try{
  const body:any={}
  for(const [k,v] of Object.entries(values.value)){
   if(v===undefined||v===''&&!schema.value.required?.includes(k))continue
   if(props.method==='PATCH'&&!systemFields.has(k)&&!schema.value.required?.includes(k)&&JSON.stringify(v)===JSON.stringify(initial.value[k]))continue
   body[k]=v
  }
  for(const k of ['expected_version','expected_sequence','expected_student_version'])if(schema.value.required?.includes(k)&&body[k]===undefined)throw new Error('缺少当前记录版本，请先打开最新详情后办理')
  if('confirmed' in (schema.value.properties||{}))body.confirmed=true
  const data=await invoke(props.method,props.path,paths.value,Object.keys(schema.value.properties||{}).length?body:undefined)
  result.value=data;emit('saved',data)
 }catch(e){error.value=errorText(e)}finally{busy.value=false}
}
</script>
<template><div class="modal-shade" @click.self="$emit('close')"><section class="operation-dialog" role="dialog" aria-modal="true" :aria-label="title"><div class="panel-title"><h2>{{title}}</h2><button type="button" class="icon-btn" aria-label="关闭表单" @click="$emit('close')">×</button></div><template v-if="result!==undefined"><div class="success-callout">操作已完成</div><RecordView :value="result" :omit-keys="hideLoginAccount?['username']:[]"/><p v-if="result?.temporaryPassword" class="info-box">初始密码仅在本次显示，请妥善交给账号本人。</p><button class="btn primary" @click="$emit('close')">完成</button></template><form v-else @submit.prevent="submit"><div class="schema-grid"><SchemaField v-for="p in pathFields" :key="p.name" :name="p.name" :schema="p.schema" required :model-value="paths[p.name]" :choices="choices" @update:model-value="paths[p.name]=$event"/><SchemaField v-for="[k,s] in fields" :key="k" :name="k" :schema="s" :required="schema.required?.includes(k)" :clearable="method==='PATCH'" :model-value="values[k]" :choices="choices" @update:model-value="values[k]=$event"/></div><p v-if="!fields.length&&!pathFields.length" class="info-box">请确认对当前记录执行“{{title}}”。</p><p v-if="error" class="error-text" role="alert">{{error}}</p><label class="check-label confirmation"><input v-model="confirmed" type="checkbox">我已核对以上内容，确认{{title}}</label><div class="dialog-actions"><button type="button" class="btn outline" @click="$emit('close')">取消</button><button class="btn primary" :disabled="busy||!confirmed">{{busy?'正在提交…':'确认'+title}}</button></div></form></section></div></template>
