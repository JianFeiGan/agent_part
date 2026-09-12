/**
 * 记忆提案审核 API。
 * 对应 /api/v1/memory-proposals/*，返回业务数据。
 */
import request from './index'
import type { TaskDetail } from '@/types/task'

export interface MemoryProposal {
  id: number
  tenant_id: string
  category: string
  summary: string | null
  best_practices: string[]
  negative_patterns: string[]
  style_guidelines: Record<string, unknown>
  performance_hints: Record<string, unknown>
  source_type: string
  source_ref: string | null
  status: string
  confidence: number
  reviewed_by: string | null
  review_reason: string | null
  created_at: string
  updated_at: string
  reviewed_at: string | null
}

export interface MemoryProposalQuery {
  status?: string
  category?: string
  limit?: number
}

export interface DistillFromTaskRequest {
  source_type: 'task_completion'
  source_ref?: string
  generation_result?: Record<string, unknown>
  category?: string
}

const BASE_URL = '/memory-proposals'

// ============================================================================
// 权限门控（memory:write）
// ============================================================================

const AUTH_SCOPES_KEY = 'auth_scopes'

type ScopesStorage = Pick<Storage, 'getItem'>

/**
 * 读取本地缓存的 scope 列表。
 *
 * 限制：当前前端没有 auth store / /auth/me，无法在首屏拿到真实权限。
 * 约定：若部署方在 localStorage 写入 `auth_scopes`（JSON 字符串数组，
 * 如 `["memory:read"]` 或 `["*"]`），则按其判定；否则返回 null 表示未知。
 */
export function readAuthScopes(storage?: ScopesStorage): string[] | null {
  const store =
    storage ?? (typeof localStorage !== 'undefined' ? localStorage : undefined)
  if (!store) return null
  try {
    const raw = store.getItem(AUTH_SCOPES_KEY)
    if (!raw) return null
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return null
    return parsed.map(String)
  } catch {
    return null
  }
}

/**
 * 是否具备 memory:write。
 *
 * - scopes 为 null（未知 / AUTH 关闭）→ 默认放行，避免误伤无鉴权部署；
 * - scopes 含 `*` 或 `memory:write` → 放行；
 * - 其余（含空数组）→ 无写权限。
 */
export function hasMemoryWrite(scopes: string[] | null): boolean {
  if (scopes === null) return true
  return scopes.includes('*') || scopes.includes('memory:write')
}

/** 判断错误是否为 HTTP 403（scope 不足）。 */
export function isForbiddenError(error: unknown): boolean {
  if (typeof error !== 'object' || error === null) return false
  const response = (error as { response?: { status?: number } }).response
  return response?.status === 403
}

/**
 * 从任务详情组装 distill 的 generation_result。
 *
 * 后端 MemoryDistiller 只认 selling_points / quality_review.issues /
 * style_guidelines / performance_hints；同时附带状态与产出计数便于溯源。
 */
export function buildDistillGenerationResult(
  detail: TaskDetail,
  taskId: string
): Record<string, unknown> {
  const qualityIssues: string[] = []
  const recommendations: string[] = []
  let bestScore: number | null = null

  for (const report of detail.quality_reports ?? []) {
    for (const issue of report.issues ?? []) {
      if (issue) qualityIssues.push(issue)
    }
    for (const rec of report.recommendations ?? []) {
      if (rec) recommendations.push(rec)
    }
    if (typeof report.overall_score === 'number') {
      bestScore =
        bestScore === null ? report.overall_score : Math.max(bestScore, report.overall_score)
    }
  }

  const state = detail.state ?? {}
  const sellingPoints = Array.isArray(state.selling_points) ? state.selling_points : []

  const generationResult: Record<string, unknown> = {
    task_id: detail.task_id || taskId,
    status: detail.status,
    progress: detail.progress,
    current_step: detail.current_step,
    task_type: detail.task_type,
    image_count: detail.images?.length ?? 0,
    has_video: Boolean(detail.video),
    quality_score: bestScore,
    selling_points: sellingPoints,
    quality_review: {
      issues: qualityIssues,
      recommendations,
      overall_score: bestScore
    },
    error_message: detail.error_message ?? null
  }

  if (bestScore !== null || recommendations.length > 0) {
    generationResult.performance_hints = {
      overall_score: bestScore,
      recommendation_count: recommendations.length
    }
  }

  return generationResult
}

// ============================================================================
// API
// ============================================================================

/** 提案列表 */
export async function listMemoryProposals(
  params?: MemoryProposalQuery
): Promise<MemoryProposal[]> {
  const res = await request.get(`${BASE_URL}/proposals`, { params })
  return res.data.data
}

/** 提案详情 */
export async function getMemoryProposal(id: number): Promise<MemoryProposal> {
  const res = await request.get(`${BASE_URL}/proposals/${id}`)
  return res.data.data
}

/** 审批通过 */
export async function approveMemoryProposal(
  id: number,
  body?: Partial<Pick<MemoryProposal, 'summary' | 'best_practices' | 'negative_patterns' | 'style_guidelines' | 'performance_hints'>>
): Promise<MemoryProposal> {
  const res = await request.post(`${BASE_URL}/proposals/${id}/approve`, body ?? {})
  return res.data.data
}

/** 审批拒绝 */
export async function rejectMemoryProposal(id: number, reason: string): Promise<MemoryProposal> {
  const res = await request.post(`${BASE_URL}/proposals/${id}/reject`, { reason })
  return res.data.data
}

/** 从任务结果手动提炼 */
export async function distillMemory(data: DistillFromTaskRequest): Promise<MemoryProposal> {
  const res = await request.post(`${BASE_URL}/distill`, data)
  return res.data.data
}
