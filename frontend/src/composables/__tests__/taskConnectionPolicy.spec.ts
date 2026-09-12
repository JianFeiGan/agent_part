import { describe, it, expect } from 'vitest'
import {
  TaskStatus,
  isTerminalTaskStatus,
  isRunningTaskStatus
} from '@/types/task'
import { shouldPollForStatus } from '@/composables/useTaskStatusCoordinator'

describe('task connection policy', () => {
  it('仅 completed/failed/cancelled 为终态（isTerminalTaskStatus）', () => {
    expect(isTerminalTaskStatus(TaskStatus.COMPLETED)).toBe(true)
    expect(isTerminalTaskStatus(TaskStatus.FAILED)).toBe(true)
    expect(isTerminalTaskStatus(TaskStatus.CANCELLED)).toBe(true)
    expect(isTerminalTaskStatus('completed')).toBe(true)
    expect(isTerminalTaskStatus('failed')).toBe(true)
    expect(isTerminalTaskStatus('cancelled')).toBe(true)
    expect(isTerminalTaskStatus(TaskStatus.RUNNING)).toBe(false)
    expect(isTerminalTaskStatus(TaskStatus.PENDING)).toBe(false)
    expect(isTerminalTaskStatus(null)).toBe(false)
    expect(isTerminalTaskStatus(undefined)).toBe(false)
    expect(isTerminalTaskStatus('')).toBe(false)
  })

  it('仅 running 为运行中（isRunningTaskStatus）', () => {
    expect(isRunningTaskStatus(TaskStatus.RUNNING)).toBe(true)
    expect(isRunningTaskStatus('running')).toBe(true)
    expect(isRunningTaskStatus(TaskStatus.PENDING)).toBe(false)
    expect(isRunningTaskStatus(TaskStatus.COMPLETED)).toBe(false)
    expect(isRunningTaskStatus(null)).toBe(false)
    expect(isRunningTaskStatus(undefined)).toBe(false)
  })

  it('仅 running 允许断线轮询（shouldPollForStatus）', () => {
    expect(shouldPollForStatus(TaskStatus.RUNNING)).toBe(true)
    expect(shouldPollForStatus('running')).toBe(true)
    expect(shouldPollForStatus('pending')).toBe(false)
    expect(shouldPollForStatus('completed')).toBe(false)
    expect(shouldPollForStatus('failed')).toBe(false)
    expect(shouldPollForStatus('cancelled')).toBe(false)
    expect(shouldPollForStatus(null)).toBe(false)
    expect(shouldPollForStatus(undefined)).toBe(false)
  })

  it('终态与运行中互斥', () => {
    for (const status of Object.values(TaskStatus)) {
      expect(isTerminalTaskStatus(status) && isRunningTaskStatus(status)).toBe(false)
    }
  })
})
