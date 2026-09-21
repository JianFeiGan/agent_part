// @vitest-environment happy-dom
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createApp } from 'vue'
import type { App } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import type { Router } from 'vue-router'
import ElementPlus from 'element-plus'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import ProductsPage from '@/views/products/index.vue'
import TasksPage from '@/views/tasks/index.vue'
import TaskCreatePage from '@/views/tasks/Create.vue'
import WorkbenchPage from '@/views/tasks/Workbench.vue'

import { getProducts } from '@/api/products'
import { getTasks, getTaskById, getTaskStatus, createTask } from '@/api/tasks'
import { listModelProviders } from '@/api/providers'
import { downloadFile } from '@/utils/download'
import { TaskStatus } from '@/types/task'
import type { TaskCreateRequest } from '@/types/task'
import { MockWebSocket } from '@/test-utils/mockWebSocket'
import { makeDetail, makeStatus, makeTask, makeProduct } from '@/test-utils/fixtures'
import { findButton, flushTasks } from '@/test-utils/dom'

vi.mock('@/api/products', () => ({ getProducts: vi.fn(), deleteProduct: vi.fn() }))
vi.mock('@/api/tasks', () => ({
  getTasks: vi.fn(),
  getTaskById: vi.fn(),
  getTaskStatus: vi.fn(),
  createTask: vi.fn(),
  cancelTask: vi.fn(),
  deleteTask: vi.fn()
}))
vi.mock('@/api/providers', () => ({ listModelProviders: vi.fn() }))
vi.mock('@/utils/download', () => ({ downloadFile: vi.fn().mockResolvedValue(undefined) }))
// 诊断区组件打桩：避免 G6 等重依赖进入测试环境
vi.mock('@/components/workbench/AgentDAG.vue', () => ({
  default: { name: 'AgentDAG', template: '<div class="dag-stub" />' }
}))
vi.mock('@/components/workbench/AgentDetailPanel.vue', () => ({
  default: { name: 'AgentDetailPanel', template: '<div class="panel-stub" />' }
}))

const getProductsMock = vi.mocked(getProducts)
const getTasksMock = vi.mocked(getTasks)
const getTaskByIdMock = vi.mocked(getTaskById)
const getTaskStatusMock = vi.mocked(getTaskStatus)
const createTaskMock = vi.mocked(createTask)
const listModelProvidersMock = vi.mocked(listModelProviders)
const downloadFileMock = vi.mocked(downloadFile)

let app: App | null = null
let container: HTMLElement | null = null

async function mountAt(path: string): Promise<Router> {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/products', component: ProductsPage },
      { path: '/products/create', component: { template: '<div />' } },
      { path: '/tasks', component: TasksPage },
      { path: '/tasks/create', component: TaskCreatePage },
      { path: '/tasks/:id', component: WorkbenchPage }
    ]
  })
  const pinia = createPinia()
  setActivePinia(pinia)
  container = document.createElement('div')
  document.body.appendChild(container)
  app = createApp({ template: '<router-view />' })
  app.use(pinia)
  app.use(router)
  app.use(ElementPlus)
  // 对齐 main.ts 的全局图标注册，消除 <Refresh /> 等图标解析告警
  for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
    app.component(key, component)
  }
  router.push(path)
  await router.isReady()
  app.mount(container)
  await flushTasks()
  return router
}

describe('主链路端到端验收', () => {
  beforeEach(() => {
    MockWebSocket.instances = []
    // happy-dom 自带 window/localStorage，切勿覆盖（popperjs 依赖 window 上的 DOM 类）
    vi.stubGlobal('WebSocket', MockWebSocket)
    if (typeof globalThis.ResizeObserver === 'undefined') {
      vi.stubGlobal(
        'ResizeObserver',
        class {
          observe() {}
          unobserve() {}
          disconnect() {}
        }
      )
    }
    listModelProvidersMock.mockResolvedValue([])
  })

  afterEach(() => {
    app?.unmount()
    app = null
    container?.remove()
    container = null
    document.body.innerHTML = ''
    vi.unstubAllGlobals()
    vi.resetAllMocks()
  })

  it('商品 → 任务创建（预选提交）→ 任务列表 → 工作台 → WS 终态 → 资产下载 完整走通', async () => {
    getProductsMock.mockResolvedValue({
      items: [makeProduct()],
      total: 1,
      page: 1,
      page_size: 10,
      pages: 1
    })
    getTasksMock.mockResolvedValue({
      items: [makeTask()],
      total: 1,
      page: 1,
      page_size: 10,
      pages: 1
    })
    createTaskMock.mockResolvedValue({ task_id: 't1' })
    getTaskByIdMock
      .mockResolvedValueOnce(
        makeDetail({ status: TaskStatus.RUNNING, progress: 45, current_step: 'creative_planner' })
      )
      .mockResolvedValue(
        makeDetail({
          status: TaskStatus.COMPLETED,
          progress: 100,
          current_step: 'completed',
          images: [{ image_id: 'img1', image_type: 'main', url: 'http://cdn/x1.png', status: 'done' }]
        })
      )

    // 1. 商品列表 → 生成任务入口
    const router = await mountAt('/products')
    expect(container!.textContent).toContain('无线降噪耳机')
    findButton(container!, '生成任务')!.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await flushTasks()

    // 2. 任务创建页：商品已预选，直接提交
    expect(router.currentRoute.value.fullPath).toBe('/tasks/create?product_id=p1')
    expect(container!.textContent).toContain('无线降噪耳机')
    findButton(container!, '创建任务')!.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await flushTasks()
    expect(createTaskMock).toHaveBeenCalledTimes(1)
    const payload = createTaskMock.mock.calls[0][0] as TaskCreateRequest
    expect(payload.product_id).toBe('p1')
    expect(router.currentRoute.value.path).toBe('/tasks')

    // 3. 任务列表：新任务行展示统一状态标签
    expect(container!.textContent).toContain('t1')
    expect(container!.querySelector('.el-table__body')?.textContent).toContain('运行中')

    // 4. 进入工作台：概览优先，WS 建立
    findButton(container!, '详情')!.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await flushTasks()
    expect(router.currentRoute.value.path).toBe('/tasks/t1')
    expect(container!.textContent).toContain('任务概览')
    expect(container!.textContent).toContain('creative_planner')
    expect(MockWebSocket.instances).toHaveLength(1)

    // 5. WS 正常路径：打开连接后推送终态帧 → 自动补拉完整详情
    const ws = MockWebSocket.instances[0]
    ws.emitOpen()
    ws.emitMessage({ status: 'completed', progress: 100, current_step: 'completed' })
    await flushTasks()
    expect(getTaskByIdMock).toHaveBeenCalledTimes(2)

    // 6. 终态展示结果区，资产可下载
    expect(container!.textContent).toContain('生成结果')
    const downloadBtn = container!.querySelector<HTMLButtonElement>('.asset-tile button')
    expect(downloadBtn?.textContent).toContain('下载')
    downloadBtn!.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await flushTasks()
    expect(downloadFileMock).toHaveBeenCalledWith('http://cdn/x1.png', 'img1.png')
  })

  it('任务列表统一展示运行中与三种终态标签', async () => {
    getTasksMock.mockResolvedValue({
      items: [
        makeTask({ task_id: 't-run', status: TaskStatus.RUNNING }),
        makeTask({ task_id: 't-ok', status: TaskStatus.COMPLETED, progress: 100 }),
        makeTask({ task_id: 't-fail', status: TaskStatus.FAILED, error_message: '生成超时' }),
        makeTask({ task_id: 't-cancel', status: TaskStatus.CANCELLED })
      ],
      total: 4,
      page: 1,
      page_size: 10,
      pages: 1
    })
    await mountAt('/tasks')

    const body = container!.querySelector('.el-table__body')
    expect(body?.textContent).toContain('运行中')
    expect(body?.textContent).toContain('已完成')
    expect(body?.textContent).toContain('失败')
    expect(body?.textContent).toContain('已取消')
    // 失败任务展示错误信息
    expect(body?.textContent).toContain('生成超时')
  })

  it('商品列表查询失败给出驻留错误与重试入口，重试后恢复', async () => {
    getProductsMock
      .mockRejectedValueOnce(new Error('network down'))
      .mockResolvedValue({ items: [makeProduct()], total: 1, page: 1, page_size: 10, pages: 1 })
    await mountAt('/products')

    // 失败：驻留错误 + 重试入口，无数据时不展示表格
    expect(container!.textContent).toContain('商品列表加载失败')
    const retryBtn = findButton(container!, '重试')
    expect(retryBtn).toBeTruthy()
    expect(container!.textContent).not.toContain('无线降噪耳机')

    // 重试恢复
    retryBtn!.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await flushTasks()
    expect(getProductsMock).toHaveBeenCalledTimes(2)
    expect(container!.textContent).toContain('无线降噪耳机')
  })

  it('工作台 WS 断开后降级轮询兜底：轻量快照驱动进度并标注轮询通道', async () => {
    getTaskByIdMock.mockResolvedValue(
      makeDetail({ status: TaskStatus.RUNNING, progress: 45, current_step: 'creative_planner' })
    )
    getTaskStatusMock.mockResolvedValue(
      makeStatus({ status: TaskStatus.RUNNING, progress: 80, current_step: 'image_generator' })
    )
    await mountAt('/tasks/t1')

    // WS 建立后服务端断开 → 降级轮询
    const ws = MockWebSocket.instances[0]
    ws.emitOpen()
    ws.close()
    await flushTasks()

    // 立即轮询一次轻量状态
    expect(getTaskStatusMock).toHaveBeenCalledTimes(1)
    // 快照驱动进度与当前阶段
    expect(container!.textContent).toContain('80%')
    expect(container!.textContent).toContain('image_generator')
    // 通道标注为轮询兜底
    expect(container!.textContent).toContain('轮询兜底')
  })
})
