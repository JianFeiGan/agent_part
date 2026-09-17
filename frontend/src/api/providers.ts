/**
 * Description: 模型厂商管理 API 函数封装。
 *
 * 返回值为 `ApiResponse.data`，错误由全局拦截器统一处理并 reject。
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
export async function listModelProviders(
  providerType?: string
): Promise<ModelProviderResponse[]> {
  const params = providerType ? { provider_type: providerType } : {}
  const res = await http.get<ApiResponse<ModelProviderResponse[]>>('/model-providers', { params })
  return res.data.data
}

/** 获取模型厂商详情 */
export async function getModelProvider(id: number): Promise<ModelProviderResponse> {
  const res = await http.get<ApiResponse<ModelProviderResponse>>(`/model-providers/${id}`)
  return res.data.data
}

/** 创建模型厂商 */
export async function createModelProvider(
  data: ModelProviderCreate
): Promise<ModelProviderResponse> {
  const res = await http.post<ApiResponse<ModelProviderResponse>>('/model-providers', data)
  return res.data.data
}

/** 更新模型厂商 */
export async function updateModelProvider(
  id: number,
  data: ModelProviderUpdate
): Promise<ModelProviderResponse> {
  const res = await http.put<ApiResponse<ModelProviderResponse>>(`/model-providers/${id}`, data)
  return res.data.data
}

/** 删除模型厂商 */
export async function deleteModelProvider(id: number): Promise<null> {
  const res = await http.delete<ApiResponse<null>>(`/model-providers/${id}`)
  return res.data.data
}

/** 设为默认厂商 */
export async function setDefaultModelProvider(id: number): Promise<ModelProviderResponse> {
  const res = await http.put<ApiResponse<ModelProviderResponse>>(
    `/model-providers/${id}/default`
  )
  return res.data.data
}

/** 测试厂商连接 */
export async function testModelProvider(
  id: number,
  model?: string
): Promise<ModelProviderTestResponse> {
  const res = await http.post<ApiResponse<ModelProviderTestResponse>>(
    `/model-providers/${id}/test`,
    model ? { model } : {}
  )
  return res.data.data
}
