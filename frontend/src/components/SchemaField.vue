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
const CHANGE_FIELDS=[{key:'gender',label:'性别'},{key:'city',label:'所在城市'},{key:'education',label:'学历'},{key:'date_of_birth',label:'出生日期',date:true},{key:'real_name',label:'姓名'},{key:'mobile',label:'联系电话'}]
const isChangeRequest=computed(()=>props.name==='change_request')
function crEnabled(key:string){return props.modelValue?.new_values?.[key]!==undefined}
function crToggle(key:string){const cur=props.modelValue||{};const oldv={...(cur.old_values||{})},newv={...(cur.new_values||{})};if(newv[key]!==undefined){delete oldv[key];delete newv[key]}else{oldv[key]='';newv[key]=''};set({old_values:oldv,new_values:newv})}
function crSet(side:string,key:string,v:string){const cur=props.modelValue||{};const obj={...(cur[side]||{})};obj[key]=v;set({...cur,[side]:obj})}
</script>
<template>
 <div class="schema-field" :class="{'wide-field':s.type==='object'||s.type==='array'||s.maxLength>500}">
  <label class="field-title" :for="inputId">{{fieldLabel(name)}}<b v-if="required"> *</b></label>
  <template v-if="s.type==='boolean'"><label class="check-label"><input :id="inputId" type="checkbox" :checked="!!modelValue" @change="set(($event.target as HTMLInputElement).checked)">{{fieldLabel(name)}}</label></template>
  <template v-else-if="s.const!==undefined"><input :id="inputId" :value="displayValue(s.const)" readonly></template>
  <template v-else-if="s.enum"><select :id="inputId" :value="modelValue??''" :required="required" @change="input"><option value="">请选择</option><option v-for="v in s.enum" :key="v" :value="v">{{displayValue(v)}}</option></select></template>
  <template v-else-if="isFile"><input :id="inputId" type="file" accept=".pdf,.doc,.docx,.xls,.xlsx,.txt,.png,.jpg,.jpeg" :disabled="uploading" @change="file"><small>{{uploading?'正在上传…':modelValue?'附件已上传':'支持规定格式，最大10MB'}}</small><button v-if="modelValue" type="button" class="text-link" @click="download('/files/'+encodeURIComponent(modelValue),'附件')">下载已上传附件</button></template>
  <template v-else-if="isArray"><div class="array-fields"><div v-for="(v,i) in modelValue||[]" :key="i" class="array-field-row"><SchemaField :schema="s.items" :model-value="v" :name="name.replace(/_ids$/,'_id')" :choices="choices" @update:model-value="changeItem(i,$event)"/><button type="button" class="text-link" @click="set(modelValue.filter((_:any,j:number)=>i!==j))">移除</button></div><button type="button" class="text-link" @click="set([...(modelValue||[]),resolveSchema(s.items).type==='object'?{}:''])">＋ 添加{{fieldLabel(name)}}</button></div></template>
  <template v-else-if="isChangeRequest"><div class="cr-editor"><p class="muted">勾选要修改的资料项，分别填写原值和新值（未勾选不提交）；姓名、电话属身份信息，提交后需老师人工核验。</p><div v-for="f in CHANGE_FIELDS" :key="f.key" class="cr-row"><label class="check-label"><input type="checkbox" :checked="crEnabled(f.key)" @change="crToggle(f.key)">{{f.label}}</label><template v-if="crEnabled(f.key)"><label class="cr-field">原值<input :type="f.date?'date':'text'" :value="modelValue?.old_values?.[f.key]" @input="crSet('old_values',f.key,($event.target as HTMLInputElement).value)"></label><label class="cr-field">新值<input :type="f.date?'date':'text'" :value="modelValue?.new_values?.[f.key]" @input="crSet('new_values',f.key,($event.target as HTMLInputElement).value)"></label></template></div></div></template>
  <template v-else-if="s.type==='object'&&s.properties"><fieldset class="nested-fields"><SchemaField v-for="(v,k) in s.properties" :key="k" :schema="v" :name="String(k)" :required="s.required?.includes(k)" :model-value="modelValue?.[k]" :choices="choices" @update:model-value="setChild(String(k),$event)"/></fieldset></template>
  <template v-else-if="s.type==='object'"><textarea :id="inputId" :value="jsonText||(modelValue?JSON.stringify(modelValue,null,2):'')" rows="5" placeholder="按业务规则填写结构化资料" @input="jsonInput"></textarea></template>
  <template v-else-if="options.length"><select :id="inputId" :value="modelValue??''" :required="required" @change="input"><option value="">请选择{{fieldLabel(name)}}</option><option v-for="o in options" :key="o.id" :value="o.id">{{o.realName||o.name||o.title||o.code}} · {{o.id}}</option></select></template>
  <template v-else-if="s.maxLength>500||['content','description','note','reason','resolution','detail','summary'].includes(name)"><textarea :id="inputId" :value="modelValue" :required="required" :minlength="s.minLength" :maxlength="s.maxLength" rows="3" @input="input"></textarea></template>
  <template v-else><input :id="inputId" :type="s.format==='date-time'?'datetime-local':s.format==='date'?'date':name.includes('password')?'password':s.type==='integer'&&!choiceKey?'number':name==='mobile'?'tel':'text'" :value="s.format==='date-time'?dateTime(modelValue):modelValue" :required="required" :minlength="s.minLength" :maxlength="s.maxLength" :min="s.minimum??(s.exclusiveMinimum!==undefined?s.exclusiveMinimum+1:undefined)" :max="s.maximum" @input="input"></template>
  <label v-if="s.nullable&&!required&&clearable" class="clear-option"><input type="checkbox" :checked="modelValue===null" @change="set(($event.target as HTMLInputElement).checked?null:undefined)">明确清空此项</label>
  <p v-if="error" class="error-text">{{error}}</p>
 </div>
</template>
<style scoped>
.cr-editor{display:flex;flex-direction:column;gap:8px;padding:10px;border:1px dashed var(--line,#d8dee6);border-radius:8px}
.cr-editor .muted{color:#68707c;font-size:12px;margin:0}
.cr-row{display:flex;align-items:center;flex-wrap:wrap;gap:12px}
.cr-field{display:inline-flex;align-items:center;gap:6px;font-size:13px}
.cr-field input{padding:6px 8px;border:1px solid var(--line,#d8dee6);border-radius:6px}
</style>
