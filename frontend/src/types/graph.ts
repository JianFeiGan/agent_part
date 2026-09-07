/**
 * 知识图谱模块类型定义。
 *
 * 对应后端 /api/v1/knowledge/* 下的知识图谱相关端点
 * （/knowledge/graphs、/knowledge/search/hybrid、/knowledge/agent/query）。
 */

/** 知识图谱信息 */
export interface KnowledgeGraph {
  id: string
  name: string
  tenant_id: string
  status: string
  document_count: number
  entity_count: number
  relation_count: number
  created_at: string
  updated_at: string
}

/** 创建图谱请求（POST /knowledge/graphs） */
export interface KnowledgeGraphCreate {
  name: string
  description?: string
}

/** 图谱列表响应（GET /knowledge/graphs） */
export interface KnowledgeGraphListResponse {
  items: KnowledgeGraph[]
  total: number
  page: number
  page_size: number
}

/** 图谱分页查询参数 */
export interface KnowledgeGraphQueryParams {
  page?: number
  page_size?: number
}

/** 向图谱添加文档请求（POST /knowledge/graphs/{id}/documents） */
export interface AddDocumentRequest {
  title: string
  content: string
  format?: string
}

/** 混合搜索单个结果 */
export interface HybridSearchResult {
  id: string
  content: string
  score: number
  source: string | null
  metadata: Record<string, unknown>
}

/** 混合搜索请求（POST /knowledge/search/hybrid） */
export interface HybridSearchRequest {
  query: string
  top_k?: number
  strategy?: string
}

/** 混合搜索响应 */
export interface HybridSearchResponse {
  query: string
  results: HybridSearchResult[]
  answer: string | null
  sources: Array<Record<string, unknown>>
}

/** Agent 问答请求（POST /knowledge/agent/query） */
export interface AgentQueryRequest {
  query: string
  session_id?: string
}

/** Agent 问答响应 */
export interface AgentQueryResponse {
  session_id: string
  answer: string
  sources: Array<Record<string, unknown>>
  agent_logs: Array<Record<string, unknown>>
}
