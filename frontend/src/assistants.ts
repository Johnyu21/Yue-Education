import {reportsApi,getStudents} from './api'
export const employeeAssistantApi={load:()=>reportsApi.get('/chat'),send:(data:any)=>reportsApi.post('/chat/messages',data),students:getStudents}
export const reportAssistantApi={generate:(request:any)=>reportsApi.post('/reports/preview',request)}
