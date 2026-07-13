/**
 * AI 会话记录类型定义
 */

/**
 * 会话状态
 */
export type ConversationStatus = 'success' | 'failed' | 'timeout'

/**
 * 搜索字段类型
 */
export type SearchField = 'input' | 'output' | 'both'

/**
 * 会话记录列表项
 */
export interface ConversationLogItem {
  id: number
  task_id: string | null
  session_id: string | null
  agent_name: string | null
  model_name: string
  provider: string
  input_tokens: number
  output_tokens: number
  total_tokens: number
  cost_usd: number
  cost_cny: number
  latency_ms: number | null
  status: ConversationStatus
  created_at: string
}

/**
 * 会话记录详情（继承列表项，增加内容字段）
 */
export interface ConversationDetail extends ConversationLogItem {
  input_content: string | null
  output_content: string | null
  error_message: string | null
  extra_data: Record<string, unknown> | null
}

/**
 * 会话列表响应
 */
export interface ConversationListResponse {
  items: ConversationLogItem[]
  total: number
  page: number
  page_size: number
}

/**
 * 会话查询参数
 */
export interface ConversationQueryParams {
  agent_name?: string
  model_name?: string
  provider?: string
  task_id?: string
  session_id?: string
  status?: ConversationStatus
  start_date?: string
  end_date?: string
  page?: number
  page_size?: number
}

/**
 * 会话内容搜索请求
 */
export interface ConversationContentQuery {
  keyword: string
  search_field?: SearchField
  page?: number
  page_size?: number
}

/**
 * Token 使用统计
 */
export interface TokenUsageStats {
  total_input_tokens: number
  total_output_tokens: number
  total_tokens: number
  total_cost_usd: number
  total_cost_cny: number
  avg_latency_ms: number | null
  success_count: number
  failed_count: number
  total_count: number
}

/**
 * 模型使用量分解
 */
export interface ModelUsageBreakdown {
  model_name: string
  provider: string
  call_count: number
  total_tokens: number
  total_cost_usd: number
  total_cost_cny: number
}

/**
 * Agent 使用量分解
 */
export interface AgentUsageBreakdown {
  agent_name: string
  call_count: number
  total_tokens: number
  total_cost_usd: number
  total_cost_cny: number
}

/**
 * 使用量概览响应
 */
export interface UsageOverviewResponse {
  stats: TokenUsageStats
  by_model: ModelUsageBreakdown[]
  by_agent: AgentUsageBreakdown[]
}

/**
 * 费用预算请求
 */
export interface CostBudgetRequest {
  daily_budget_cny?: number
  monthly_budget_cny?: number
}

/**
 * 费用预算响应
 */
export interface CostBudgetResponse {
  today_cost_cny: number
  today_cost_usd: number
  today_token_count: number
  today_call_count: number
  daily_budget_cny: number
  daily_remaining_cny: number
  daily_usage_percent: number
  month_cost_cny: number
  monthly_budget_cny: number
  monthly_remaining_cny: number
  monthly_usage_percent: number
  projected_month_cost_cny: number
}

/**
 * 会话状态标签映射
 */
export const CONVERSATION_STATUS_LABELS: Record<ConversationStatus, string> = {
  success: '成功',
  failed: '失败',
  timeout: '超时'
}

/**
 * 会话状态颜色映射
 */
export const CONVERSATION_STATUS_COLORS: Record<ConversationStatus, string> = {
  success: 'success',
  failed: 'danger',
  timeout: 'warning'
}
