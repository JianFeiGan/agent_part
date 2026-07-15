// frontend/src/composables/useTaskWebSocket.ts

import { onMounted, onUnmounted } from 'vue'
import { useWorkbenchStore } from '@/stores/workbench'
import type { TaskWsEvent } from '@/types/task'

/**
 * 任务 WebSocket 连接 composable。
 *
 * 建立与后端的 WebSocket 连接，接收实时事件并分发到 workbench store。
 *
 * @param taskId - 任务 ID
 */
export function useTaskWebSocket(taskId: string) {
  const store = useWorkbenchStore()
  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null

  /** 构建 WebSocket URL */
  function buildWsUrl(): string {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const token = localStorage.getItem('token')
    const baseUrl = `${protocol}//${host}/api/v1/tasks/${taskId}/ws`
    return token ? `${baseUrl}?token=${token}` : baseUrl
  }

  /** 连接 WebSocket */
  function connect() {
    if (ws && ws.readyState === WebSocket.OPEN) return

    try {
      ws = new WebSocket(buildWsUrl())

      ws.onopen = () => {
        store.setWsConnected(true)
      }

      ws.onmessage = (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data)
          if (data.error) {
            console.error('WebSocket error:', data.error)
            return
          }
          // 判断是否为新格式事件（有 type 字段）
          if (data.type) {
            store.handleWsEvent(data as TaskWsEvent)
          }
          // 兼容旧格式（直接推送 status_data）
          else if (data.status) {
            store.handleWsEvent({
              type: 'progress_update',
              progress: data.progress ?? 0,
              current_step: data.current_step ?? '',
            })
          }
        } catch (e) {
          console.error('WebSocket 消息解析失败:', e)
        }
      }

      ws.onclose = () => {
        store.setWsConnected(false)
        // 任务运行中时自动重连
        if (store.taskDetail?.status === 'running') {
          reconnectTimer = setTimeout(connect, 3000)
        }
      }

      ws.onerror = () => {
        store.setWsConnected(false)
      }
    } catch (e) {
      console.error('WebSocket 连接失败:', e)
    }
  }

  /** 断开 WebSocket */
  function disconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (ws) {
      ws.close()
      ws = null
    }
  }

  onMounted(() => {
    connect()
  })

  onUnmounted(() => {
    disconnect()
  })

  return { connect, disconnect }
}
