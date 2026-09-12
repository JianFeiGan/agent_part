import { onMounted, onUnmounted, ref, computed } from 'vue'
import { useWorkbenchStore } from '@/stores/workbench'
import { getTaskStatus } from '@/api/tasks'
import type { TaskWsEvent, TaskStatus } from '@/types/task'

/** 连接模式：页面只消费该状态，不直接协调 WS/轮询 */
export type TaskConnectionMode = 'connecting' | 'websocket' | 'polling' | 'closed'

const POLL_INTERVAL_MS = 5000
const TERMINAL_STATUSES: ReadonlySet<string> = new Set(['completed', 'failed', 'cancelled'])

/**
 * 任务实时状态协调器。
 *
 * - WebSocket 优先实时更新
 * - WS 断开/不可用且任务仍 running 时，每 5s 轮询轻量状态
 * - 进入终态后停止轮询并补拉完整详情
 */
export function useTaskStatusCoordinator(taskId: string) {
  const store = useWorkbenchStore()
  const connectionMode = ref<TaskConnectionMode>('connecting')

  let ws: WebSocket | null = null
  let pollTimer: ReturnType<typeof setInterval> | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let stopped = false

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

  function isTerminal(status: string | undefined | null): boolean {
    return !!status && TERMINAL_STATUSES.has(status)
  }

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
      // 失败由拦截器提示
    }
  }

  async function pollOnce() {
    try {
      const status = await getTaskStatus(taskId)
      store.applyStatusSnapshot(status)
      if (isTerminal(status.status)) {
        stopPolling()
        connectionMode.value = 'closed'
        await fetchFullDetail()
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
    const status = store.taskDetail?.status as TaskStatus | undefined
    return status === 'running' || status === 'pending'
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
        store.setWsConnected(true)
        stopPolling()
        clearReconnect()
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
              current_step: data.current_step ?? ''
            })
          }
          if (isTerminal(store.taskDetail?.status)) {
            stopPolling()
            ws?.close()
          }
        } catch {
          // 忽略无法解析的帧
        }
      }

      ws.onclose = () => {
        store.setWsConnected(false)
        if (stopped) {
          connectionMode.value = 'closed'
          return
        }
        if (shouldPoll()) {
          startPolling()
          reconnectTimer = setTimeout(connectWs, 10_000)
        } else if (isTerminal(store.taskDetail?.status)) {
          connectionMode.value = 'closed'
        } else {
          connectionMode.value = 'closed'
          startPolling()
        }
      }

      ws.onerror = () => {
        store.setWsConnected(false)
      }
    } catch {
      connectionMode.value = 'polling'
      if (shouldPoll()) startPolling()
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
    store.setWsConnected(false)
  }

  onMounted(async () => {
    await fetchFullDetail()
    if (isTerminal(store.taskDetail?.status)) {
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
