<template>
  <div class="agent-child-calls" v-if="log?.child_calls?.length">
    <div class="section-title">🔧 子调用记录</div>
    <div class="call-list">
      <div class="call-item" v-for="(call, index) in log.child_calls" :key="index">
        <div class="call-header">
          <span :class="['call-type-badge', `type-${call.call_type}`]">{{ call.call_type.toUpperCase() }}</span>
          <span class="call-name">{{ call.name }}</span>
          <span class="call-meta">{{ formatCallMeta(call) }}</span>
        </div>
        <div class="call-detail" v-if="expandedIndex === index">
          <div class="call-io" v-if="call.input">
            <div class="io-label">Input:</div>
            <pre class="io-content">{{ truncate(call.input, 500) }}</pre>
          </div>
          <div class="call-io" v-if="call.output">
            <div class="io-label">Output:</div>
            <pre class="io-content">{{ truncate(call.output, 500) }}</pre>
          </div>
        </div>
        <el-button link size="small" @click="toggleExpand(index)" class="expand-btn">
          {{ expandedIndex === index ? '收起' : '展开' }}
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { AgentLog, ChildCallRecord } from '@/types/task'

/**
 * Agent 子调用记录列表。
 * 展示 LLM/TOOL/RAG 三种类型的子调用。
 */

defineProps<{
  log: AgentLog | null
}>()

const expandedIndex = ref<number | null>(null)

function toggleExpand(index: number) {
  expandedIndex.value = expandedIndex.value === index ? null : index
}

function formatCallMeta(call: ChildCallRecord): string {
  const parts: string[] = []
  if (call.latency_ms) parts.push(`${(call.latency_ms / 1000).toFixed(1)}s`)
  if (call.tokens) parts.push(`${call.tokens} tok`)
  return parts.length ? parts.join(' · ') : ''
}

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
.call-list {
  background: #1a1a2e;
  border-radius: 6px;
  overflow: hidden;
  margin-bottom: 12px;
}
.call-item {
  padding: 8px 10px;
  border-bottom: 1px solid #2d2d4e;
}
.call-item:last-child { border-bottom: none; }
.call-header {
  display: flex;
  align-items: center;
  gap: 6px;
}
.call-type-badge {
  font-size: 9px;
  padding: 1px 5px;
  border-radius: 3px;
  color: #fff;
  font-weight: 600;
}
.type-llm { background: #1f6feb; }
.type-tool { background: #e17055; }
.type-rag { background: #00cec9; }
.call-name {
  color: #c9d1d9;
  font-size: 11px;
  flex: 1;
}
.call-meta {
  color: #8b949e;
  font-size: 10px;
}
.call-detail {
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px solid #2d2d4e;
}
.call-io { margin-bottom: 4px; }
.io-label { color: #636e72; font-size: 9px; }
.io-content {
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  font-size: 10px;
  color: #c9d1d9;
  margin: 2px 0 0 0;
  white-space: pre-wrap;
}
.expand-btn {
  font-size: 10px;
  color: #58a6ff;
  margin-top: 2px;
}
</style>
