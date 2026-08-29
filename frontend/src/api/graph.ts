/**
 * 知识图谱 API 封装。
 * 对应后端 /api/v1/knowledge/* 下的知识图谱端点。
 *
 * 返回值为 `ApiResponse.data`，错误由全局拦截器统一处理并 reject。
 */
import request from './index'
import type {
  KnowledgeGraph,
  KnowledgeGraphCreate,
  KnowledgeGraphListResponse,
  KnowledgeGraphQueryParams,
  AddDocumentRequest,
  HybridSearchRequest,
  HybridSearchResponse,
  AgentQueryRequest,
  AgentQueryResponse
} from '@/types/graph'

const BASE_URL = '/knowledge'

/**
 * 创建知识图谱。
 */
export async function createGraph(data: KnowledgeGraphCreate): Promise<KnowledgeGraph> {
  const res = await request.post(`${BASE_URL}/graphs`, data)
  return res.data.data
}

/**
 * 获取知识图谱列表。
 */
export async function listGraphs(
  params?: KnowledgeGraphQueryParams
): Promise<KnowledgeGraphListResponse> {
  const res = await request.get(`${BASE_URL}/graphs`, { params })
  return res.data.data
}

/**
 * 向图谱添加文档。
 */
export async function addGraphDocument(
  graphId: string,
  data: AddDocumentRequest
): Promise<Record<string, unknown>> {
  const res = await request.post(`${BASE_URL}/graphs/${graphId}/documents`, data)
  return res.data.data
}

/**
 * 混合检索（向量 + 关键词）。
 */
export async function hybridSearch(
  data: HybridSearchRequest
): Promise<HybridSearchResponse> {
  const res = await request.post(`${BASE_URL}/search/hybrid`, data)
  return res.data.data
}

/**
 * 知识 Agent 问答（多 Agent 协作生成回答）。
 */
export async function agentQuery(data: AgentQueryRequest): Promise<AgentQueryResponse> {
  const res = await request.post(`${BASE_URL}/agent/query`, data)
  return res.data.data
}
