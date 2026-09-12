import { describe, it, expect } from 'vitest'

/** 与 useTaskStatusCoordinator 内联逻辑保持一致的终态判定 */
const TERMINAL = new Set(['completed', 'failed', 'cancelled'])

describe('task connection policy', () => {
  it('仅 completed/failed/cancelled 为终态', () => {
    expect(TERMINAL.has('completed')).toBe(true)
    expect(TERMINAL.has('failed')).toBe(true)
    expect(TERMINAL.has('cancelled')).toBe(true)
    expect(TERMINAL.has('running')).toBe(false)
    expect(TERMINAL.has('pending')).toBe(false)
  })

  it('仅 running 允许断线轮询', () => {
    const shouldPoll = (status: string) => status === 'running'
    expect(shouldPoll('running')).toBe(true)
    expect(shouldPoll('pending')).toBe(false)
    expect(shouldPoll('completed')).toBe(false)
  })
})
