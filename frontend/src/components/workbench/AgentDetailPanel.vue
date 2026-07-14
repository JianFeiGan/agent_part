<template>
  <div class="agent-detail-panel">
    <!-- 无选中节点 -->
    <div v-if="!store.selectedAgentLog" class="empty-state">
      <p>点击左侧节点查看详情</p>
    </div>

    <!-- 有选中节点 -->
    <template v-else>
      <!-- Agent 头部 -->
      <div class="agent-header">
        <div class="agent-icon" :style="{ background: nodeColor }">
          {{ nodeEmoji }}
        </div>
        <div class="agent-info">
          <div class="agent-name">{{ store.selectedAgentLog.agent_name }}</div>
          <div class="agent-role" :style="{ color: nodeColor }">
            {{ nodeRole }} · {{ statusLabel }}
          </div>
        </div>
      </div>

      <!-- 指标网格 -->
      <AgentMetrics :log="store.selectedAgentLog" />

      <!-- 输入参数 -->
      <AgentInputData
        :log="store.selectedAgentLog"
        :from-label="store.upstreamLabels.join(', ')"
      />

      <!-- 提示词轨迹 -->
      <AgentPromptTrace :log="store.selectedAgentLog" />

      <!-- 子调用记录 -->
      <AgentChildCalls :log="store.selectedAgentLog" />

      <!-- 输出数据 -->
      <AgentOutputData
        :log="store.selectedAgentLog"
        :to-label="store.downstreamLabels.join(', ')"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useWorkbenchStore } from '@/stores/workbench'
import { NODE_MAP } from '@/workflow/topology'
import { AgentLogStatusLabels } from '@/types/task'
import AgentMetrics from './AgentMetrics.vue'
import AgentInputData from './AgentInputData.vue'
import AgentPromptTrace from './AgentPromptTrace.vue'
import AgentChildCalls from './AgentChildCalls.vue'
import AgentOutputData from './AgentOutputData.vue'

const store = useWorkbenchStore()

const nodeDef = computed(() => {
  const id = store.selectedAgentId
  return id ? NODE_MAP.get(id) : undefined
})

const nodeColor = computed(() => nodeDef.value?.color ?? '#636e72')
const nodeRole = computed(() => nodeDef.value?.role ?? '')

const nodeEmoji = computed(() => {
  const id = store.selectedAgentId
  const emojiMap: Record<string, string> = {
    orchestrator: '⚡',
    requirement_analyzer: '🔍',
    creative_planner: '💡',
    visual_designer: '🎨',
    image_generator: '🖼',
    video_generator: '🎬',
    quality_reviewer: '✅',
  }
  return emojiMap[id ?? ''] ?? '🤖'
})

const statusLabel = computed(() => {
  const status = store.selectedAgentLog?.status
  return status ? (AgentLogStatusLabels[status as keyof typeof AgentLogStatusLabels] ?? status) : ''
})
</script>

<style scoped>
.agent-detail-panel {
  padding: 16px;
  overflow-y: auto;
  height: 100%;
  background: #161b22;
}
.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  color: #636e72;
  font-size: 14px;
}
.agent-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #2d2d4e;
}
.agent-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
}
.agent-name {
  color: #fff;
  font-size: 14px;
  font-weight: 600;
}
.agent-role {
  font-size: 11px;
}
</style>
