/**
 * 主链路页面三态判定：loading / empty / error / ready。
 *
 * 规则：
 * - 加载中且无数据 → loading（有数据时静默刷新，保留列表）
 * - 加载失败且无数据 → error（有数据时保留旧数据，全局弹错由 axios 拦截器负责）
 * - 无数据 → empty
 * - 其余 → ready
 */
export type PageKind = 'loading' | 'empty' | 'error' | 'ready'

export function resolvePageKind(state: {
  loading: boolean
  failed: boolean
  hasData: boolean
}): PageKind {
  if (state.loading && !state.hasData) return 'loading'
  if (state.failed && !state.hasData) return 'error'
  if (!state.hasData) return 'empty'
  return 'ready'
}
