import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { createTaskStatusCoordinator } from '@/composables/useTaskStatusCoordinator'
import { useWorkbenchStore } from '@/stores/workbench'
import { getTaskById, getTaskStatus } from '@/api/tasks'
import { TaskStatus } from '@/types/task'
import { MockWebSocket } from '@/test-utils/mockWebSocket'
import { makeDetail, makeStatus } from '@/test-utils/fixtures'
import { flushMicrotasks } from '@/test-utils/dom'

vi.mock('@/api/tasks', () => ({
  getTaskById: vi.fn(),
  getTaskStatus: vi.fn()
}))

const getTaskByIdMock = vi.mocked(getTaskById)
const getTaskStatusMock = vi.mocked(getTaskStatus)

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
    const coordinator = createTaskStatusCoordinator('t1')
    expect(coordinator.connectionMode.value).toBe('connecting')
    expect(coordinator.connectionLabel.value).toBe('连接中')

    await coordinator.start()
    expect(MockWebSocket.instances).toHaveLength(1)
    const ws = MockWebSocket.instances[0]
    expect(ws.url).toBe('ws://test.local/api/v1/tasks/t1/ws')

    ws.emitOpen()
    expect(coordinator.connectionMode.value).toBe('websocket')
    expect(coordinator.connectionLabel.value).toBe('实时连接')

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
    const coordinator = createTaskStatusCoordinator('t1')
    await coordinator.start()
    const ws = MockWebSocket.instances[0]
    ws.emitOpen()

    // legacy 轻量帧（无 type，仅状态字段）
    ws.emitMessage({ status: 'completed', progress: 100, current_step: 'done' })
    await flushMicrotasks()

    expect(coordinator.connectionMode.value).toBe('closed')
    expect(coordinator.connectionLabel.value).toBe('已断开')
    // 初始 1 次 + 终态补拉 1 次（onclose 与 onmessage 双路径不重复拉取）
    expect(getTaskByIdMock).toHaveBeenCalledTimes(2)
    expect(store.taskDetail?.status).toBe(TaskStatus.COMPLETED)
  })

  it('WS 断开且任务 running 时降级轮询：间隔 5s、轻量快照更新', async () => {
    getTaskByIdMock.mockResolvedValue(makeDetail({ status: TaskStatus.RUNNING, progress: 10 }))
    const coordinator = createTaskStatusCoordinator('t1')
    await coordinator.start()
    const ws = MockWebSocket.instances[0]
    ws.emitOpen()

    getTaskStatusMock.mockResolvedValue(
      makeStatus({ status: TaskStatus.RUNNING, progress: 30, current_step: 'image_generator' })
    )
    ws.close()
    await flushMicrotasks()

    expect(coordinator.connectionMode.value).toBe('polling')
    expect(coordinator.connectionLabel.value).toBe('轮询兜底')
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
    const coordinator = createTaskStatusCoordinator('t1')
    await coordinator.start()
    const ws = MockWebSocket.instances[0]
    ws.emitOpen()

    getTaskStatusMock.mockResolvedValueOnce(makeStatus({ status: TaskStatus.RUNNING, progress: 40 }))
    ws.close()
    await flushMicrotasks()
    expect(getTaskStatusMock).toHaveBeenCalledTimes(1)

    getTaskStatusMock.mockResolvedValueOnce(makeStatus({ status: TaskStatus.COMPLETED, progress: 100 }))
    await vi.advanceTimersByTimeAsync(5000)
    await flushMicrotasks()

    expect(coordinator.connectionMode.value).toBe('closed')
    expect(getTaskStatusMock).toHaveBeenCalledTimes(2)
    // 终态补拉完整详情
    expect(getTaskByIdMock).toHaveBeenCalledTimes(2)
    expect(store.taskDetail?.progress).toBe(100)

    // 轮询已停、重连已清：继续推进不产生新请求/新连接
    await vi.advanceTimersByTimeAsync(60_000)
    await flushMicrotasks()
    expect(getTaskStatusMock).toHaveBeenCalledTimes(2)
    expect(MockWebSocket.instances).toHaveLength(1)
  })

  it('非 running 任务断线后不启动轮询', async () => {
    getTaskByIdMock.mockResolvedValue(makeDetail({ status: TaskStatus.PENDING }))
    const coordinator = createTaskStatusCoordinator('t1')
    await coordinator.start()
    const ws = MockWebSocket.instances[0]
    ws.emitOpen()
    ws.close()
    await flushMicrotasks()

    expect(coordinator.connectionMode.value).toBe('closed')
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

    const coordinator = createTaskStatusCoordinator('t1')
    await coordinator.start()
    await flushMicrotasks()

    expect(coordinator.connectionMode.value).toBe('polling')
    expect(getTaskStatusMock).toHaveBeenCalledTimes(1)
  })

  it('首屏加载即为终态时不建立任何连接', async () => {
    getTaskByIdMock.mockResolvedValue(makeDetail({ status: TaskStatus.COMPLETED, progress: 100 }))
    const coordinator = createTaskStatusCoordinator('t1')
    await coordinator.start()

    expect(coordinator.connectionMode.value).toBe('closed')
    expect(MockWebSocket.instances).toHaveLength(0)
    expect(getTaskStatusMock).not.toHaveBeenCalled()
  })

  it('stop 后停止轮询且不再发起状态请求', async () => {
    getTaskByIdMock.mockResolvedValue(makeDetail({ status: TaskStatus.RUNNING }))
    const coordinator = createTaskStatusCoordinator('t1')
    await coordinator.start()
    const ws = MockWebSocket.instances[0]
    ws.emitOpen()

    getTaskStatusMock.mockResolvedValue(makeStatus({ status: TaskStatus.RUNNING, progress: 10 }))
    ws.close()
    await flushMicrotasks()
    expect(getTaskStatusMock).toHaveBeenCalledTimes(1)

    coordinator.stop()
    expect(coordinator.connectionMode.value).toBe('closed')
    await vi.advanceTimersByTimeAsync(60_000)
    expect(getTaskStatusMock).toHaveBeenCalledTimes(1)
  })

  it('首屏加载失败且无已有详情时回调 onFirstLoadError', async () => {
    getTaskByIdMock.mockRejectedValue(new Error('boom'))
    const onFirstLoadError = vi.fn()
    const coordinator = createTaskStatusCoordinator('t1', { onFirstLoadError })
    await coordinator.start()

    expect(onFirstLoadError).toHaveBeenCalledTimes(1)
  })
})
