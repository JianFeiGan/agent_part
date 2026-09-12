import { onMounted, onUnmounted, ref, computed } from 'vue'
import { useWorkbenchStore } from '@/stores/workbench'
import { getTaskStatus } from '@/api/tasks'
import { isTerminalTaskStatus, isRunningTaskStatus } from '@/types/task'
import type { TaskWsEvent } from '@/types/task'

/** 连接模式：页面只消费该状态，不直接协调 WS/轮询 */
export type TaskConnectionMode = 'connecting' | 'websocket' | 'polling' | 'closed'

const POLL_INTERVAL_MS = 5000

/** 断线后是否启动轮询：按 Spec 仅 running */
export function shouldPollForStatus(status: string | null | undefined): boolean {
  return isRunningTaskStatus(status)
}

/**
 * 任务实时状态协调器。
 *
 * - WebSocket 优先实时更新
 * - WS 断开/不可用且任务仍 running 时，每 5s 轮询轻量状态
 * - 进入终态后停止轮询并补拉完整详情
 */
export function useTaskStatusCoordinator(
  taskId: string,
  options?: { onFirstLoadError?: () => void }
) {
  const store = useWorkbenchStore()
  const connectionMode = ref<TaskConnectionMode>('connecting')

  let ws: WebSocket | null = null
  let pollTimer: ReturnType<typeof setInterval> | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let stopped = false
  /** 终态后是否已补拉过详情，避免 WS close 与 onmessage 双拉 */
  let terminalDetailFetched = false

  const connectionLabel = computed(() => {
    switch (connectionMode.value) {
      case 'websocket':
        return '实时连接'
      case 'polling':
        return '轮询兜底'
      case 'connecting':
        return '连接中'
      default:
        return '已断开'
    }
  })

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  function clearReconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  async function fetchFullDetail() {
    try {
      await store.loadTask(taskId)
    } catch {
      // 仅首屏无数据时进入 error；终态补拉失败保留已有详情
      if (!store.taskDetail) {
        options?.onFirstLoadError?.()
      }
    }
  }

  async function fetchTerminalDetailOnce() {
    if (terminalDetailFetched) return
    terminalDetailFetched = true
    await fetchFullDetail()
  }

  async function pollOnce() {
    try {
      const status = await getTaskStatus(taskId)
      store.applyStatusSnapshot(status)
      if (isTerminalTaskStatus(status.status)) {
        stopPolling()
        connectionMode.value = 'closed'
        await fetchTerminalDetailOnce()
      }
    } catch {
      // 拦截器已提示；保留轮询等下一次
    }
  }

  function startPolling() {
    if (pollTimer || stopped) return
    connectionMode.value = 'polling'
    void pollOnce()
    pollTimer = setInterval(() => {
      void pollOnce()
    }, POLL_INTERVAL_MS)
  }

  function shouldPoll(): boolean {
    return shouldPollForStatus(store.taskDetail?.status)
  }

  function finishToTerminal() {
    stopPolling()
    clearReconnect()
    connectionMode.value = 'closed'
    void fetchTerminalDetailOnce()
  }

  function buildWsUrl(): string {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const token = localStorage.getItem('token')
    const baseUrl = `${protocol}//${host}/api/v1/tasks/${taskId}/ws`
    return token ? `${baseUrl}?token=${encodeURIComponent(token)}` : baseUrl
  }

  function connectWs() {
    if (stopped) return
    try {
      ws = new WebSocket(buildWsUrl())

      ws.onopen = () => {
        connectionMode.value = 'websocket'
        clearReconnect()
        stopPolling()
      }

      ws.onmessage = (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data)
          if (data.error) return
          if (data.type) {
            store.handleWsEvent(data as TaskWsEvent)
          } else if (data.status) {
            store.handleWsEvent({
              type: 'progress_update',
              progress: data.progress ?? 0,
              current_step: data.current_step ?? '',
              status: data.status
            })
          }
          if (isTerminalTaskStatus(store.taskDetail?.status)) {
            ws?.close()
            finishToTerminal()
          }
        } catch {
          // 忽略无法解析的帧
        }
      }

      ws.onclose = () => {
        if (stopped) {
          connectionMode.value = 'closed'
          return
        }
        if (isTerminalTaskStatus(store.taskDetail?.status)) {
          connectionMode.value = 'closed'
          void fetchTerminalDetailOnce()
          return
        }
        if (shouldPoll()) {
          startPolling()
          reconnectTimer = setTimeout(connectWs, 10_000)
        } else {
          connectionMode.value = 'closed'
        }
      }

      ws.onerror = () => {
        // onclose 随后触发并降级
      }
    } catch {
      if (shouldPoll()) startPolling()
      else connectionMode.value = 'closed'
    }
  }

  function stop() {
    stopped = true
    stopPolling()
    clearReconnect()
    if (ws) {
      ws.close()
      ws = null
    }
    connectionMode.value = 'closed'
  }

  onMounted(async () => {
    await fetchFullDetail()
    if (isTerminalTaskStatus(store.taskDetail?.status)) {
      connectionMode.value = 'closed'
      return
    }
    connectWs()
  })

  onUnmounted(() => {
    stop()
  })

  return {
    connectionMode,
    connectionLabel,
    stop
  }
}
