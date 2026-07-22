/**
 * Description: 模型厂商管理 API 函数封装。
 * @author ganjianfei
 * @version 1.0.0
 * 2026-07-22
 */

import http from '@/api'
import type {
  ModelProviderCreate,
  ModelProviderResponse,
  ModelProviderTestResponse,
  ModelProviderUpdate,
} from '@/types/provider'
import type { ApiResponse } from '@/types/api'

/** 获取模型厂商列表 */
export function listModelProviders(providerType?: string) {
  const params = providerType ? { provider_type: providerType } : {}
  return http.get<ApiResponse<ModelProviderResponse[]>>('/model-providers', { params })
}

/** 获取模型厂商详情 */
export function getModelProvider(id: number) {
  return http.get<ApiResponse<ModelProviderResponse>>(`/model-providers/${id}`)
}

/** 创建模型厂商 */
export function createModelProvider(data: ModelProviderCreate) {
  return http.post<ApiResponse<ModelProviderResponse>>('/model-providers', data)
}

/** 更新模型厂商 */
export function updateModelProvider(id: number, data: ModelProviderUpdate) {
  return http.put<ApiResponse<ModelProviderResponse>>(`/model-providers/${id}`, data)
}

/** 删除模型厂商 */
export function deleteModelProvider(id: number) {
  return http.delete<ApiResponse<null>>(`/model-providers/${id}`)
}

/** 设为默认厂商 */
export function setDefaultModelProvider(id: number) {
  return http.put<ApiResponse<ModelProviderResponse>>(`/model-providers/${id}/default`)
}

/** 测试厂商连接 */
export function testModelProvider(id: number, model?: string) {
  return http.post<ApiResponse<ModelProviderTestResponse>>(
    `/model-providers/${id}/test`,
    model ? { model } : {}
  )
}
