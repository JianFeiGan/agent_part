<template>
  <div class="agent-detail-panel">
    <!-- 无选中节点 -->
    <div v-if="!store.selectedAgentLog" class="empty-state">
      <div class="empty-icon">🎯</div>
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
          <div class="agent-meta">
            <span class="agent-role" :style="{ color: nodeColor }">{{ nodeRole }}</span>
            <span class="status-dot" :class="store.selectedAgentLog.status" />
            <span class="agent-status">{{ statusLabel }}</span>
            <span v-if="store.selectedAgentLog.latency_ms" class="agent-latency">
              {{ (store.selectedAgentLog.latency_ms / 1000).toFixed(1) }}s
            </span>
          </div>
        </div>
      </div>

      <!-- 指标栏 -->
      <div class="metrics-bar">
        <div class="metric" v-for="m in metrics" :key="m.label">
          <span class="metric-val" :class="m.cls">{{ m.value }}</span>
          <span class="metric-lbl">{{ m.label }}</span>
        </div>
      </div>

      <!-- Tab 切换 -->
      <div class="tab-bar">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          class="tab-btn"
          :class="{ active: activeTab === tab.key }"
          @click="activeTab = tab.key"
        >
          <span class="tab-icon">{{ tab.icon }}</span>
          <span class="tab-label">{{ tab.label }}</span>
          <span v-if="tab.count > 0" class="tab-count">{{ tab.count }}</span>
        </button>
      </div>

      <!-- Tab 内容 -->
      <div class="tab-content">
        <!-- 概览 Tab -->
        <div v-if="activeTab === 'overview'" class="tab-pane">
          <div class="info-section">
            <div class="info-row">
              <span class="info-key">时间范围</span>
              <span class="info-val">{{ formatTimeRange(store.selectedAgentLog) }}</span>
            </div>
            <div class="info-row" v-if="store.upstreamLabels.length">
              <span class="info-key">数据来源</span>
              <span class="info-val accent-orange">{{ store.upstreamLabels.join(' → ') }}</span>
            </div>
            <div class="info-row" v-if="store.downstreamLabels.length">
              <span class="info-key">传递去向</span>
              <span class="info-val accent-cyan">{{ store.downstreamLabels.join(' → ') }}</span>
            </div>
            <div class="info-row" v-if="store.selectedAgentLog.output_summary">
              <span class="info-key">输出摘要</span>
              <span class="info-val">{{ store.selectedAgentLog.output_summary }}</span>
            </div>
            <div class="info-row" v-if="store.selectedAgentLog.message && store.selectedAgentLog.status === 'failed'">
              <span class="info-key">错误信息</span>
              <span class="info-val accent-red">{{ store.selectedAgentLog.message }}</span>
            </div>
          </div>

          <!-- 输入输出快览 -->
          <div class="io-peek" v-if="store.selectedAgentLog.input_data || store.selectedAgentLog.output_data">
            <div class="io-peek-item" v-if="store.selectedAgentLog.input_data" @click="activeTab = 'io'">
              <div class="io-peek-label">📥 输入 <span class="io-peek-src">from {{ store.upstreamLabels.join(', ') }}</span></div>
              <pre class="io-peek-code">{{ formatJson(store.selectedAgentLog.input_data, 3) }}</pre>
              <div class="io-peek-more">查看完整输入 →</div>
            </div>
            <div class="io-peek-item" v-if="store.selectedAgentLog.output_data" @click="activeTab = 'io'">
              <div class="io-peek-label">📤 输出 <span class="io-peek-src">→ {{ store.downstreamLabels.join(', ') }}</span></div>
              <pre class="io-peek-code">{{ formatJson(store.selectedAgentLog.output_data, 3) }}</pre>
              <div class="io-peek-more">查看完整输出 →</div>
            </div>
          </div>
        </div>

        <!-- 提示词 Tab -->
        <div v-if="activeTab === 'prompt'" class="tab-pane">
          <div class="prompt-empty" v-if="!store.selectedAgentLog.prompt_template && !store.selectedAgentLog.prompt_variables">
            <div class="empty-hint">此 Agent 暂无提示词记录</div>
            <div class="empty-sub">提示词轨迹仅在 LLM 调用成功后记录</div>
          </div>
          <template v-else>
            <!-- System Prompt -->
            <div class="prompt-section" v-if="store.selectedAgentLog.prompt_template">
              <div class="prompt-section-header">
                <span class="prompt-section-icon">📝</span>
                System Prompt
                <button class="copy-btn" @click="copyText(store.selectedAgentLog.prompt_template ?? '')" title="复制">⎘</button>
              </div>
              <div class="prompt-code-block">
                <pre>{{ store.selectedAgentLog.prompt_template }}</pre>
              </div>
            </div>
            <!-- Variables -->
            <div class="prompt-section" v-if="store.selectedAgentLog.prompt_variables && Object.keys(store.selectedAgentLog.prompt_variables).length">
              <div class="prompt-section-header">
                <span class="prompt-section-icon">🔤</span>
                变量替换 ({{ Object.keys(store.selectedAgentLog.prompt_variables).length }})
              </div>
              <div class="var-table">
                <div class="var-row" v-for="(value, key) in store.selectedAgentLog.prompt_variables" :key="String(key)">
                  <div class="var-key">{{ String(key) }}</div>
                  <div class="var-arrow-col">→</div>
                  <div class="var-value-col">
                    <pre>{{ formatVarValue(value) }}</pre>
                  </div>
                </div>
              </div>
            </div>
          </template>
        </div>

        <!-- 输入/输出 Tab -->
        <div v-if="activeTab === 'io'" class="tab-pane">
          <div class="io-empty" v-if="!store.selectedAgentLog.input_data && !store.selectedAgentLog.output_data">
            <div class="empty-hint">此 Agent 暂无输入输出记录</div>
            <div class="empty-sub">数据快照在 Agent 完成后记录</div>
          </div>
          <template v-else>
            <div class="io-section" v-if="store.selectedAgentLog.input_data">
              <div class="io-section-header">
                <span class="io-section-icon">📥</span>
                输入参数
                <span class="io-flow-tag from" v-if="store.upstreamLabels.length">from {{ store.upstreamLabels.join(', ') }}</span>
                <button class="copy-btn" @click="copyText(JSON.stringify(store.selectedAgentLog.input_data, null, 2))" title="复制">⎘</button>
              </div>
              <div class="io-code-block input-block">
                <pre>{{ formatJson(store.selectedAgentLog.input_data) }}</pre>
              </div>
            </div>
            <div class="io-section" v-if="store.selectedAgentLog.output_data">
              <div class="io-section-header">
                <span class="io-section-icon">📤</span>
                输出数据
                <span class="io-flow-tag to" v-if="store.downstreamLabels.length">→ {{ store.downstreamLabels.join(', ') }}</span>
                <button class="copy-btn" @click="copyText(JSON.stringify(store.selectedAgentLog.output_data, null, 2))" title="复制">⎘</button>
              </div>
              <div class="io-code-block output-block">
                <pre>{{ formatJson(store.selectedAgentLog.output_data) }}</pre>
              </div>
            </div>
          </template>
        </div>

        <!-- 子调用 Tab -->
        <div v-if="activeTab === 'calls'" class="tab-pane">
          <div class="calls-empty" v-if="!store.selectedAgentLog.child_calls?.length">
            <div class="empty-hint">此 Agent 暂无子调用记录</div>
            <div class="empty-sub">LLM/工具/RAG 调用将在执行后记录</div>
          </div>
          <div class="call-list" v-else>
            <div
              class="call-card"
              v-for="(call, index) in store.selectedAgentLog.child_calls"
              :key="index"
              :class="{ expanded: expandedCallIndex === index }"
            >
              <div class="call-card-header" @click="toggleCallExpand(index)">
                <span class="call-type-dot" :class="call.call_type" />
                <span class="call-type-label">{{ call.call_type.toUpperCase() }}</span>
                <span class="call-name">{{ call.name }}</span>
                <span class="call-meta">{{ formatCallMeta(call) }}</span>
                <span class="call-expand-icon">{{ expandedCallIndex === index ? '▾' : '▸' }}</span>
              </div>
              <div class="call-card-body" v-if="expandedCallIndex === index">
                <div class="call-io-block" v-if="call.input">
                  <div class="call-io-label">Input</div>
                  <pre class="call-io-code">{{ call.input }}</pre>
                </div>
                <div class="call-io-block" v-if="call.output">
                  <div class="call-io-label">Output</div>
                  <pre class="call-io-code">{{ call.output }}</pre>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useWorkbenchStore } from '@/stores/workbench'
import { NODE_MAP } from '@/workflow/topology'
import { AgentLogStatusLabels } from '@/types/task'
import type { AgentLog, ChildCallRecord } from '@/types/task'

/**
 * Agent 详情面板。
 * DevTools Inspector 风格：Tab 切换不同信息维度。
 */

const store = useWorkbenchStore()
const activeTab = ref<'overview' | 'prompt' | 'io' | 'calls'>('overview')
const expandedCallIndex = ref<number | null>(null)

const nodeDef = computed(() => {
  const id = store.selectedAgentId
  return id ? NODE_MAP.get(id) : undefined
})

const nodeColor = computed(() => nodeDef.value?.color ?? '#636e72')
const nodeRole = computed(() => nodeDef.value?.role ?? '')

const nodeEmoji = computed(() => {
  const id = store.selectedAgentId
  const emojiMap: Record<string, string> = {
    orchestrator: '⚡', requirement_analyzer: '🔍', creative_planner: '💡',
    visual_designer: '🎨', image_generator: '🖼', video_generator: '🎬', quality_reviewer: '✅',
  }
  return emojiMap[id ?? ''] ?? '🤖'
})

const statusLabel = computed(() => {
  const status = store.selectedAgentLog?.status
  return status ? (AgentLogStatusLabels[status as keyof typeof AgentLogStatusLabels] ?? status) : ''
})

const metrics = computed(() => {
  const log = store.selectedAgentLog
  if (!log) return []
  return [
    { label: 'Model', value: log.model_name ?? '-', cls: '' },
    { label: 'Provider', value: log.provider ?? '-', cls: '' },
    { label: 'Tokens', value: log.total_tokens ? `${log.input_tokens}/${log.output_tokens}` : '0', cls: '' },
    { label: 'Cost', value: log.cost_cny ? `¥${log.cost_cny.toFixed(3)}` : '-', cls: 'val-yellow' },
  ]
})

const tabs = computed(() => {
  const log = store.selectedAgentLog
  return [
    { key: 'overview' as const, icon: '📋', label: '概览', count: 0 },
    { key: 'prompt' as const, icon: '💬', label: '提示词', count: log?.prompt_template ? 1 : 0 },
    { key: 'io' as const, icon: '🔄', label: '输入输出', count: (log?.input_data ? 1 : 0) + (log?.output_data ? 1 : 0) },
    { key: 'calls' as const, icon: '🔧', label: '子调用', count: log?.child_calls?.length ?? 0 },
  ]
})

function toggleCallExpand(index: number) {
  expandedCallIndex.value = expandedCallIndex.value === index ? null : index
}

function formatJson(data: Record<string, unknown> | null, maxLines?: number): string {
  if (!data) return ''
  const json = JSON.stringify(data, null, 2)
  if (maxLines) {
    const lines = json.split('\n')
    if (lines.length > maxLines) {
      return lines.slice(0, maxLines).join('\n') + `\n  ... 共 ${lines.length} 行`
    }
  }
  return json
}

function formatVarValue(value: unknown): string {
  if (typeof value === 'string') return value
  return JSON.stringify(value, null, 2)
}

function formatTimeRange(log: AgentLog): string {
  const fmt = (t: string | null) => t ? t.replace('T', ' ').substring(0, 19) : '-'
  return `${fmt(log.start_time)} → ${fmt(log.end_time)}`
}

function formatCallMeta(call: ChildCallRecord): string {
  const parts: string[] = []
  if (call.latency_ms) parts.push(`${(call.latency_ms / 1000).toFixed(1)}s`)
  if (call.tokens) parts.push(`${call.tokens} tok`)
  return parts.length ? parts.join(' · ') : ''
}

function copyText(text: string) {
  navigator.clipboard.writeText(text).catch(() => {})
}
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=DM+Sans:wght@400;500;600;700&display=swap');

.agent-detail-panel {
  padding: 0;
  overflow-y: auto;
  height: 100%;
  background: #0d1117;
  font-family: 'DM Sans', -apple-system, sans-serif;
  color: #c9d1d9;
}

/* ========== 空状态 ========== */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 300px;
  gap: 8px;
}
.empty-icon { font-size: 32px; opacity: 0.5; }
.empty-state p { color: #484f58; font-size: 14px; }

/* ========== Agent 头部 ========== */
.agent-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: linear-gradient(135deg, #161b22 0%, #1c2333 100%);
  border-bottom: 1px solid #21262d;
}
.agent-icon {
  width: 40px; height: 40px;
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 18px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.3);
}
.agent-name {
  font-size: 15px;
  font-weight: 700;
  color: #f0f6fc;
  letter-spacing: -0.3px;
}
.agent-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 2px;
}
.agent-role { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
.status-dot {
  width: 6px; height: 6px; border-radius: 50%;
  margin: 0 2px;
}
.status-dot.completed { background: #3fb950; box-shadow: 0 0 4px #3fb950; }
.status-dot.running { background: #58a6ff; animation: pulse-dot 1.5s infinite; }
.status-dot.failed { background: #f85149; }
.status-dot.pending { background: #484f58; }
.agent-status { font-size: 11px; color: #8b949e; }
.agent-latency { font-size: 11px; color: #58a6ff; margin-left: 4px; }
@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* ========== 指标栏 ========== */
.metrics-bar {
  display: flex;
  gap: 0;
  padding: 0 16px;
  background: #0d1117;
  border-bottom: 1px solid #21262d;
}
.metric {
  flex: 1;
  padding: 10px 0;
  text-align: center;
  border-right: 1px solid #21262d;
}
.metric:last-child { border-right: none; }
.metric-val {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #c9d1d9;
  font-family: 'JetBrains Mono', monospace;
}
.metric-val.val-yellow { color: #d29922; }
.metric-lbl {
  display: block;
  font-size: 9px;
  color: #484f58;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-top: 2px;
}

/* ========== Tab 栏 ========== */
.tab-bar {
  display: flex;
  gap: 0;
  padding: 0 12px;
  background: #0d1117;
  border-bottom: 1px solid #21262d;
}
.tab-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 10px 12px;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: #8b949e;
  font-size: 12px;
  font-family: 'DM Sans', sans-serif;
  cursor: pointer;
  transition: all 0.15s;
}
.tab-btn:hover { color: #c9d1d9; background: #161b22; }
.tab-btn.active {
  color: #f0f6fc;
  border-bottom-color: #58a6ff;
}
.tab-icon { font-size: 13px; }
.tab-label { font-weight: 600; }
.tab-count {
  font-size: 10px;
  font-weight: 700;
  background: #21262d;
  color: #8b949e;
  padding: 0 5px;
  border-radius: 8px;
  min-width: 16px;
  text-align: center;
  line-height: 16px;
}
.tab-btn.active .tab-count {
  background: #1f6feb;
  color: #fff;
}

/* ========== Tab 内容 ========== */
.tab-content {
  padding: 0;
}
.tab-pane {
  padding: 16px;
}

/* ========== 概览 Tab ========== */
.info-section {
  margin-bottom: 16px;
}
.info-row {
  display: flex;
  padding: 8px 0;
  border-bottom: 1px solid #161b22;
  gap: 12px;
}
.info-key {
  flex-shrink: 0;
  width: 70px;
  font-size: 11px;
  color: #484f58;
  font-weight: 600;
}
.info-val {
  font-size: 12px;
  color: #8b949e;
  word-break: break-all;
  line-height: 1.5;
}
.info-val.accent-orange { color: #e17055; }
.info-val.accent-cyan { color: #3fb950; }
.info-val.accent-red { color: #f85149; }

/* IO 快览 */
.io-peek {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.io-peek-item {
  background: #161b22;
  border-radius: 8px;
  padding: 12px;
  cursor: pointer;
  transition: background 0.15s;
  border: 1px solid #21262d;
}
.io-peek-item:hover {
  background: #1c2333;
  border-color: #30363d;
}
.io-peek-label {
  font-size: 11px;
  font-weight: 600;
  color: #8b949e;
  margin-bottom: 6px;
}
.io-peek-src {
  font-size: 10px;
  color: #484f58;
  font-weight: 400;
}
.io-peek-code {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  color: #636e72;
  margin: 0;
  white-space: pre-wrap;
  max-height: 60px;
  overflow: hidden;
  line-height: 1.5;
}
.io-peek-more {
  font-size: 10px;
  color: #58a6ff;
  margin-top: 6px;
  font-weight: 600;
}

/* ========== 提示词 Tab ========== */
.prompt-empty, .io-empty, .calls-empty {
  text-align: center;
  padding: 32px 16px;
}
.empty-hint {
  font-size: 13px;
  color: #484f58;
  margin-bottom: 4px;
}
.empty-sub {
  font-size: 11px;
  color: #30363d;
}

.prompt-section {
  margin-bottom: 16px;
}
.prompt-section-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #c9d1d9;
  margin-bottom: 8px;
}
.prompt-section-icon { font-size: 14px; }
.copy-btn {
  margin-left: auto;
  background: none;
  border: 1px solid #21262d;
  color: #484f58;
  font-size: 13px;
  padding: 2px 6px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s;
}
.copy-btn:hover { color: #c9d1d9; border-color: #30363d; background: #161b22; }

.prompt-code-block {
  background: #161b22;
  border-radius: 8px;
  padding: 14px;
  border: 1px solid #21262d;
  overflow-x: auto;
}
.prompt-code-block pre {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  line-height: 1.7;
  color: #a29bfe;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}

/* 变量表 */
.var-table {
  background: #161b22;
  border-radius: 8px;
  border: 1px solid #21262d;
  overflow: hidden;
}
.var-row {
  display: flex;
  padding: 10px 14px;
  border-bottom: 1px solid #21262d;
  gap: 12px;
  align-items: flex-start;
}
.var-row:last-child { border-bottom: none; }
.var-key {
  flex-shrink: 0;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 600;
  color: #ff79c6;
  min-width: 80px;
  padding-top: 1px;
}
.var-arrow-col {
  color: #30363d;
  font-size: 12px;
  padding-top: 1px;
}
.var-value-col {
  flex: 1;
  min-width: 0;
}
.var-value-col pre {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  line-height: 1.6;
  color: #81ecec;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}

/* ========== 输入输出 Tab ========== */
.io-section {
  margin-bottom: 16px;
}
.io-section-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #c9d1d9;
  margin-bottom: 8px;
}
.io-section-icon { font-size: 14px; }
.io-flow-tag {
  font-size: 10px;
  font-weight: 400;
  padding: 1px 6px;
  border-radius: 4px;
}
.io-flow-tag.from { color: #e17055; background: rgba(225,112,85,0.1); }
.io-flow-tag.to { color: #3fb950; background: rgba(63,185,80,0.1); }

.io-code-block {
  background: #161b22;
  border-radius: 8px;
  padding: 14px;
  border: 1px solid #21262d;
  overflow-x: auto;
}
.io-code-block pre {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  line-height: 1.6;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}
.input-block pre { color: #c9d1d9; }
.output-block pre { color: #81ecec; }

/* ========== 子调用 Tab ========== */
.call-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.call-card {
  background: #161b22;
  border-radius: 8px;
  border: 1px solid #21262d;
  overflow: hidden;
  transition: border-color 0.15s;
}
.call-card.expanded { border-color: #30363d; }
.call-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  cursor: pointer;
  transition: background 0.15s;
}
.call-card-header:hover { background: #1c2333; }
.call-type-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.call-type-dot.llm { background: #1f6feb; box-shadow: 0 0 4px rgba(31,111,235,0.4); }
.call-type-dot.tool { background: #e17055; box-shadow: 0 0 4px rgba(225,112,85,0.4); }
.call-type-dot.rag { background: #3fb950; box-shadow: 0 0 4px rgba(63,185,80,0.4); }
.call-type-label {
  font-size: 9px;
  font-weight: 700;
  color: #484f58;
  letter-spacing: 0.5px;
  flex-shrink: 0;
}
.call-name {
  font-size: 12px;
  font-weight: 500;
  color: #c9d1d9;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.call-meta {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  color: #484f58;
  flex-shrink: 0;
}
.call-expand-icon {
  color: #484f58;
  font-size: 10px;
  flex-shrink: 0;
}
.call-card-body {
  border-top: 1px solid #21262d;
  padding: 12px 14px;
}
.call-io-block {
  margin-bottom: 10px;
}
.call-io-block:last-child { margin-bottom: 0; }
.call-io-label {
  font-size: 10px;
  font-weight: 600;
  color: #484f58;
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.call-io-code {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  line-height: 1.5;
  color: #8b949e;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  background: #0d1117;
  padding: 10px;
  border-radius: 6px;
  max-height: 300px;
  overflow-y: auto;
}
</style>
