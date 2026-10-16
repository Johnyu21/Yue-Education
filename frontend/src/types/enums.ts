/**
 * 枚举中英对照（前端映射表）
 *
 * ⚠️ 后端存英文，前端显示中文。本表来自 docs/M1-01-公共契约冻结.md
 *    后端枚举若有变更，同步更新这里。
 */
export const LEAD_STATUS: Record<string, string> = {
  NEW: '新增意向', FOLLOWING: '跟进中', SIGNED: '已签约', LOST: '已流失',
}
export const LEAD_SOURCE: Record<string, string> = {
  WEBSITE: '网站', CHAT: '客服对话', EVENT: '活动', MANUAL: '手工录入',
}
export const EMPLOYEE_ROLE: Record<string, string> = {
  NEWCOMER: '新人', ADVISOR: '顾问', SENIOR_ADVISOR: '高级顾问', ADMIN: '管理员',
}
export const SERVICE_STATUS: Record<string, string> = {
  PENDING: '待审批', APPROVED: '已通过', REJECTED: '已驳回', CANCELLED: '已取消',
}
export const TICKET_STATUS: Record<string, string> = {
  PENDING: '待处理', PROCESSING: '处理中', RESOLVED: '已解决', CLOSED: '已关闭',
}
export const RISK_LEVEL: Record<string, string> = {
  HIGH: '高', MEDIUM: '中', LOW: '低',
}
export const EMOTION_STATE: Record<string, string> = {
  HEALTHY: '健康', NEGATIVE: '消极', VERY_NEGATIVE: '极度消极', UNKNOWN: '未观测',
}

/** 通用：查表转中文，查不到就原样返回 */
export function label(map: Record<string, string>, key?: string): string {
  return key ? (map[key] ?? key) : ''
}
