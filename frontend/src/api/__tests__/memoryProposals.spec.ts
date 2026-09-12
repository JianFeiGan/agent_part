import { describe, it, expect } from 'vitest'
import {
  readAuthScopes,
  hasMemoryWrite,
  isForbiddenError,
  buildDistillGenerationResult
} from '@/api/memoryProposals'
import type { TaskDetail } from '@/types/task'

function fakeStorage(map: Record<string, string>): Pick<Storage, 'getItem'> {
  return {
    getItem: (key: string) => map[key] ?? null
  }
}

describe('readAuthScopes', () => {
  it('未写入 auth_scopes 时返回 null（未知）', () => {
    expect(readAuthScopes(fakeStorage({}))).toBeNull()
  })

  it('解析 JSON 字符串数组', () => {
    expect(readAuthScopes(fakeStorage({ auth_scopes: '["memory:read","memory:write"]' }))).toEqual([
      'memory:read',
      'memory:write'
    ])
  })

  it('非法 JSON / 非数组返回 null', () => {
    expect(readAuthScopes(fakeStorage({ auth_scopes: 'not-json' }))).toBeNull()
    expect(readAuthScopes(fakeStorage({ auth_scopes: '{"a":1}' }))).toBeNull()
  })
})

describe('hasMemoryWrite', () => {
  it('scope 未知（null）默认放行，兼容 AUTH 关闭部署', () => {
    expect(hasMemoryWrite(null)).toBe(true)
  })

  it('含 * 或 memory:write 时放行', () => {
    expect(hasMemoryWrite(['*'])).toBe(true)
    expect(hasMemoryWrite(['memory:read', 'memory:write'])).toBe(true)
  })

  it('仅 read 或空数组时无写权限', () => {
    expect(hasMemoryWrite(['memory:read'])).toBe(false)
    expect(hasMemoryWrite([])).toBe(false)
  })
})

describe('isForbiddenError', () => {
  it('识别 axios 403', () => {
    expect(isForbiddenError({ response: { status: 403 } })).toBe(true)
    expect(isForbiddenError({ response: { status: 500 } })).toBe(false)
    expect(isForbiddenError(new Error('x'))).toBe(false)
    expect(isForbiddenError(null)).toBe(false)
  })
})

describe('buildDistillGenerationResult', () => {
  const baseDetail = {
    task_id: 't1',
    product_id: 'p1',
    task_type: 'image_only',
    status: 'completed',
    progress: 100,
    current_step: 'quality_review',
    completed_steps: [],
    agent_logs: [],
    images: [
      { image_id: 'i1', image_type: 'main', url: 'u', status: 'ok' },
      { image_id: 'i2', image_type: 'scene', url: 'u2', status: 'ok' }
    ],
    video: null,
    quality_reports: [
      {
        report_id: 'r1',
        overall_score: 0.82,
        issues: ['背景过曝'],
        recommendations: ['降低曝光']
      }
    ],
    error_message: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    state: {
      selling_points: [{ title: '高清细节' }, '轻薄便携']
    }
  } as unknown as TaskDetail

  it('把任务真实字段写入 generation_result', () => {
    const result = buildDistillGenerationResult(baseDetail, 't1')

    expect(result.task_id).toBe('t1')
    expect(result.status).toBe('completed')
    expect(result.image_count).toBe(2)
    expect(result.has_video).toBe(false)
    expect(result.quality_score).toBe(0.82)
    expect(result.selling_points).toEqual([{ title: '高清细节' }, '轻薄便携'])
    expect(result.quality_review).toEqual({
      issues: ['背景过曝'],
      recommendations: ['降低曝光'],
      overall_score: 0.82
    })
    expect(result.performance_hints).toEqual({
      overall_score: 0.82,
      recommendation_count: 1
    })
  })

  it('缺 state / quality 时仍给出安全默认值', () => {
    const bare = {
      task_id: 't2',
      product_id: 'p1',
      task_type: 'video_only',
      status: 'failed',
      progress: 10,
      current_step: 'image',
      completed_steps: [],
      agent_logs: [],
      images: [],
      video: { video_id: 'v1', url: 'u', duration: 5, status: 'ok' },
      quality_reports: [],
      error_message: 'boom',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z'
    } as unknown as TaskDetail

    const result = buildDistillGenerationResult(bare, 't2')
    expect(result.image_count).toBe(0)
    expect(result.has_video).toBe(true)
    expect(result.selling_points).toEqual([])
    expect(result.quality_review).toEqual({
      issues: [],
      recommendations: [],
      overall_score: null
    })
    expect(result.error_message).toBe('boom')
    expect(result.performance_hints).toBeUndefined()
  })
})
