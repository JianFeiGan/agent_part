/**
 * Description: 刊登工具 API 函数封装。
 * @author ganjianfei
 * @version 1.0.0
 * 2026-04-25
 */

import http from '@/api'
import type {
  AdapterConfigCreate,
  AdapterConfigResponse,
  AdapterConfigUpdate,
  ComplianceReportResponse,
  CreateListingTaskRequest,
  ListingTaskResponse,
  ProductImportRequest,
  ProductResponse,
  PushListingRequest,
  PushResponse,
  PushResultResponse,
} from '@/types/listing'
import type { ApiResponse } from '@/types/api'

/** 导入商品 */
export function importProduct(data: ProductImportRequest) {
  return http.post<ApiResponse<ProductResponse>>('/listing/import-product', data)
}

/** 获取商品列表 */
export function listProducts() {
  return http.get<ApiResponse<ProductResponse[]>>('/listing/products')
}

/** 创建刊登任务 */
export function createTask(data: CreateListingTaskRequest) {
  return http.post<ApiResponse<ListingTaskResponse>>('/listing/tasks', data)
}

/** 获取任务列表 */
export function listTasks() {
  return http.get<ApiResponse<ListingTaskResponse[]>>('/listing/tasks')
}

/** 执行合规检查 */
export function runComplianceCheck(taskId: number) {
  return http.post<ApiResponse<Record<string, ComplianceReportResponse>>>(
    `/listing/tasks/${taskId}/compliance`
  )
}

/** 获取合规报告 */
export function getComplianceReport(taskId: number) {
  return http.get<ApiResponse<Record<string, ComplianceReportResponse>>>(
    `/listing/compliance/${taskId}`
  )
}

/** 推送刊登 */
export function pushListing(taskId: number, data?: PushListingRequest) {
  return http.post<ApiResponse<PushResponse>>(
    `/listing/tasks/${taskId}/push`,
    data
  )
}

/** 获取推送结果 */
export function getPushResults(taskId: number) {
  return http.get<ApiResponse<PushResultResponse[]>>(
    `/listing/tasks/${taskId}/push-results`
  )
}

/** 获取适配器配置列表 */
export function listAdapterConfigs(platform?: string) {
  const params = platform ? { platform } : {}
  return http.get<ApiResponse<AdapterConfigResponse[]>>('/listing/adapter-configs', { params })
}

/** 创建适配器配置 */
export function createAdapterConfig(data: AdapterConfigCreate) {
  return http.post<ApiResponse<AdapterConfigResponse>>('/listing/adapter-configs', data)
}

/** 更新适配器配置 */
export function updateAdapterConfig(id: number, data: AdapterConfigUpdate) {
  return http.put<ApiResponse<AdapterConfigResponse>>(`/listing/adapter-configs/${id}`, data)
}

/** 删除适配器配置 */
export function deleteAdapterConfig(id: number) {
  return http.delete<ApiResponse<null>>(`/listing/adapter-configs/${id}`)
}
