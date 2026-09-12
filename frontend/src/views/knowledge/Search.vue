<template>
  <div class="knowledge-search-page">
    <!-- 模式切换：默认走真实文档检索；图谱/Agent 端点已 deprecated，仅作兼容入口 -->
    <el-card style="margin-bottom: 16px">
      <el-radio-group v-model="mode">
        <el-radio-button value="docs">文档检索</el-radio-button>
        <el-radio-button value="hybrid">
          图谱混合检索
          <el-tag size="small" type="warning" style="margin-left: 4px">废弃</el-tag>
        </el-radio-button>
        <el-radio-button value="agent">
          Agent 问答
          <el-tag size="small" type="warning" style="margin-left: 4px">废弃</el-tag>
        </el-radio-button>
      </el-radio-group>
      <el-alert
        v-if="mode !== 'docs'"
        type="warning"
        :closable="false"
        show-icon
        style="margin-top: 12px"
        title="该模式调用已废弃的 graphs 内存占位端点，请改用文档检索（/api/v1/knowledge/search）"
      />
    </el-card>

    <!-- 输入区 -->
    <el-card style="margin-bottom: 16px">
      <el-input
        v-model="query"
        :placeholder="placeholder"
        clearable
        @keyup.enter="handleSubmit"
      >
        <template #append>
          <el-button :loading="loading" @click="handleSubmit">查询</el-button>
        </template>
      </el-input>
    </el-card>

    <!-- 检索结果 -->
    <el-card v-if="mode !== 'agent' && displayResults.length" v-loading="loading">
      <template #header>
        <span>检索结果（{{ displayResults.length }}）</span>
      </template>
      <el-timeline>
        <el-timeline-item
          v-for="r in displayResults"
          :key="r.id"
          :timestamp="`score: ${(r.score * 100).toFixed(1)}%`"
        >
          <div class="result-content">{{ r.content }}</div>
          <div v-if="r.source" class="result-source">来源：{{ r.source }}</div>
        </el-timeline-item>
      </el-timeline>
    </el-card>

    <!-- Agent 问答结果（兼容入口） -->
    <el-card v-if="mode === 'agent' && answer" v-loading="loading">
      <template #header>
        <span>回答<template v-if="sessionId">（会话 {{ sessionId }}）</template></span>
      </template>
      <div class="agent-answer">{{ answer }}</div>
    </el-card>

    <!-- 空状态 -->
    <el-card
      v-if="queried && ((mode !== 'agent' && !displayResults.length) || (mode === 'agent' && !answer))"
    >
      <el-empty description="暂无结果" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { hybridSearch, agentQuery } from '@/api/graph'
import { searchKnowledge } from '@/api/knowledge'

/** 默认文档检索；hybrid/agent 为废弃 graphs 端点的兼容入口 */
const mode = ref<'docs' | 'hybrid' | 'agent'>('docs')
const query = ref('')
const loading = ref(false)
const queried = ref(false)

interface ResultRow {
  id: string
  content: string
  score: number
  source: string | null
}
const results = ref<ResultRow[]>([])
const docResults = ref<ResultRow[]>([])
const answer = ref('')
const sessionId = ref('')

const placeholder = computed(() => {
  if (mode.value === 'agent') return '输入问题，多 Agent 协作回答（废弃端点）'
  if (mode.value === 'hybrid') return '输入问题，检索知识图谱（废弃端点）'
  return '输入问题，检索知识库文档'
})

const displayResults = computed(() =>
  mode.value === 'hybrid' ? results.value : docResults.value
)

async function handleSubmit() {
  const q = query.value.trim()
  if (!q) return

  loading.value = true
  queried.value = false
  results.value = []
  docResults.value = []
  answer.value = ''
  try {
    if (mode.value === 'hybrid') {
      const res = await hybridSearch({ query: q, top_k: 10 })
      results.value = res.results.map((r) => ({
        id: r.id,
        content: r.content,
        score: r.score,
        source: r.source
      }))
    } else if (mode.value === 'docs') {
      const res = await searchKnowledge({ query: q, top_k: 10 })
      docResults.value = res.results.map((r) => ({
        id: String(r.chunk_id),
        content: r.content,
        score: r.similarity,
        source: r.doc_title
      }))
    } else {
      const res = await agentQuery({ query: q, session_id: sessionId.value || undefined })
      answer.value = res.answer
      sessionId.value = res.session_id
    }
    queried.value = true
  } catch (err) {
    console.error('知识检索失败:', err)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.knowledge-search-page {
  padding: 20px;
}
.result-content {
  white-space: pre-wrap;
  line-height: 1.6;
}
.result-source {
  margin-top: 4px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.agent-answer {
  white-space: pre-wrap;
  line-height: 1.8;
}
</style>
