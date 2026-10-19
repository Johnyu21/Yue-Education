<script setup lang="ts">
import {ref} from 'vue'
import {api,upload,errorText} from '../api/client'
import {uuid} from '../api/uuid'
import RecordView from './RecordView.vue'
const emit=defineEmits(['changed'])
const opened=ref(false),objectKey=ref(''),filename=ref(''),mapping=ref<any>({name:'姓名',mobile:'手机号'}),sheet=ref(''),preview=ref<any>(null),error=ref(''),busy=ref(false),confirmed=ref(false),key=ref(uuid()),receipt=ref<any>(null)
async function select(e:Event){const f=(e.target as HTMLInputElement).files?.[0];if(!f)return;busy.value=true;error.value='';try{const result=await upload(f);objectKey.value=result.objectKey;filename.value=f.name;preview.value=null;receipt.value=null;key.value=uuid()}catch(e){error.value=errorText(e)}finally{busy.value=false}}
function changed(){preview.value=null;confirmed.value=false;key.value=uuid()}
function body(){return {object_key:objectKey.value,mapping:mapping.value,sheet_name:sheet.value||null,request_key:key.value}}
async function inspect(){busy.value=true;error.value='';try{preview.value=await api.post('/employees/lead-imports/preview',body());confirmed.value=false}catch(e){error.value=errorText(e)}finally{busy.value=false}}
async function apply(){if(!preview.value||!confirmed.value)return;busy.value=true;error.value='';try{receipt.value=await api.post('/employees/lead-imports/apply',{...body(),fingerprint:preview.value.fingerprint,confirmed:true});preview.value=null;emit('changed')}catch(e){error.value=errorText(e)}finally{busy.value=false}}
</script>
<template><section class="paper import-panel"><div class="panel-title"><h3>客户资料批量导入</h3><button class="text-link" @click="opened=!opened">{{opened?'收起':'上传 Excel 资料'}}</button></div><template v-if="opened"><p class="muted">每批最多200行。先上传并预检，核对全部行后再确认导入。</p><label>客户 Excel 文件<input type="file" accept=".xlsx" @change="select"></label><p>{{filename}}</p><div class="form-columns"><label>姓名对应的表头<input v-model="mapping.name" @input="changed"></label><label>手机号对应的表头<input v-model="mapping.mobile" @input="changed"></label><label>工作表（选填）<input v-model="sheet" @input="changed"></label></div><button class="btn outline" :disabled="busy||!objectKey" @click="inspect">预检资料</button><template v-if="preview"><RecordView :value="preview"/><label class="check-label"><input v-model="confirmed" type="checkbox">我已核对预检结果，确认整批导入</label><button class="btn primary" :disabled="busy||!confirmed||!preview.fingerprint||!preview.canApply" @click="apply">确认导入</button></template><p v-if="error" class="error-text" role="alert">{{error}}</p><RecordView v-if="receipt" :value="receipt"/></template></section></template>
