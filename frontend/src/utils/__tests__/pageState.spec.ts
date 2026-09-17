import { describe, it, expect } from 'vitest'
import { resolvePageKind } from '@/utils/pageState'

describe('resolvePageKind 页面三态判定', () => {
  it('加载中且无数据 → loading', () => {
    expect(resolvePageKind({ loading: true, failed: false, hasData: false })).toBe('loading')
  })

  it('加载中但有数据 → ready（静默刷新，保留列表）', () => {
    expect(resolvePageKind({ loading: true, failed: false, hasData: true })).toBe('ready')
  })

  it('加载失败且无数据 → error（驻留重试入口）', () => {
    expect(resolvePageKind({ loading: false, failed: true, hasData: false })).toBe('error')
  })

  it('加载失败但有旧数据 → ready（保留旧数据，弹错交给拦截器）', () => {
    expect(resolvePageKind({ loading: false, failed: true, hasData: true })).toBe('ready')
  })

  it('空闲且无数据 → empty', () => {
    expect(resolvePageKind({ loading: false, failed: false, hasData: false })).toBe('empty')
  })

  it('空闲且有数据 → ready', () => {
    expect(resolvePageKind({ loading: false, failed: false, hasData: true })).toBe('ready')
  })

  it('重试进行中（loading 与 failed 同真）→ loading 优先', () => {
    expect(resolvePageKind({ loading: true, failed: true, hasData: false })).toBe('loading')
  })
})
