import { describe, it, expect } from 'vitest'
import { formatTime, getTaskStatusLabel, getTaskStatusTagType } from '@/utils/format'

describe('formatTime', () => {
  it('将 ISO 时间格式化为本地可读格式', () => {
    expect(formatTime('2026-04-05T10:30:45.123456')).toBe('2026-04-05 10:30:45')
    expect(formatTime('2026-04-05T10:30:45Z')).toBe('2026-04-05 10:30:45')
  })

  it('空值统一返回占位符，避免模板渲染出 null/undefined', () => {
    expect(formatTime('')).toBe('-')
    expect(formatTime(null)).toBe('-')
    expect(formatTime(undefined)).toBe('-')
  })
})

describe('getTaskStatusLabel', () => {
  it('映射已知的五种生成任务状态', () => {
    expect(getTaskStatusLabel('pending')).toBe('待处理')
    expect(getTaskStatusLabel('running')).toBe('运行中')
    expect(getTaskStatusLabel('completed')).toBe('已完成')
    expect(getTaskStatusLabel('failed')).toBe('失败')
    expect(getTaskStatusLabel('cancelled')).toBe('已取消')
  })

  it('空值返回占位符', () => {
    expect(getTaskStatusLabel('')).toBe('-')
    expect(getTaskStatusLabel(null)).toBe('-')
    expect(getTaskStatusLabel(undefined)).toBe('-')
  })

  it('未知状态原样返回，便于发现后端新增状态', () => {
    expect(getTaskStatusLabel('archived')).toBe('archived')
  })
})

describe('getTaskStatusTagType', () => {
  it('按语义返回标签类型', () => {
    expect(getTaskStatusTagType('pending')).toBe('info')
    expect(getTaskStatusTagType('running')).toBe('warning')
    expect(getTaskStatusTagType('completed')).toBe('success')
    expect(getTaskStatusTagType('failed')).toBe('danger')
    expect(getTaskStatusTagType('cancelled')).toBe('info')
  })

  it('未知状态与空值回退为 info，不抛错', () => {
    expect(getTaskStatusTagType('archived')).toBe('info')
    expect(getTaskStatusTagType('')).toBe('info')
    expect(getTaskStatusTagType(undefined)).toBe('info')
  })
})
