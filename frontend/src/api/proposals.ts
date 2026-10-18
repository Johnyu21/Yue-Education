import {api} from './client'
export interface Proposal{operation:string;entityId?:string;preview:any;expectedVersion?:number;requestKey?:string;confirmationToken?:string;expiresAt?:string}
export function proposalRequest(p:Proposal){
 const v=p.preview||{},entity=encodeURIComponent(p.entityId||v.leadId||v.serviceId||v.ticketId||v.alertId||'')
 const system:any={request_key:p.requestKey,confirmation_token:p.confirmationToken||undefined}
 if(p.expectedVersion!=null)system.expected_version=p.expectedVersion
 let path='',data:any={}
 switch(p.operation){
 case 'CREATE_LEAD':path='/employees/leads';data={...v};break
 case 'ADD_FOLLOWUP':path='/employees/leads/'+entity+'/follow-ups';data={content:v.content,follow_up_type:'CONTACT'};if(v.nextFollowUpAtProvided)data.next_follow_up_at=v.nextFollowUpAt;break
 case 'TRANSITION_LEAD':path='/employees/leads/'+entity+'/status';data={target_status:v.targetStatus,reason:v.reason};break
 case 'DECIDE_SERVICE':path='/services/'+entity+'/decision';data={decision:v.decision,note:v.note};break
 case 'HANDLE_FEEDBACK':path='/employees/feedback-tickets/'+entity+'/handling';data={action:v.action,note:v.note,resolution:v.resolution,assignee_user_id:v.assigneeUserId??null};break
 case 'CLAIM_FEEDBACK':path='/employees/feedback-tickets/'+entity+'/claim';data={};break
 case 'PSYCH_ALERT_NOTE':path='/employees/psych-alerts/'+entity+'/actions';data={action:'NOTE',note:v.note};break
 case 'ADVANCE_APPLICATION':
  if(v.expectedSequence==null||!v.occurredAt||!Object.prototype.hasOwnProperty.call(v,'assigneeUserId'))throw new Error('确认卡资料不全，请重新向助手生成建议')
  path='/employees/application-cases/'+encodeURIComponent(v.caseNo)+'/events';data={event_kind:v.eventKind,stage:v.stage,detail:v.detail,expected_sequence:v.expectedSequence,occurred_at:v.occurredAt,assignee_user_id:v.assigneeUserId};break
 case 'SUBMIT_SERVICE':path='/services';data={...v,confirmed:true};break
 case 'SUBMIT_FEEDBACK':path='/me/feedback-tickets';data={...v,confirmed:true};break
 case 'UPGRADE_INTEREST':path='/me/upgrade-interests';data={...v,confirmed:true};break
 case 'CAPTURE_LEAD':path='/public/leads';for(const key of ['name','mobile','gender','city','education','date_of_birth','intended_project_id','study_purpose','interest_level'])if(v[key]!==undefined)data[key]=v[key];data.channel='ASSISTANT';data.confirmed=true;break
 case 'REGISTER_EVENT':path='/events/'+encodeURIComponent(v.event_id)+'/registrations';data={name:v.name,mobile:v.mobile,confirmed:true};break
 default:throw new Error('该建议需要在对应业务表单核对，不能直接提交')
 }
 return {path,data:{...data,...system}}
}
export async function confirmProposal(p:Proposal){if(p.expiresAt&&new Date(p.expiresAt).getTime()<Date.now())throw new Error('确认卡已过期，请重新生成');if(!p.requestKey)throw new Error('确认卡缺少提交凭证，请重新生成');const req=proposalRequest(p);return api.post(req.path,req.data)}
