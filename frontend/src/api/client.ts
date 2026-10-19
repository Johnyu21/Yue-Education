import axios, { type AxiosError } from 'axios'
import {uuid} from './uuid'
export interface ApiResponse<T=unknown>{code:string;message:string;data:T;errors?:{field:string;reason:string}[];request_id:string}
export class ApiError extends Error {
 constructor(message:string,public code:string,public requestId='',public httpStatus=0,public errors:{field:string;reason:string}[]=[],public data:unknown=null){super(message);this.name='ApiError'}
}
const TOKEN_KEY='yue_access_token'
export const tokenStore={get:()=>localStorage.getItem(TOKEN_KEY),set:(v:string)=>localStorage.setItem(TOKEN_KEY,v),clear:()=>{localStorage.removeItem(TOKEN_KEY);retries.clear()}}
const http=axios.create({baseURL:import.meta.env.VITE_API_BASE_URL||'/api/v1',timeout:90000})
const retries=new Map<string,string>()
http.interceptors.request.use(c=>{const token=tokenStore.get();if(token)c.headers.Authorization='Bearer '+token;c.headers['X-Request-ID']=uuid();return c},undefined,{synchronous:true})
http.interceptors.response.use(r=>r,async(err:AxiosError<ApiResponse>)=>{
 let body:any=err.response?.data
 if(body instanceof Blob){try{body=JSON.parse(await body.text())}catch{body=null}}
 const status=err.response?.status||0
 if(status===401&&!err.config?.url?.includes('/auth/login')&&err.config?.headers?.Authorization==='Bearer '+tokenStore.get()){tokenStore.clear();window.dispatchEvent(new Event('auth-expired'))}
 throw new ApiError(body?.message||(status?'请求未完成':'无法连接服务，请检查后端是否启动'),body?.code||'NETWORK_ERROR',body?.request_id||'',status,body?.errors||[],body?.data)
})
export async function request<T=any>(method:string,url:string,body?:any,params?:any):Promise<T>{
 const r=await http.request<ApiResponse<T>>({method,url,data:body,params})
 if(r.data.code!=='OK')throw new ApiError(r.data.message,r.data.code,r.data.request_id,r.status,r.data.errors,r.data.data)
 return r.data.data
}
export const api={get:<T=any>(url:string,params?:any)=>request<T>('GET',url,undefined,params),post:<T=any>(url:string,data?:any)=>request<T>('POST',url,data),put:<T=any>(url:string,data?:any)=>request<T>('PUT',url,data),patch:<T=any>(url:string,data?:any)=>request<T>('PATCH',url,data)}
export async function writeRequest(method:string,url:string,data:any){
 const payload={...data};const fingerprint=method+url+JSON.stringify(payload)
 if(!payload.request_key){if(!retries.has(fingerprint))retries.set(fingerprint,uuid());payload.request_key=retries.get(fingerprint)}
 const result=await request(method,url,payload);retries.delete(fingerprint);return result
}
export async function download(url:string,filename:string){const r=await http.get(url,{responseType:'blob'});const link=document.createElement('a');const href=URL.createObjectURL(r.data);link.href=href;link.download=filename;link.click();setTimeout(()=>URL.revokeObjectURL(href),1000)}
export async function upload(file:File){const data=new FormData();data.append('file',file);return api.post('/files',data)}
export function errorText(e:any){return [e.message,...(e.errors||[]).map((v:any)=>v.reason)].filter(Boolean).join('；')}
export default http
