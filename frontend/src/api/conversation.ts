import type { AxiosResponse } from 'axios'
import request from './index'
import type { ApiResponse } from '@/types/api'
import type {
  ConversationQueryParams,
  ConversationContentQuery,
  CostBudgetRequest,
  ConversationListResponse,
  ConversationDetail,
  UsageOverviewResponse,
  CostBudgetResponse
} from '@/types/conversation'

/**
 * AI 会话记录 API
 * @description AI 会话记录查询、Token 统计、费用预算
 */

const BASE_URL = '/ai'

/**
 * 查询会话记录列表
 */
export function getConversations(
  params: ConversationQueryParams
): Promise<AxiosResponse<ApiResponse<ConversationListResponse>>> {
  return request.get(`${BASE_URL}/conversations`, { params })
}

/**
 * 获取会话记录详情
 */
export function getConversationDetail(
  id: number
): Promise<AxiosResponse<ApiResponse<ConversationDetail>>> {
  return request.get(`${BASE_URL}/conversations/${id}`)
}

/**
 * 搜索会话内容
 */
export function searchConversations(
  data: ConversationContentQuery
): Promise<AxiosResponse<ApiResponse<ConversationListResponse>>> {
  return request.post(`${BASE_URL}/conversations/search`, data)
}

/**
 * 获取使用量概览
 */
export function getUsageOverview(
  startDate?: string,
  endDate?: string
): Promise<AxiosResponse<ApiResponse<UsageOverviewResponse>>> {
  const params: Record<string, string> = {}
  if (startDate) params.start_date = startDate
  if (endDate) params.end_date = endDate
  return request.get(`${BASE_URL}/usage/overview`, { params })
}

/**
 * 费用预算分析
 */
export function getCostBudget(
  data: CostBudgetRequest
): Promise<AxiosResponse<ApiResponse<CostBudgetResponse>>> {
  return request.post(`${BASE_URL}/usage/budget`, data)
}
