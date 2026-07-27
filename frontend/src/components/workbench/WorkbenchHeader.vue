<template>
  <div class="workbench-header">
    <div class="header-left">
      <el-button link @click="router.back()">
        <el-icon><ArrowLeft /></el-icon>
        返回
      </el-button>
      <span class="task-id">{{ store.taskDetail?.task_id }}</span>
      <el-tag :type="statusTagType" size="small">{{ statusLabel }}</el-tag>
      <el-tag v-if="taskTypeLabel" size="small" type="info">{{ taskTypeLabel }}</el-tag>
      <span v-if="store.wsConnected" class="ws-indicator connected">WS 已连接</span>
      <span v-else class="ws-indicator disconnected">WS 断开</span>
    </div>
    <div class="header-right">
      <div class="global-metrics">
        <span>⏱ {{ formatLatency(store.totalLatency) }}</span>
        <span>📊 {{ formatTokens(store.totalTokens) }}</span>
        <span>💰 ¥{{ store.totalCost.toFixed(3) }}</span>
      </div>
      <el-progress
        v-if="store.taskDetail?.status === 'running'"
        :percentage="store.taskDetail?.progress ?? 0"
        :stroke-width="6"
        style="width: 120px"
      />
      <el-button
        v-if="store.taskDetail?.status === 'running'"
        type="warning"
        size="small"
        @click="$emit('cancel')"
      >
        取消任务
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import { useWorkbenchStore } from '@/stores/workbench'
import { TaskStatusLabels, TaskTypeLabels } from '@/types/task'
import type { TaskStatus, TaskType } from '@/types/task'

const router = useRouter()
const store = useWorkbenchStore()

defineEmits<{
  cancel: []
}>()

const statusLabel = computed(() => {
  const status = store.taskDetail?.status
  return status ? (TaskStatusLabels[status as TaskStatus] ?? status) : ''
})

const statusTagType = computed(() => {
  const map: Record<string, string> = {
    pending: 'info',
    running: 'warning',
    completed: 'success',
    failed: 'danger',
  }
  return map[store.taskDetail?.status ?? ''] ?? 'info'
})

const taskTypeLabel = computed(() => {
  const type = store.taskDetail?.task_type
  return type ? (TaskTypeLabels[type as TaskType] ?? type) : ''
})

function formatLatency(ms: number): string {
  if (ms === 0) return '0s'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function formatTokens(tokens: number): string {
  if (tokens === 0) return '0 tok'
  if (tokens >= 1000) return `${(tokens / 1000).toFixed(1)}k tok`
  return `${tokens} tok`
}
</script>

<style scoped>
.workbench-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  background: #0d1117;
  border-bottom: 1px solid #2d2d4e;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.task-id {
  color: #c9d1d9;
  font-size: 13px;
  font-weight: 600;
}
.ws-indicator {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
}
.ws-indicator.connected {
  background: #238636;
  color: #fff;
}
.ws-indicator.disconnected {
  background: #30363d;
  color: #8b949e;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.global-metrics {
  display: flex;
  gap: 12px;
  color: #8b949e;
  font-size: 11px;
}
</style>
