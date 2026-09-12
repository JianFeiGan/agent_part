/**
 * 知识库 API。
 *
 * 走真实 `/api/v1/knowledge`（document processor + vector store），
 * 不要使用 `/knowledge/graphs` 的内存占位实现。
 * 返回值为 `ApiResponse.data`。
 */
import request from './index'
import type {
  KnowledgeDocument,
  KnowledgeDocumentCreate,
  KnowledgeDocumentListResponse,
  KnowledgeQueryParams,
  SearchRequest,
  SearchResponse,
  KnowledgeStats
} from '@/types/knowledge'

const BASE_URL = '/knowledge'

/** 获取文档列表 */
export async function getDocuments(
  params: KnowledgeQueryParams
): Promise<KnowledgeDocumentListResponse> {
  const res = await request.get(`${BASE_URL}/documents`, { params })
  return res.data.data
}

/** 创建文档 */
export async function createDocument(
  data: KnowledgeDocumentCreate
): Promise<KnowledgeDocument> {
  const res = await request.post(`${BASE_URL}/documents`, data)
  return res.data.data
}

/** 上传文档文件 */
export async function uploadDocument(
  file: File,
  docType: string,
  category?: string
): Promise<KnowledgeDocument> {
  const formData = new FormData()
  formData.append('file', file)

  const params: Record<string, string> = { doc_type: docType }
  if (category) {
    params.category = category
  }

  const res = await request.post(`${BASE_URL}/documents/upload`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    },
    params
  })
  return res.data.data
}

/** 删除文档 */
export async function deleteDocument(docId: number): Promise<{ deleted_id: number }> {
  const res = await request.delete(`${BASE_URL}/documents/${docId}`)
  return res.data.data
}

/** 检索知识库 */
export async function searchKnowledge(data: SearchRequest): Promise<SearchResponse> {
  const res = await request.post(`${BASE_URL}/search`, data)
  return res.data.data
}

/** 知识库统计 */
export async function getKnowledgeStats(): Promise<KnowledgeStats> {
  const res = await request.get(`${BASE_URL}/stats`)
  return res.data.data
}
