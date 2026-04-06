/**
 * 知识库文档类型
 */
export type DocType = 'brand_guide' | 'category_knowledge' | 'case_study' | 'compliance_rule'

/**
 * 文档类型标签映射
 */
export const DOC_TYPE_LABELS: Record<DocType, string> = {
  brand_guide: '品牌规范',
  category_knowledge: '类目知识',
  case_study: '成功案例',
  compliance_rule: '合规规则'
}

/**
 * 知识库文档
 */
export interface KnowledgeDocument {
  id: number
  title: string
  doc_type: DocType
  category: string | null
  source: string | null
  version: number
  created_at: string
  updated_at: string
}

/**
 * 创建文档请求
 */
export interface KnowledgeDocumentCreate {
  title: string
  doc_type: DocType
  category?: string
  content: string
  metadata?: Record<string, unknown>
}

/**
 * 文档查询参数
 */
export interface KnowledgeQueryParams {
  doc_type?: DocType
  category?: string
  page?: number
  page_size?: number
}

/**
 * 文档列表响应
 */
export interface KnowledgeDocumentListResponse {
  total: number
  documents: KnowledgeDocument[]
}

/**
 * 检索请求
 */
export interface SearchRequest {
  query: string
  doc_type?: DocType
  category?: string
  top_k?: number
}

/**
 * 检索结果项
 */
export interface SearchResultItem {
  chunk_id: number
  doc_id: number
  content: string
  similarity: number
  doc_title: string
  doc_type: DocType
}

/**
 * 检索响应
 */
export interface SearchResponse {
  query: string
  results: SearchResultItem[]
  total: number
}

/**
 * 知识库统计
 */
export interface KnowledgeStats {
  total_documents: number
  total_chunks: number
  documents_by_type: Record<string, number>
}