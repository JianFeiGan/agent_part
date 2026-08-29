/**
 * RAG 评估模块类型定义。
 *
 * 对应后端 /api/v1/evaluation/* 路由。
 */

/** 命中率响应（GET /evaluation/hit-rate） */
export interface HitRateResponse {
  period: string
  total_retrievals: number
  unique_chunks_hit: number
  unique_docs_hit: number
  avg_results_per_query: number
  top_hit_chunks: Array<Record<string, unknown>>
}

/** 对比请求（POST /evaluation/compare） */
export interface ComparisonRequest {
  task_id?: string
  start_date?: string
  end_date?: string
}

/** 对比响应 */
export interface ComparisonResponse {
  period: string
  rag_stats: Record<string, unknown>
  non_rag_stats: Record<string, unknown>
  improvement: Record<string, number>
}

/** 评估报告响应（GET /evaluation/report） */
export interface EvaluationReportResponse {
  generated_at: string
  period: string
  summary: Record<string, unknown>
  retrieval_metrics: Record<string, unknown>
  quality_metrics: Record<string, unknown>
  recommendations: string[]
}

/** 评估模块查询参数 */
export interface EvaluationQueryParams {
  days?: number
}
