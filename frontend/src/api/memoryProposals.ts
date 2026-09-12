/**
 * 记忆提案审核 API。
 * 对应 /api/v1/memory-proposals/*，返回业务数据。
 */
import request from './index'

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
