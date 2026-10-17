<script setup lang="ts">
import {fieldLabel,displayValue} from '../api/contract'
defineProps<{value:any;depth?:number;omitKeys?:string[]}>()
const hidden=new Set(['confirmationToken','confirmation_token','requestKey','request_key','snapshot_id','fingerprint','password_hash','payload_hash'])
</script>
<template>
 <span v-if="value===null||typeof value!=='object'">{{displayValue(value)}}</span>
 <div v-else-if="Array.isArray(value)" class="record-array"><p v-if="!value.length" class="muted">暂无记录</p><article v-for="(v,i) in value" :key="i"><RecordView :value="v" :depth="(depth||0)+1" :omit-keys="omitKeys"/></article></div>
 <dl v-else class="record-fields"><template v-for="(v,k) in value" :key="k"><template v-if="!hidden.has(String(k))&&!omitKeys?.includes(String(k))"><dt>{{fieldLabel(String(k))}}</dt><dd><RecordView :value="v" :depth="(depth||0)+1" :omit-keys="omitKeys"/></dd></template></template></dl>
</template>
