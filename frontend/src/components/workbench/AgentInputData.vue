<template>
  <div class="agent-input-data" v-if="log?.input_data">
    <div class="section-title">📥 输入参数 <span v-if="fromLabel" class="from-label">from {{ fromLabel }}</span></div>
    <div class="code-block">
      <pre>{{ formatJson(log.input_data) }}</pre>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { AgentLog } from '@/types/task'

/**
 * Agent 输入参数展示。
 * 展示 input_data 字段，标注来源 Agent。
 */

const props = defineProps<{
  log: AgentLog | null
  fromLabel?: string
}>()

function formatJson(data: Record<string, unknown> | null): string {
  if (!data) return ''
  return JSON.stringify(data, null, 2)
}
</script>

<style scoped>
.section-title {
  color: #636e72;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 6px;
}
.from-label {
  color: #e17055;
  font-size: 10px;
  text-transform: none;
}
.code-block {
  background: #1a1a2e;
  border-radius: 6px;
  padding: 10px;
  border-left: 3px solid #e17055;
  overflow-x: auto;
  margin-bottom: 12px;
}
.code-block pre {
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  font-size: 11px;
  line-height: 1.5;
  color: #c9d1d9;
  margin: 0;
  white-space: pre-wrap;
}
</style>
