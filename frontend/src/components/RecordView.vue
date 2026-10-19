<script setup lang="ts">
import {fieldLabel,displayValue} from '../api/contract'
const props=defineProps<{value:any;depth?:number;omitKeys?:string[];includeKeys?:string[];hideEmpty?:boolean}>()
const hidden=new Set(['confirmationToken','confirmation_token','requestKey','request_key','snapshot_id','fingerprint','password_hash','payload_hash','id','version','versionNo','userId','studentProfileId','enrollmentId','assigneeUserId','recordedByUserId','createdByUserId','followUpUserId','reviewedByUserId','verifiedByUserId','leadId','courseProjectId','eventId','deptId','classId','psychProfileId','replacesProfileId','scheduleId','cancelToken','tokenVersion','mustChangePassword','temporaryPasswordExpiresAt','sourceEventKey','businessEventKey','relatedType','relatedId','assessmentRequestId','previousId','convertedLeadId','ownerUserId','submittedByUserId','organizerUserId','hostDepartmentId','defaultDeptId','headTeacherId','headUserId','parentId','advisorUserId','consentVersion','consentAt','psychWithdrawnAt','psychConsentAt','psychConsentStatus','dataSource','contentHash','expectedVersion','expectedSequence','expectedStudentVersion','latestSequence'])
const empty=(v:any)=>v==null||v===''
function visible(k:string){if((props.depth||0)===0&&props.includeKeys?.length)return props.includeKeys.includes(k);return !hidden.has(k)&&!props.omitKeys?.includes(k)}
</script>
<template>
 <span v-if="value===null||typeof value!=='object'">{{displayValue(value)}}</span>
 <div v-else-if="Array.isArray(value)" class="record-array"><p v-if="!value.length" class="muted">暂无记录</p><article v-for="(v,i) in value" :key="i"><RecordView :value="v" :depth="(depth||0)+1" :omit-keys="omitKeys" :include-keys="includeKeys" :hide-empty="hideEmpty"/></article></div>
 <dl v-else class="record-fields"><template v-for="(v,k) in value" :key="k"><template v-if="visible(String(k))&&!(hideEmpty&&empty(v))"><dt>{{fieldLabel(String(k))}}</dt><dd><RecordView :value="v" :depth="(depth||0)+1" :omit-keys="omitKeys" :include-keys="includeKeys" :hide-empty="hideEmpty"/></dd></template></template></dl>
</template>
