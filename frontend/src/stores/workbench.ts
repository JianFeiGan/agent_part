// frontend/src/stores/workbench.ts

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getTaskById } from '@/api/tasks'
import type {
  TaskDetail,
  AgentLog,
  TaskWsEvent,
  AgentStatusChangeEvent,
  AgentLogUpdateEvent,
} from '@/types/task'
import { NODE_MAP, getUpstreamNodeIds, getDownstreamNodeIds } from '@/workflow/topology'

/**
 * Agent 可观测工作台状态管理。
 */
export const useWorkbenchStore = defineStore('workbench', () => {
  // ==================== 状态 ====================
  /** 任务详情 */
  const taskDetail = ref<TaskDetail | null>(null)
  /** 当前选中的 Agent 节点 ID */
  const selectedAgentId = ref<string | null>(null)
  /** WebSocket 连接状态 */
  const wsConnected = ref(false)
  /** 加载状态 */
  const loading = ref(false)
  /** Agent 日志映射：step key → AgentLog */
  const agentLogMap = ref<Map<string, AgentLog>>(new Map())

  // ==================== 计算属性 ====================
  /** 当前选中的 Agent 日志 */
  const selectedAgentLog = computed<AgentLog | null>(() => {
    if (!selectedAgentId.value) return null
    return agentLogMap.value.get(selectedAgentId.value) ?? null
  })

  /** 选中节点的上游 Agent 标签列表 */
  const upstreamLabels = computed<string[]>(() => {
    if (!selectedAgentId.value) return []
    return getUpstreamNodeIds(selectedAgentId.value)
      .map(id => NODE_MAP.get(id)?.label ?? id)
  })

  /** 选中节点的下游 Agent 标签列表 */
  const downstreamLabels = computed<string[]>(() => {
    if (!selectedAgentId.value) return []
    return getDownstreamNodeIds(selectedAgentId.value)
      .map(id => NODE_MAP.get(id)?.label ?? id)
  })

  /** 全局统计：总 token */
  const totalTokens = computed(() => {
    let sum = 0
    for (const log of agentLogMap.value.values()) {
      sum += log.total_tokens
    }
    return sum
  })

  /** 全局统计：总费用 */
  const totalCost = computed(() => {
    let sum = 0
    for (const log of agentLogMap.value.values()) {
      sum += log.cost_cny
    }
    return sum
  })

  /** 全局统计：总耗时（ms） */
  const totalLatency = computed(() => {
    let sum = 0
    for (const log of agentLogMap.value.values()) {
      if (log.latency_ms) sum += log.latency_ms
    }
    return sum
  })

  // ==================== 方法 ====================
  /** 加载任务详情 */
  async function loadTask(taskId: string) {
    loading.value = true
    try {
      const response = await getTaskById(taskId)
      if (response.data.code === 200) {
        taskDetail.value = response.data.data
        // 构建 agentLogMap
        const map = new Map<string, AgentLog>()
        if (taskDetail.value?.agent_logs) {
          for (const log of taskDetail.value.agent_logs) {
            map.set(log.step, log)
          }
        }
        agentLogMap.value = map
        // 默认选中运行中或第一个节点
        const runningLog = taskDetail.value.agent_logs?.find(l => l.status === 'running')
        if (runningLog) {
          selectedAgentId.value = runningLog.step
        } else if (taskDetail.value.agent_logs?.length) {
          selectedAgentId.value = taskDetail.value.agent_logs[0].step
        } else {
          selectedAgentId.value = 'orchestrator'
        }
      }
    } finally {
      loading.value = false
    }
  }

  /** 选中 Agent 节点 */
  function selectAgent(agentId: string) {
    selectedAgentId.value = agentId
  }

  /** 处理 WebSocket 事件 */
  function handleWsEvent(event: TaskWsEvent) {
    switch (event.type) {
      case 'agent_status_change': {
        const e = event as AgentStatusChangeEvent
        const existing = agentLogMap.value.get(e.agent_name)
        if (existing) {
          existing.status = e.status
        } else {
          // 新节点开始运行，创建基础日志
          const nodeDef = NODE_MAP.get(e.agent_name)
          agentLogMap.value.set(e.agent_name, {
            agent_name: nodeDef?.label ?? e.agent_name,
            step: e.agent_name,
            start_time: e.status === 'running' ? new Date().toISOString() : null,
            end_time: null,
            status: e.status,
            message: null,
            output_summary: null,
            input_data: null,
            output_data: null,
            prompt_template: null,
            prompt_variables: null,
            input_tokens: 0,
            output_tokens: 0,
            total_tokens: 0,
            cost_cny: 0,
            latency_ms: null,
            model_name: null,
            provider: null,
            child_calls: [],
          })
        }
        // 自动选中运行中的节点
        if (e.status === 'running') {
          selectedAgentId.value = e.agent_name
        }
        break
      }
      case 'agent_log_update': {
        const e = event as AgentLogUpdateEvent
        agentLogMap.value.set(e.agent_log.step, e.agent_log)
        break
      }
      case 'progress_update': {
        if (taskDetail.value) {
          taskDetail.value.progress = event.progress
          taskDetail.value.current_step = event.current_step
        }
        break
      }
    }
  }

  /** 设置 WebSocket 连接状态 */
  function setWsConnected(connected: boolean) {
    wsConnected.value = connected
  }

  return {
    taskDetail,
    selectedAgentId,
    wsConnected,
    loading,
    agentLogMap,
    selectedAgentLog,
    upstreamLabels,
    downstreamLabels,
    totalTokens,
    totalCost,
    totalLatency,
    loadTask,
    selectAgent,
    handleWsEvent,
    setWsConnected,
  }
})
