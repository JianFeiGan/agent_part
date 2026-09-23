// @vitest-environment happy-dom
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createApp, nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus from 'element-plus'
import Workbench from '@/views/tasks/Workbench.vue'
import { getTaskById } from '@/api/tasks'
import { downloadFile } from '@/utils/download'
import { TaskStatus } from '@/types/task'
import type { TaskDetail } from '@/types/task'
import { MockWebSocket } from '@/test-utils/mockWebSocket'
import { makeDetail } from '@/test-utils/fixtures'
import { findButton, flushMicrotasks, trackMount, unmountAll } from '@/test-utils/dom'

const { routerPushMock } = vi.hoisted(() => ({ routerPushMock: vi.fn() }))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: 't1' } }),
  useRouter: () => ({ push: routerPushMock })
}))

vi.mock('@/api/tasks', () => ({
  getTaskById: vi.fn(),
  getTaskStatus: vi.fn(),
  cancelTask: vi.fn()
}))

vi.mock('@/utils/download', () => ({
  downloadFile: vi.fn().mockResolvedValue(undefined)
}))

// 诊断区组件打桩：避免 G6 等重依赖进入测试环境
vi.mock('@/components/workbench/AgentDAG.vue', () => ({
  default: { name: 'AgentDAG', template: '<div class="dag-stub">DAG</div>' }
}))
vi.mock('@/components/workbench/AgentDetailPanel.vue', () => ({
  default: { name: 'AgentDetailPanel', template: '<div class="panel-stub">PANEL</div>' }
}))

const getTaskByIdMock = vi.mocked(getTaskById)
const downloadFileMock = vi.mocked(downloadFile)

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
  await flushMicrotasks()
  await nextTick()
  trackMount(app, container)
  return { app, container }
}

beforeEach(() => {
  // happy-dom 自带 window/localStorage，切勿覆盖（popperjs 依赖 window 上的 DOM 类）
  MockWebSocket.instances = []
  vi.stubGlobal('WebSocket', MockWebSocket)
})

afterEach(() => {
  unmountAll()
  document.body.innerHTML = ''
  vi.unstubAllGlobals()
  vi.resetAllMocks()
})

describe('任务工作台：概览优先', () => {
  it('默认展示任务概览（状态/进度/当前阶段/结果概要），Agent 诊断默认折叠且不挂载', async () => {
    getTaskByIdMock.mockResolvedValue(
      makeDetail({ status: TaskStatus.RUNNING, progress: 45, current_step: 'creative_planner' })
    )
    const { container } = await mountWorkbench()

    // 概览默认可见
    expect(container.textContent).toContain('任务概览')
    expect(container.textContent).toContain('当前阶段')
    expect(container.textContent).toContain('creative_planner')
    expect(container.textContent).toContain('45%')
    // 非终态时结果概要显示生成中
    expect(container.textContent).toContain('生成中')
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

  it('终态任务的概览展示结果概要', async () => {
    getTaskByIdMock.mockResolvedValue(
      makeDetail({
        status: TaskStatus.COMPLETED,
        progress: 100,
        images: [
          { image_id: 'img1', image_type: 'main', url: 'http://cdn/x1.png', status: 'done' },
          { image_id: 'img2', image_type: 'scene', url: 'http://cdn/x2.png', status: 'done' }
        ],
        video: { video_id: 'v1', url: 'http://cdn/v.mp4', duration: 30, status: 'done' }
      })
    )
    const { container } = await mountWorkbench()
    expect(container.querySelector('.overview-grid')?.textContent).toContain('2 张图片 + 1 个视频')
  })
})

describe('任务工作台：加载失败与空态', () => {
  it('首屏加载失败展示驻留错误与重试入口，重试后恢复概览', async () => {
    getTaskByIdMock
      .mockRejectedValueOnce(new Error('boom'))
      .mockResolvedValueOnce(makeDetail({ status: TaskStatus.RUNNING, progress: 45 }))
    const { container } = await mountWorkbench()

    expect(container.textContent).toContain('任务详情加载失败')
    const retry = findButton(container, '重试')
    expect(retry).toBeTruthy()

    retry!.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await flushMicrotasks()
    await nextTick()
    expect(getTaskByIdMock).toHaveBeenCalledTimes(2)
    expect(container.textContent).toContain('任务概览')
  })

  it('任务详情为空时提供返回任务列表的下一步动作', async () => {
    getTaskByIdMock.mockResolvedValue(null as unknown as TaskDetail)
    const { container } = await mountWorkbench()

    expect(container.textContent).toContain('任务详情为空')
    const backBtn = findButton(container, '返回任务列表')
    expect(backBtn).toBeTruthy()
    backBtn!.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await nextTick()
    expect(routerPushMock).toHaveBeenCalledWith('/tasks')
  })
})

describe('任务工作台：资产结果与下载', () => {
  it('完成后展示图片资产，每张图可预览且有下载动作', async () => {
    getTaskByIdMock.mockResolvedValue(
      makeDetail({
        status: TaskStatus.COMPLETED,
        progress: 100,
        images: [
          { image_id: 'img1', image_type: 'main', url: 'http://cdn/x1.png', status: 'done' },
          { image_id: 'img2', image_type: 'scene', url: 'http://cdn/x2.png', status: 'done' }
        ]
      })
    )
    const { container } = await mountWorkbench()

    const tiles = container.querySelectorAll('.asset-tile')
    expect(tiles).toHaveLength(2)
    const imgs = container.querySelectorAll<HTMLImageElement>('.result-image img')
    expect(imgs).toHaveLength(2)
    expect(imgs[0].src).toBe('http://cdn/x1.png')

    const downloadBtn = tiles[0].querySelector('button')!
    expect(downloadBtn.textContent).toContain('下载')
    downloadBtn.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await flushMicrotasks(10)
    expect(downloadFileMock).toHaveBeenCalledWith('http://cdn/x1.png', 'img1.png')
  })

  it('完成后展示视频资产：可直接播放并提供下载', async () => {
    getTaskByIdMock.mockResolvedValue(
      makeDetail({
        status: TaskStatus.COMPLETED,
        progress: 100,
        video: { video_id: 'v1', url: 'http://cdn/v.mp4', duration: 30, status: 'done' }
      })
    )
    const { container } = await mountWorkbench()

    const video = container.querySelector<HTMLVideoElement>('video.result-video')
    expect(video).toBeTruthy()
    expect(video!.src).toBe('http://cdn/v.mp4')
    expect(video!.hasAttribute('controls')).toBe(true)

    findButton(container, '下载视频')!.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await flushMicrotasks(10)
    expect(downloadFileMock).toHaveBeenCalledWith('http://cdn/v.mp4', 'v1.mp4')
  })

  it('没有资产时显示明确空态', async () => {
    getTaskByIdMock.mockResolvedValue(
      makeDetail({ status: TaskStatus.COMPLETED, progress: 100, images: [], video: null })
    )
    const { container } = await mountWorkbench()
    expect(container.querySelector('.asset-empty')?.textContent).toContain('暂无图片或视频资产')
  })

  it('图片 URL 不可用时兜底展示且禁用下载', async () => {
    getTaskByIdMock.mockResolvedValue(
      makeDetail({
        status: TaskStatus.COMPLETED,
        progress: 100,
        images: [{ image_id: 'img1', image_type: 'main', url: '', status: 'failed' }]
      })
    )
    const { container } = await mountWorkbench()

    expect(container.querySelector('.asset-broken')?.textContent).toContain('图片地址不可用')
    const btn = container.querySelector<HTMLButtonElement>('.asset-tile button')
    expect(btn?.disabled).toBe(true)
  })

  it('视频 URL 不可用时兜底展示', async () => {
    getTaskByIdMock.mockResolvedValue(
      makeDetail({
        status: TaskStatus.COMPLETED,
        progress: 100,
        video: { video_id: 'v1', url: '', duration: 0, status: 'failed' }
      })
    )
    const { container } = await mountWorkbench()

    expect(container.querySelector('.asset-broken')?.textContent).toContain('视频地址不可用')
    expect(container.querySelector('video')).toBeNull()
  })

  it('任务未到终态时不展示结果区', async () => {
    getTaskByIdMock.mockResolvedValue(makeDetail({ status: TaskStatus.RUNNING, progress: 30 }))
    const { container } = await mountWorkbench()
    expect(container.querySelector('.results-card')).toBeNull()
  })
})
