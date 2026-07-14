<template>
  <div class="agent-output-data" v-if="log?.output_data">
    <div class="section-title">📤 输出数据 <span v-if="toLabel" class="to-label">→ {{ toLabel }}</span></div>
    <div class="code-block">
      <pre>{{ formatJson(log.output_data) }}</pre>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { AgentLog } from '@/types/task'

/**
 * Agent 输出数据展示。
 * 展示 output_data 字段，标注去向 Agent。
 */

const props = defineProps<{
  log: AgentLog | null
  toLabel?: string
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
.to-label {
  color: #00cec9;
  font-size: 10px;
  text-transform: none;
}
.code-block {
  background: #1a1a2e;
  border-radius: 6px;
  padding: 10px;
  border-left: 3px solid #00cec9;
  overflow-x: auto;
}
.code-block pre {
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  font-size: 11px;
  line-height: 1.5;
  color: #81ecec;
  margin: 0;
  white-space: pre-wrap;
}
</style>
