import type { AxiosResponse } from 'axios'
import request from './index'
import type { ApiResponse } from '@/types/api'
import type {
  KnowledgeDocument,
  KnowledgeDocumentCreate,
  KnowledgeDocumentListResponse,
  KnowledgeQueryParams,
  SearchRequest,
  SearchResponse,
  KnowledgeStats
} from '@/types/knowledge'

/**
 * 知识库 API
 * @description 知识库管理相关接口
 */

const BASE_URL = '/knowledge'

/**
 * 获取文档列表
 */
export function getDocuments(
  params: KnowledgeQueryParams
): Promise<AxiosResponse<ApiResponse<KnowledgeDocumentListResponse>>> {
  return request.get(`${BASE_URL}/documents`, { params })
}

/**
 * 创建文档
 */
export function createDocument(
  data: KnowledgeDocumentCreate
): Promise<AxiosResponse<ApiResponse<KnowledgeDocument>>> {
  return request.post(`${BASE_URL}/documents`, data)
}

/**
 * 上传文档文件
 */
export function uploadDocument(
  file: File,
  docType: string,
  category?: string
): Promise<AxiosResponse<ApiResponse<KnowledgeDocument>>> {
  const formData = new FormData()
  formData.append('file', file)

  const params: Record<string, string> = { doc_type: docType }
  if (category) {
    params.category = category
  }

  return request.post(`${BASE_URL}/documents/upload`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    },
    params
  })
}

/**
 * 删除文档
 */
export function deleteDocument(
  docId: number
): Promise<AxiosResponse<ApiResponse<{ deleted_id: number }>>> {
  return request.delete(`${BASE_URL}/documents/${docId}`)
}

/**
 * 检索知识库
 */
export function searchKnowledge(
  data: SearchRequest
): Promise<AxiosResponse<ApiResponse<SearchResponse>>> {
  return request.post(`${BASE_URL}/search`, data)
}

/**
 * 获取知识库统计
 */
export function getKnowledgeStats(): Promise<AxiosResponse<ApiResponse<KnowledgeStats>>> {
  return request.get(`${BASE_URL}/stats`)
}