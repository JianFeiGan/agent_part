/**
 * RAG 评估 API 封装。
 * 对应后端 /api/v1/evaluation/* 路由。
 *
 * 返回值为 `ApiResponse.data`，错误由全局拦截器统一处理并 reject。
 */
import request from './index'
import type {
  HitRateResponse,
  ComparisonRequest,
  ComparisonResponse,
  EvaluationReportResponse,
  EvaluationQueryParams
} from '@/types/evaluation'

const BASE_URL = '/evaluation'

/**
 * 获取命中率统计。
 */
export async function getHitRate(params?: EvaluationQueryParams): Promise<HitRateResponse> {
  const res = await request.get(`${BASE_URL}/hit-rate`, { params })
  return res.data.data
}

/**
 * RAG 与非 RAG 效果对比。
 */
export async function compareStrategies(
  data: ComparisonRequest
): Promise<ComparisonResponse> {
  const res = await request.post(`${BASE_URL}/compare`, data)
  return res.data.data
}

/**
 * 获取评估报告。
 */
export async function getEvaluationReport(
  params?: EvaluationQueryParams
): Promise<EvaluationReportResponse> {
  const res = await request.get(`${BASE_URL}/report`, { params })
  return res.data.data
}

/**
 * 获取优化建议列表。
 */
export async function getOptimizeSuggestions(): Promise<string[]> {
  const res = await request.get(`${BASE_URL}/optimize-suggestions`)
  return res.data.data
}
