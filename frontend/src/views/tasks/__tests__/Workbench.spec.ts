// @vitest-environment happy-dom
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createApp, nextTick } from 'vue'
import type { App } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus from 'element-plus'
import Workbench from '@/views/tasks/Workbench.vue'
import { getTaskById } from '@/api/tasks'
import { TaskStatus, TaskType } from '@/types/task'
import type { TaskDetail } from '@/types/task'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: 't1' } }),
  useRouter: () => ({ push: vi.fn() })
}))

vi.mock('@/api/tasks', () => ({
  getTaskById: vi.fn(),
  getTaskStatus: vi.fn(),
  cancelTask: vi.fn()
}))

// 诊断区组件打桩：避免 G6 等重依赖进入测试环境
vi.mock('@/components/workbench/AgentDAG.vue', () => ({
  default: { name: 'AgentDAG', template: '<div class="dag-stub">DAG</div>' }
}))
vi.mock('@/components/workbench/AgentDetailPanel.vue', () => ({
  default: { name: 'AgentDetailPanel', template: '<div class="panel-stub">PANEL</div>' }
}))

const getTaskByIdMock = vi.mocked(getTaskById)

class MockWebSocket {
  onopen: (() => void) | null = null
  onmessage: ((event: { data: string }) => void) | null = null
  onclose: (() => void) | null = null
  onerror: (() => void) | null = null
  constructor(public url: string) {}
  close() {
    this.onclose?.()
  }
}

function makeDetail(overrides: Partial<TaskDetail> = {}): TaskDetail {
  return {
    task_id: 't1',
    product_id: 'p1',
    task_type: TaskType.IMAGE_ONLY,
    status: TaskStatus.RUNNING,
    progress: 0,
    current_step: 'orchestrator',
    completed_steps: [],
    agent_logs: [],
    images: [],
    video: null,
    quality_reports: [],
    error_message: null,
    created_at: '2026-09-17T00:00:00Z',
    updated_at: '2026-09-17T00:00:00Z',
    ...overrides
  }
}

const mounted: Array<{ app: App; container: HTMLElement }> = []

async function mountWorkbench() {
  const container = document.createElement('div')
  document.body.appendChild(container)
  const pinia = createPinia()
  setActivePinia(pinia)
  const app = createApp(Workbench)
  app.use(pinia)
  app.use(ElementPlus)
  app.mount(container)
  // 等首屏详情加载与 DOM 更新
  for (let i = 0; i < 20; i++) await Promise.resolve()
  await nextTick()
  const entry = { app, container }
  mounted.push(entry)
  return entry
}

function findButton(container: HTMLElement, text: string): HTMLButtonElement | undefined {
  return Array.from(container.querySelectorAll('button')).find(b =>
    b.textContent?.includes(text)
  )
}

describe('任务工作台：概览优先', () => {
  beforeEach(() => {
    vi.stubGlobal('WebSocket', MockWebSocket)
    vi.stubGlobal('window', { location: { protocol: 'http:', host: 'test.local' } })
    vi.stubGlobal('localStorage', { getItem: () => null })
  })

  afterEach(() => {
    while (mounted.length) {
      const { app, container } = mounted.pop()!
      app.unmount()
      container.remove()
    }
    vi.unstubAllGlobals()
    vi.resetAllMocks()
  })

  it('默认展示任务概览（状态/进度/当前阶段），Agent 诊断默认折叠且不挂载', async () => {
    getTaskByIdMock.mockResolvedValue(
      makeDetail({ status: TaskStatus.RUNNING, progress: 45, current_step: 'creative_planner' })
    )
    const { container } = await mountWorkbench()

    // 概览默认可见
    expect(container.textContent).toContain('任务概览')
    expect(container.textContent).toContain('当前阶段')
    expect(container.textContent).toContain('creative_planner')
    expect(container.textContent).toContain('45%')
    // 诊断区默认折叠：入口可见，内容未挂载
    expect(findButton(container, '展开 Agent 诊断')).toBeTruthy()
    expect(container.querySelector('.dag-stub')).toBeNull()
    expect(container.querySelector('.panel-stub')).toBeNull()
  })

  it('点击展开后可查看 Agent 诊断，再次点击收起', async () => {
    getTaskByIdMock.mockResolvedValue(makeDetail({ status: TaskStatus.RUNNING, progress: 45 }))
    const { container } = await mountWorkbench()

    const toggle = findButton(container, '展开 Agent 诊断')!
    toggle.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await nextTick()

    expect(container.querySelector('.dag-stub')).toBeTruthy()
    expect(container.querySelector('.panel-stub')).toBeTruthy()
    expect(findButton(container, '收起诊断')).toBeTruthy()

    findButton(container, '收起诊断')!.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await nextTick()
    expect(container.querySelector('.dag-stub')).toBeNull()
  })

  it('失败任务在概览中直接展示关键错误', async () => {
    getTaskByIdMock.mockResolvedValue(
      makeDetail({
        status: TaskStatus.FAILED,
        progress: 60,
        error_message: '图片生成服务返回 429：额度不足'
      })
    )
    const { container } = await mountWorkbench()

    const alert = container.querySelector('.overview-error')
    expect(alert).toBeTruthy()
    expect(alert!.textContent).toContain('图片生成服务返回 429：额度不足')
    // 概览中状态标签同步为失败
    expect(container.querySelector('.overview-grid')?.textContent).toContain('失败')
  })
})
