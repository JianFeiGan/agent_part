<template>
  <div class="agent-prompt-trace" v-if="log?.prompt_template || log?.prompt_variables">
    <div class="section-title">💬 提示词轨迹</div>
    <div class="prompt-block" v-if="log?.prompt_template">
      <div class="prompt-label">System Prompt</div>
      <pre class="prompt-content">{{ log.prompt_template }}</pre>
    </div>
    <div class="vars-block" v-if="log?.prompt_variables && Object.keys(log.prompt_variables).length">
      <div class="prompt-label">Variables</div>
      <div class="var-item" v-for="(value, key) in log.prompt_variables" :key="String(key)">
        <span class="var-name">{{ String(key) }}</span>
        <span class="var-arrow">→</span>
        <span class="var-value">{{ truncate(String(value), 80) }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { AgentLog } from '@/types/task'

/**
 * Agent 提示词轨迹展示。
 * 展示 prompt_template 和 prompt_variables。
 */

defineProps<{
  log: AgentLog | null
}>()

function truncate(str: string, max: number): string {
  return str.length > max ? str.slice(0, max) + '...' : str
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
.prompt-block {
  background: #1a1a2e;
  border-radius: 6px;
  padding: 10px;
  border-left: 3px solid #6c5ce7;
  margin-bottom: 8px;
  overflow-x: auto;
}
.prompt-label {
  color: #636e72;
  font-size: 9px;
  margin-bottom: 4px;
}
.prompt-content {
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  font-size: 11px;
  line-height: 1.5;
  color: #a29bfe;
  margin: 0;
  white-space: pre-wrap;
}
.vars-block {
  background: #1a1a2e;
  border-radius: 6px;
  padding: 10px;
  border-left: 3px solid #6c5ce7;
  margin-bottom: 12px;
}
.var-item {
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  font-size: 11px;
  line-height: 1.8;
}
.var-name { color: #ff79c6; }
.var-arrow { color: #636e72; }
.var-value { color: #81ecec; }
</style>
