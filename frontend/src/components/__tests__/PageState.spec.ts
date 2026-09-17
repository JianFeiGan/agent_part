// @vitest-environment happy-dom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createApp, h } from 'vue'
import type { App } from 'vue'
import ElementPlus from 'element-plus'
import PageState from '@/components/PageState.vue'

const mounted: Array<{ app: App; container: HTMLElement }> = []

type PageStateMountProps = {
  kind: 'loading' | 'empty' | 'error' | 'ready'
  emptyDescription?: string
  emptyActionText?: string
  errorTitle?: string
  retryText?: string
  retrying?: boolean
  rows?: number
  onRetry?: () => void
  'onEmpty-action'?: () => void
}

function mountPageState(props: PageStateMountProps, slotContent?: string) {
  const container = document.createElement('div')
  document.body.appendChild(container)
  const app = createApp({
    render() {
      return h(PageState, props, slotContent ? { default: () => slotContent } : undefined)
    }
  })
  app.use(ElementPlus)
  app.mount(container)
  const entry = { app, container }
  mounted.push(entry)
  return entry
}

afterEach(() => {
  while (mounted.length) {
    const { app, container } = mounted.pop()!
    app.unmount()
    container.remove()
  }
})

describe('PageState 共享三态组件', () => {
  it('loading：渲染骨架屏，不渲染默认内容', () => {
    const { container } = mountPageState({ kind: 'loading' }, 'READY-CONTENT')
    expect(container.querySelector('.el-skeleton')).toBeTruthy()
    expect(container.textContent).not.toContain('READY-CONTENT')
  })

  it('empty：展示描述与引导动作，点击触发 empty-action', () => {
    const onEmptyAction = vi.fn()
    const { container } = mountPageState({
      kind: 'empty',
      emptyDescription: '还没有商品，先创建一个再生成视觉素材',
      emptyActionText: '创建商品',
      'onEmpty-action': onEmptyAction
    })
    expect(container.textContent).toContain('还没有商品，先创建一个再生成视觉素材')
    const btn = container.querySelector<HTMLButtonElement>('.el-empty button')
    expect(btn?.textContent).toContain('创建商品')
    btn?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    expect(onEmptyAction).toHaveBeenCalledTimes(1)
  })

  it('empty：未配置动作文案时不渲染动作按钮', () => {
    const { container } = mountPageState({ kind: 'empty', emptyDescription: '暂无数据' })
    expect(container.textContent).toContain('暂无数据')
    expect(container.querySelector('.el-empty button')).toBeNull()
  })

  it('error：驻留错误信息与重试入口，点击触发 retry', () => {
    const onRetry = vi.fn()
    const { container } = mountPageState({
      kind: 'error',
      errorTitle: '任务列表加载失败',
      onRetry
    })
    expect(container.textContent).toContain('任务列表加载失败')
    const btn = container.querySelector<HTMLButtonElement>('.page-state__error button')
    expect(btn?.textContent).toContain('重试')
    btn?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    expect(onRetry).toHaveBeenCalledTimes(1)
    // error 态只提供驻留信息，不产生全局弹窗（弹错由 axios 拦截器负责）
    expect(document.body.querySelector('.el-message')).toBeNull()
  })

  it('error：支持自定义重试文案与重试中态', () => {
    const { container } = mountPageState({
      kind: 'error',
      errorTitle: '商品列表加载失败',
      retryText: '重新加载',
      retrying: true
    })
    const btn = container.querySelector<HTMLButtonElement>('.page-state__error button')
    expect(btn?.textContent).toContain('重新加载')
    expect(btn?.classList.contains('is-loading')).toBe(true)
  })

  it('ready：渲染默认插槽内容', () => {
    const { container } = mountPageState({ kind: 'ready' }, 'READY-CONTENT')
    expect(container.textContent).toContain('READY-CONTENT')
    expect(container.querySelector('.el-skeleton')).toBeNull()
    expect(container.querySelector('.el-empty')).toBeNull()
    expect(container.querySelector('.el-alert')).toBeNull()
  })
})
