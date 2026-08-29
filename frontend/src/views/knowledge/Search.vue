<template>
  <div class="knowledge-search-page">
    <!-- 模式切换 -->
    <el-card style="margin-bottom: 16px">
      <el-radio-group v-model="mode">
        <el-radio-button value="hybrid">图谱混合检索</el-radio-button>
        <el-radio-button value="agent">Agent 问答</el-radio-button>
      </el-radio-group>
    </el-card>

    <!-- 输入区 -->
    <el-card style="margin-bottom: 16px">
      <el-input
        v-model="query"
        :placeholder="mode === 'hybrid' ? '输入问题，检索知识图谱（向量 + 关键词）' : '输入问题，多 Agent 协作回答'"
        clearable
        @keyup.enter="handleSubmit"
      >
        <template #append>
          <el-button :loading="loading" @click="handleSubmit">查询</el-button>
        </template>
      </el-input>
    </el-card>

    <!-- 混合检索结果 -->
    <el-card v-if="mode === 'hybrid' && results.length" v-loading="loading">
      <template #header>
        <span>检索结果（{{ results.length }}）</span>
      </template>
      <el-timeline>
        <el-timeline-item v-for="r in results" :key="r.id" :timestamp="`score: ${(r.score * 100).toFixed(1)}%`">
          <div class="result-content">{{ r.content }}</div>
          <div v-if="r.source" class="result-source">来源：{{ r.source }}</div>
        </el-timeline-item>
      </el-timeline>
    </el-card>

    <!-- Agent 问答结果 -->
    <el-card v-if="mode === 'agent' && answer" v-loading="loading">
      <template #header>
        <span>回答<template v-if="sessionId">（会话 {{ sessionId }}）</template></span>
      </template>
      <div class="agent-answer">{{ answer }}</div>
    </el-card>

    <!-- 空状态 -->
    <el-card v-if="queried && ((mode === 'hybrid' && !results.length) || (mode === 'agent' && !answer))">
      <el-empty description="暂无结果" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { hybridSearch, agentQuery } from '@/api/graph'

/** 检索模式：graph 混合检索 / agent 问答 */
const mode = ref<'hybrid' | 'agent'>('hybrid')
const query = ref('')
const loading = ref(false)
/** 是否执行过查询（用于空状态展示） */
const queried = ref(false)

// 混合检索结果
interface ResultRow {
  id: string
  content: string
  score: number
  source: string | null
}
const results = ref<ResultRow[]>([])

// Agent 问答
const answer = ref('')
const sessionId = ref('')

/** 执行查询：按当前模式分发 */
async function handleSubmit() {
  const q = query.value.trim()
  if (!q) return

  loading.value = true
  queried.value = false
  results.value = []
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
    } else {
      const res = await agentQuery({ query: q, session_id: sessionId.value || undefined })
      answer.value = res.answer
      sessionId.value = res.session_id
    }
    queried.value = true
  } catch (err) {
    // 错误提示已由全局拦截器统一处理
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
