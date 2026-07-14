<template>
  <div class="agent-metrics">
    <div class="metric-card" v-for="metric in metrics" :key="metric.label">
      <div class="metric-label">{{ metric.label }}</div>
      <div class="metric-value" :class="metric.colorClass">{{ metric.value }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AgentLog } from '@/types/task'

/**
 * Agent 指标卡片网格。
 * 展示 Model、Provider、Latency、Tokens、Cost、Status 六个指标。
 */

const props = defineProps<{
  log: AgentLog | null
}>()

const metrics = computed(() => {
  const log = props.log
  if (!log) return []
  return [
    { label: 'Model', value: log.model_name ?? '-', colorClass: '' },
    { label: 'Provider', value: log.provider ?? '-', colorClass: '' },
    { label: 'Latency', value: log.latency_ms ? `${(log.latency_ms / 1000).toFixed(1)}s` : '-', colorClass: 'text-blue' },
    { label: 'Tokens', value: log.total_tokens ? `${log.input_tokens} / ${log.output_tokens}` : '-', colorClass: '' },
    { label: 'Cost', value: log.cost_cny ? `¥${log.cost_cny.toFixed(3)}` : '-', colorClass: 'text-yellow' },
    { label: 'Status', value: log.status, colorClass: log.status === 'running' ? 'text-blue' : log.status === 'failed' ? 'text-red' : '' },
  ]
})
</script>

<style scoped>
.agent-metrics {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 16px;
}
.metric-card {
  background: #1a1a2e;
  border-radius: 6px;
  padding: 8px;
}
.metric-label {
  color: #636e72;
  font-size: 10px;
}
.metric-value {
  color: #c9d1d9;
  font-size: 12px;
  margin-top: 2px;
}
.text-blue { color: #58a6ff; }
.text-yellow { color: #fdcb6e; }
.text-red { color: #f85149; }
</style>
