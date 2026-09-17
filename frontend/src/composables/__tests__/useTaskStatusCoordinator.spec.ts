import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { createTaskStatusCoordinator } from '@/composables/useTaskStatusCoordinator'
import { useWorkbenchStore } from '@/stores/workbench'
import { getTaskById, getTaskStatus } from '@/api/tasks'
import { TaskStatus, TaskType } from '@/types/task'
import type { TaskDetail, TaskStatusResponse } from '@/types/task'

vi.mock('@/api/tasks', () => ({
  getTaskById: vi.fn(),
  getTaskStatus: vi.fn()
}))

const getTaskByIdMock = vi.mocked(getTaskById)
const getTaskStatusMock = vi.mocked(getTaskStatus)

type WsHandler = (() => void) | null

class MockWebSocket {
  static instances: MockWebSocket[] = []

  onopen: WsHandler = null
  onmessage: ((event: { data: string }) => void) | null = null
  onclose: WsHandler = null
  onerror: WsHandler = null
  closed = false

  constructor(public url: string) {
    MockWebSocket.instances.push(this)
  }

  close() {
    if (this.closed) return
    this.closed = true
    this.onclose?.()
  }

  emitOpen() {
    this.onopen?.()
  }

  emitMessage(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) })
  }

  /** 服务端/网络侧断开（非本端 close） */
  emitServerClose() {
    if (this.closed) return
    this.closed = true
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

function makeStatus(overrides: Partial<TaskStatusResponse> = {}): TaskStatusResponse {
  return {
    task_id: 't1',
    status: TaskStatus.RUNNING,
    progress: 0,
    current_step: '',
    created_at: '2026-09-17T00:00:00Z',
    updated_at: '2026-09-17T00:00:00Z',
    ...overrides
  }
}

/** 仅冲刷微任务队列（fake timers 下 Promise 链不受影响） */
async function flush() {
  for (let i = 0; i < 20; i++) await Promise.resolve()
}

describe('useTaskStatusCoordinator 行为', () => {
  let store: ReturnType<typeof useWorkbenchStore>

  beforeEach(() => {
    vi.useFakeTimers()
    setActivePinia(createPinia())
    store = useWorkbenchStore()
    MockWebSocket.instances = []
    vi.stubGlobal('WebSocket', MockWebSocket)
    vi.stubGlobal('window', { location: { protocol: 'http:', host: 'test.local' } })
    vi.stubGlobal('localStorage', { getItem: () => null })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    vi.resetAllMocks()
  })

  it('WebSocket 正常时实时更新任务状态与 Agent 状态，页面可感知连接模式', async () => {
    getTaskByIdMock.mockResolvedValue(makeDetail({ status: TaskStatus.RUNNING, progress: 10 }))
    const c = createTaskStatusCoordinator('t1')
    expect(c.connectionMode.value).toBe('connecting')
    expect(c.connectionLabel.value).toBe('连接中')

    await c.start()
    expect(MockWebSocket.instances).toHaveLength(1)
    const ws = MockWebSocket.instances[0]
    expect(ws.url).toBe('ws://test.local/api/v1/tasks/t1/ws')

    ws.emitOpen()
    expect(c.connectionMode.value).toBe('websocket')
    expect(c.connectionLabel.value).toBe('实时连接')

    ws.emitMessage({ type: 'progress_update', progress: 55, current_step: 'creative_planner' })
    expect(store.taskDetail?.progress).toBe(55)
    expect(store.taskDetail?.current_step).toBe('creative_planner')

    ws.emitMessage({ type: 'agent_status_change', agent_name: 'creative_planner', status: 'running' })
    expect(store.agentLogMap.get('creative_planner')?.status).toBe('running')
    expect(store.selectedAgentId).toBe('creative_planner')
  })

  it('收到终态帧后关闭连接，且仅补拉一次完整详情', async () => {
    getTaskByIdMock
      .mockResolvedValueOnce(makeDetail({ status: TaskStatus.RUNNING, progress: 10 }))
      .mockResolvedValue(makeDetail({ status: TaskStatus.COMPLETED, progress: 100 }))
    const c = createTaskStatusCoordinator('t1')
    await c.start()
    const ws = MockWebSocket.instances[0]
    ws.emitOpen()

    // legacy 轻量帧（无 type，仅状态字段）
    ws.emitMessage({ status: 'completed', progress: 100, current_step: 'done' })
    await flush()

    expect(c.connectionMode.value).toBe('closed')
    expect(c.connectionLabel.value).toBe('已断开')
    // 初始 1 次 + 终态补拉 1 次（onclose 与 onmessage 双路径不重复拉取）
    expect(getTaskByIdMock).toHaveBeenCalledTimes(2)
    expect(store.taskDetail?.status).toBe(TaskStatus.COMPLETED)
  })

  it('WS 断开且任务 running 时降级轮询：间隔 5s、轻量快照更新', async () => {
    getTaskByIdMock.mockResolvedValue(makeDetail({ status: TaskStatus.RUNNING, progress: 10 }))
    const c = createTaskStatusCoordinator('t1')
    await c.start()
    const ws = MockWebSocket.instances[0]
    ws.emitOpen()

    getTaskStatusMock.mockResolvedValue(
      makeStatus({ status: TaskStatus.RUNNING, progress: 30, current_step: 'image_generator' })
    )
    ws.emitServerClose()
    await flush()

    expect(c.connectionMode.value).toBe('polling')
    expect(c.connectionLabel.value).toBe('轮询兜底')
    // 降级后立即轮询一次
    expect(getTaskStatusMock).toHaveBeenCalledTimes(1)
    // 轻量快照驱动状态/进度
    expect(store.taskDetail?.progress).toBe(30)
    expect(store.taskDetail?.current_step).toBe('image_generator')

    // 间隔恰好 5s
    await vi.advanceTimersByTimeAsync(4999)
    expect(getTaskStatusMock).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(1)
    expect(getTaskStatusMock).toHaveBeenCalledTimes(2)
  })

  it('轮询发现终态后停止轮询、清除重连并补拉完整详情', async () => {
    getTaskByIdMock
      .mockResolvedValueOnce(makeDetail({ status: TaskStatus.RUNNING }))
      .mockResolvedValue(makeDetail({ status: TaskStatus.COMPLETED, progress: 100 }))
    const c = createTaskStatusCoordinator('t1')
    await c.start()
    const ws = MockWebSocket.instances[0]
    ws.emitOpen()

    getTaskStatusMock.mockResolvedValueOnce(makeStatus({ status: TaskStatus.RUNNING, progress: 40 }))
    ws.emitServerClose()
    await flush()
    expect(getTaskStatusMock).toHaveBeenCalledTimes(1)

    getTaskStatusMock.mockResolvedValueOnce(makeStatus({ status: TaskStatus.COMPLETED, progress: 100 }))
    await vi.advanceTimersByTimeAsync(5000)
    await flush()

    expect(c.connectionMode.value).toBe('closed')
    expect(getTaskStatusMock).toHaveBeenCalledTimes(2)
    // 终态补拉完整详情
    expect(getTaskByIdMock).toHaveBeenCalledTimes(2)
    expect(store.taskDetail?.progress).toBe(100)

    // 轮询已停、重连已清：继续推进不产生新请求/新连接
    await vi.advanceTimersByTimeAsync(60_000)
    await flush()
    expect(getTaskStatusMock).toHaveBeenCalledTimes(2)
    expect(MockWebSocket.instances).toHaveLength(1)
  })

  it('非 running 任务断线后不启动轮询', async () => {
    getTaskByIdMock.mockResolvedValue(makeDetail({ status: TaskStatus.PENDING }))
    const c = createTaskStatusCoordinator('t1')
    await c.start()
    const ws = MockWebSocket.instances[0]
    ws.emitOpen()
    ws.emitServerClose()
    await flush()

    expect(c.connectionMode.value).toBe('closed')
    await vi.advanceTimersByTimeAsync(30_000)
    expect(getTaskStatusMock).not.toHaveBeenCalled()
  })

  it('WebSocket 构造失败且任务 running 时直接进入轮询', async () => {
    getTaskByIdMock.mockResolvedValue(makeDetail({ status: TaskStatus.RUNNING }))
    class ThrowingWebSocket {
      constructor() {
        throw new Error('WebSocket unsupported')
      }
    }
    vi.stubGlobal('WebSocket', ThrowingWebSocket)
    getTaskStatusMock.mockResolvedValue(makeStatus({ status: TaskStatus.RUNNING, progress: 5 }))

    const c = createTaskStatusCoordinator('t1')
    await c.start()
    await flush()

    expect(c.connectionMode.value).toBe('polling')
    expect(getTaskStatusMock).toHaveBeenCalledTimes(1)
  })

  it('首屏加载即为终态时不建立任何连接', async () => {
    getTaskByIdMock.mockResolvedValue(makeDetail({ status: TaskStatus.COMPLETED, progress: 100 }))
    const c = createTaskStatusCoordinator('t1')
    await c.start()

    expect(c.connectionMode.value).toBe('closed')
    expect(MockWebSocket.instances).toHaveLength(0)
    expect(getTaskStatusMock).not.toHaveBeenCalled()
  })

  it('stop 后停止轮询且不再发起状态请求', async () => {
    getTaskByIdMock.mockResolvedValue(makeDetail({ status: TaskStatus.RUNNING }))
    const c = createTaskStatusCoordinator('t1')
    await c.start()
    const ws = MockWebSocket.instances[0]
    ws.emitOpen()

    getTaskStatusMock.mockResolvedValue(makeStatus({ status: TaskStatus.RUNNING, progress: 10 }))
    ws.emitServerClose()
    await flush()
    expect(getTaskStatusMock).toHaveBeenCalledTimes(1)

    c.stop()
    expect(c.connectionMode.value).toBe('closed')
    await vi.advanceTimersByTimeAsync(60_000)
    expect(getTaskStatusMock).toHaveBeenCalledTimes(1)
  })

  it('首屏加载失败且无已有详情时回调 onFirstLoadError', async () => {
    getTaskByIdMock.mockRejectedValue(new Error('boom'))
    const onFirstLoadError = vi.fn()
    const c = createTaskStatusCoordinator('t1', { onFirstLoadError })
    await c.start()

    expect(onFirstLoadError).toHaveBeenCalledTimes(1)
  })
})
