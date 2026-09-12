/**
 * 知识图谱兼容 API 封装（对应后端已 deprecated 的 graphs 端点）。
 *
 * 默认前端路径请使用 `@/api/knowledge` 的 documents/search。
 * 仅保留 Search 页兼容入口所需的 hybrid / agent 调用。
 *
 * 返回值为 `ApiResponse.data`，错误由全局拦截器统一处理并 reject。
 */
import request from './index'
import type {
  HybridSearchRequest,
  HybridSearchResponse,
  AgentQueryRequest,
  AgentQueryResponse
} from '@/types/graph'

const BASE_URL = '/knowledge'

/** @deprecated 走 /api/v1/knowledge/search */
export async function hybridSearch(
  data: HybridSearchRequest
): Promise<HybridSearchResponse> {
  const res = await request.post(`${BASE_URL}/search/hybrid`, data)
  return res.data.data
}

/** @deprecated 走真实知识库检索，而非 graphs agent 占位 */
export async function agentQuery(data: AgentQueryRequest): Promise<AgentQueryResponse> {
  const res = await request.post(`${BASE_URL}/agent/query`, data)
  return res.data.data
}
