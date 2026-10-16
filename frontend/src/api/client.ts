/**
 * 公共 HTTP 客户端（唯一的请求入口）
 *
 * ⚠️ 规范要求（02 文档）：全项目只有这一个 HTTP 客户端。
 *    处理：Bearer 令牌 / request_id / 统一错误 / 401 自动登出
 *
 * 用法：
 *   import { api } from '@/api/client'
 *   const data = await api.get('/crm/leads', { page: 1 })
 *   await api.post('/auth/login', { username, password })
 *
 * 对应后端（M1-03）：统一响应 { code, message, data, errors, request_id }
 */
import axios, { AxiosError } from 'axios'

/** 后端统一响应结构 */
export interface ApiResponse<T = any> {
  code: string
  message: string
  data: T
  errors?: { field: string, reason: string }[]
  request_id: string
}

/** 业务错误（code !== 'OK'） */
export class ApiError extends Error {
  code: string
  errors: { field: string, reason: string }[]
  requestId: string
  httpStatus: number

  constructor(msg: string, code: string, requestId: string,
              httpStatus: number, errors: { field: string, reason: string }[] = []) {
    super(msg)
    this.code = code
    this.errors = errors
    this.requestId = requestId
    this.httpStatus = httpStatus
  }
}

const TOKEN_KEY = 'yue_access_token'

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (t: string) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
}

const http = axios.create({
  baseURL: '/api/v1',
  timeout: 60000,   // AI 调用可能慢（后端预算 45 秒），给足余量
})

// ---- 请求：自动带令牌 ----
http.interceptors.request.use((config) => {
  const token = tokenStore.get()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// ---- 响应：统一处理 ----
http.interceptors.response.use(
  (resp) => resp,
  (err: AxiosError<ApiResponse>) => {
    const body = err.response?.data
    const status = err.response?.status ?? 0

    // 401：令牌失效 → 清理并回登录
    if (status === 401) {
      tokenStore.clear()
      if (location.pathname !== '/login') location.href = '/login'
      throw new ApiError('登录已过期，请重新登录', 'TOKEN_EXPIRED', '', 401)
    }

    // 其他错误：把后端的 code/message/errors/request_id 原样抛给调用方
    if (body && typeof body.code === 'string') {
      throw new ApiError(body.message, body.code, body.request_id ?? '',
                         status, body.errors ?? [])
    }

    // 网络层错误（后端没起 / 超时）
    throw new ApiError('网络异常，请稍后重试', 'NETWORK_ERROR', '', status)
  },
)

/** 请求时带上 X-Request-ID，方便和后端日志对上 */
function rid(): string {
  return `fe-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
}

/** 拆出 data（统一响应里的 data 才是业务数据） */
async function unwrap<T>(p: Promise<{ data: ApiResponse<T> }>): Promise<T> {
  const resp = await p
  return resp.data.data
}

export const api = {
  get: <T = any>(url: string, params?: any) =>
    unwrap<T>(http.get(url, { params, headers: { 'X-Request-ID': rid() } })),

  post: <T = any>(url: string, data?: any) =>
    unwrap<T>(http.post(url, data, { headers: { 'X-Request-ID': rid() } })),

  put: <T = any>(url: string, data?: any) =>
    unwrap<T>(http.put(url, data, { headers: { 'X-Request-ID': rid() } })),

  patch: <T = any>(url: string, data?: any) =>
    unwrap<T>(http.patch(url, data, { headers: { 'X-Request-ID': rid() } })),

  delete: <T = any>(url: string) =>
    unwrap<T>(http.delete(url, { headers: { 'X-Request-ID': rid() } })),
}

export default http
