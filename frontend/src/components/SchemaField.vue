<script setup lang="ts">
import {computed,ref,useId} from 'vue'
import {resolveSchema,fieldLabel,displayValue} from '../api/contract'
import {upload,errorText,download} from '../api/client'
const props=defineProps<{schema:any;modelValue:any;name:string;required?:boolean;clearable?:boolean;choices?:Record<string,any[]>}>()
const emit=defineEmits(['update:modelValue'])
const inputId='business-field-'+useId()
const s=computed(()=>{const v=resolveSchema(props.schema);if(!v.enum&&typeof v.pattern==='string'&&/^\^\([A-Z_|]+\)\$/.test(v.pattern))return {...v,enum:v.pattern.slice(2,-2).split('|')};return v}),uploading=ref(false),error=ref('')
const isFile=computed(()=>['object_key','resume_object_key'].includes(props.name))
const choiceKey=computed(()=>{if(!/(?:_id|_ids)$/.test(props.name))return '';return /student/.test(props.name)?'students':/project/.test(props.name)?'projects':/class_id/.test(props.name)?'classes':/dept|department/.test(props.name)?'departments':/user_id|teacher_id/.test(props.name)?'users':''})
const options=computed(()=>props.choices?.[choiceKey.value]||[])
const isArray=computed(()=>s.value.type==='array')
function set(v:any){emit('update:modelValue',v)}
function input(e:Event){const el=e.target as HTMLInputElement;if(s.value.type==='integer'&&!choiceKey.value)set(el.value===''?undefined:Number(el.value));else if(s.value.format==='date-time')set(el.value?new Date(el.value).toISOString():undefined);else set(el.value||undefined)}
function dateTime(v:any){if(!v)return '';const d=new Date(v);if(Number.isNaN(d.getTime()))return '';const local=new Date(d.getTime()-d.getTimezoneOffset()*60000);return local.toISOString().slice(0,16)}
function setChild(k:string,v:any){set({...props.modelValue,[k]:v})}
function changeItem(i:number,v:any){const a=[...(props.modelValue||[])];a[i]=v;set(a)}
async function file(e:Event){const f=(e.target as HTMLInputElement).files?.[0];if(!f)return;uploading.value=true;error.value='';try{const r=await upload(f);set(r.objectKey||r.object_key)}catch(e){error.value=errorText(e)}finally{uploading.value=false}}
const jsonText=ref('')
function jsonInput(e:Event){jsonText.value=(e.target as HTMLTextAreaElement).value;try{set(JSON.parse(jsonText.value));error.value=''}catch{error.value='请检查资料格式，内容须为有效的 JSON 对象'}}
</script>
<template>
 <div class="schema-field" :class="{'wide-field':s.type==='object'||s.type==='array'||s.maxLength>500}">
  <label class="field-title" :for="inputId">{{fieldLabel(name)}}<b v-if="required"> *</b></label>
  <template v-if="s.type==='boolean'"><label class="check-label"><input :id="inputId" type="checkbox" :checked="!!modelValue" @change="set(($event.target as HTMLInputElement).checked)">{{fieldLabel(name)}}</label></template>
  <template v-else-if="s.const!==undefined"><input :id="inputId" :value="displayValue(s.const)" readonly></template>
  <template v-else-if="s.enum"><select :id="inputId" :value="modelValue??''" :required="required" @change="input"><option value="">请选择</option><option v-for="v in s.enum" :key="v" :value="v">{{displayValue(v)}}</option></select></template>
  <template v-else-if="isFile"><input :id="inputId" type="file" accept=".pdf,.doc,.docx,.xls,.xlsx,.txt,.png,.jpg,.jpeg" :disabled="uploading" @change="file"><small>{{uploading?'正在上传…':modelValue?'附件已上传':'支持规定格式，最大10MB'}}</small><button v-if="modelValue" type="button" class="text-link" @click="download('/files/'+encodeURIComponent(modelValue),'附件')">下载已上传附件</button></template>
  <template v-else-if="isArray"><div class="array-fields"><div v-for="(v,i) in modelValue||[]" :key="i" class="array-field-row"><SchemaField :schema="s.items" :model-value="v" :name="name.replace(/_ids$/,'_id')" :choices="choices" @update:model-value="changeItem(i,$event)"/><button type="button" class="text-link" @click="set(modelValue.filter((_:any,j:number)=>i!==j))">移除</button></div><button type="button" class="text-link" @click="set([...(modelValue||[]),resolveSchema(s.items).type==='object'?{}:''])">＋ 添加{{fieldLabel(name)}}</button></div></template>
  <template v-else-if="s.type==='object'&&s.properties"><fieldset class="nested-fields"><SchemaField v-for="(v,k) in s.properties" :key="k" :schema="v" :name="String(k)" :required="s.required?.includes(k)" :model-value="modelValue?.[k]" :choices="choices" @update:model-value="setChild(String(k),$event)"/></fieldset></template>
  <template v-else-if="s.type==='object'"><textarea :id="inputId" :value="jsonText||(modelValue?JSON.stringify(modelValue,null,2):'')" rows="5" placeholder="按业务规则填写结构化资料" @input="jsonInput"></textarea></template>
  <template v-else-if="options.length"><select :id="inputId" :value="modelValue??''" :required="required" @change="input"><option value="">请选择{{fieldLabel(name)}}</option><option v-for="o in options" :key="o.id" :value="o.id">{{o.realName||o.name||o.title||o.code}} · {{o.id}}</option></select></template>
  <template v-else-if="s.maxLength>500||['content','description','note','reason','resolution','detail','summary'].includes(name)"><textarea :id="inputId" :value="modelValue" :required="required" :minlength="s.minLength" :maxlength="s.maxLength" rows="3" @input="input"></textarea></template>
  <template v-else><input :id="inputId" :type="s.format==='date-time'?'datetime-local':s.format==='date'?'date':name.includes('password')?'password':s.type==='integer'&&!choiceKey?'number':name==='mobile'?'tel':'text'" :value="s.format==='date-time'?dateTime(modelValue):modelValue" :required="required" :minlength="s.minLength" :maxlength="s.maxLength" :min="s.minimum??(s.exclusiveMinimum!==undefined?s.exclusiveMinimum+1:undefined)" :max="s.maximum" @input="input"></template>
  <label v-if="s.nullable&&!required&&clearable" class="clear-option"><input type="checkbox" :checked="modelValue===null" @change="set(($event.target as HTMLInputElement).checked?null:undefined)">明确清空此项</label>
  <p v-if="error" class="error-text">{{error}}</p>
 </div>
</template>
