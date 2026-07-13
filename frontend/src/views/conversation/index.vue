<template>
  <div class="conversation-page">
    <!-- 顶部统计卡片 -->
    <div class="overview-cards">
      <div class="overview-card overview-card--tokens">
        <div class="overview-card__glow"></div>
        <div class="overview-card__content">
          <div class="overview-card__header">
            <el-icon :size="18"><Coin /></el-icon>
            <span>总 Token 消耗</span>
          </div>
          <div class="overview-card__value">{{ formatNumber(overview.stats.total_tokens) }}</div>
          <div class="overview-card__sub">
            输入 {{ formatNumber(overview.stats.total_input_tokens) }} / 输出 {{ formatNumber(overview.stats.total_output_tokens) }}
          </div>
        </div>
      </div>

      <div class="overview-card overview-card--cost">
        <div class="overview-card__glow"></div>
        <div class="overview-card__content">
          <div class="overview-card__header">
            <el-icon :size="18"><Wallet /></el-icon>
            <span>总费用</span>
          </div>
          <div class="overview-card__value">¥{{ formatMoney(overview.stats.total_cost_cny) }}</div>
          <div class="overview-card__sub">
            ${{ formatMoney(overview.stats.total_cost_usd) }} USD
          </div>
        </div>
      </div>

      <div class="overview-card overview-card--calls">
        <div class="overview-card__glow"></div>
        <div class="overview-card__content">
          <div class="overview-card__header">
            <el-icon :size="18"><Connection /></el-icon>
            <span>调用次数</span>
          </div>
          <div class="overview-card__value">{{ formatNumber(overview.stats.total_count) }}</div>
          <div class="overview-card__sub">
            成功 {{ overview.stats.success_count }} / 失败 {{ overview.stats.failed_count }}
          </div>
        </div>
      </div>

      <div class="overview-card overview-card--latency">
        <div class="overview-card__glow"></div>
        <div class="overview-card__content">
          <div class="overview-card__header">
            <el-icon :size="18"><Timer /></el-icon>
            <span>平均延迟</span>
          </div>
          <div class="overview-card__value">{{ overview.stats.avg_latency_ms ?? '-' }}<small>ms</small></div>
          <div class="overview-card__sub">响应时间</div>
        </div>
      </div>
    </div>

    <!-- Tab 区域 -->
    <div class="tab-section">
      <el-tabs v-model="activeTab" class="conversation-tabs">
        <!-- 会话记录列表 -->
        <el-tab-pane label="会话记录" name="records">
          <div class="filter-bar">
            <el-form :inline="true" @submit.prevent="loadRecords">
              <el-form-item>
                <el-input
                  v-model="filters.keyword"
                  placeholder="搜索会话内容..."
                  clearable
                  style="width: 260px"
                  @keyup.enter="handleSearch"
                >
                  <template #prefix>
                    <el-icon><Search /></el-icon>
                  </template>
                </el-input>
              </el-form-item>
              <el-form-item>
                <el-select v-model="filters.search_field" placeholder="搜索范围" style="width: 120px">
                  <el-option label="全部" value="both" />
                  <el-option label="输入内容" value="input" />
                  <el-option label="输出内容" value="output" />
                </el-select>
              </el-form-item>
              <el-form-item>
                <el-select v-model="filters.agent_name" placeholder="Agent" clearable style="width: 150px">
                  <el-option v-for="a in agentOptions" :key="a" :label="a" :value="a" />
                </el-select>
              </el-form-item>
              <el-form-item>
                <el-select v-model="filters.model_name" placeholder="模型" clearable style="width: 140px">
                  <el-option v-for="m in modelOptions" :key="m" :label="m" :value="m" />
                </el-select>
              </el-form-item>
              <el-form-item>
                <el-select v-model="filters.status" placeholder="状态" clearable style="width: 100px">
                  <el-option label="成功" value="success" />
                  <el-option label="失败" value="failed" />
                  <el-option label="超时" value="timeout" />
                </el-select>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" :loading="recordsLoading" @click="handleSearch">
                  <el-icon><Search /></el-icon>
                  搜索
                </el-button>
              </el-form-item>
            </el-form>
          </div>

          <el-table
            :data="records"
            style="width: 100%"
            class="records-table"
            v-loading="recordsLoading"
            @row-click="showDetail"
            highlight-current-row
          >
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column prop="agent_name" label="Agent" width="150">
              <template #default="{ row }">
                <span class="agent-badge">{{ row.agent_name || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="model_name" label="模型" width="130">
              <template #default="{ row }">
                <span class="model-text">{{ row.model_name }}</span>
              </template>
            </el-table-column>
            <el-table-column label="Token" width="140">
              <template #default="{ row }">
                <div class="token-cell">
                  <span class="token-total">{{ formatNumber(row.total_tokens) }}</span>
                  <span class="token-detail">↑{{ formatNumber(row.input_tokens) }} ↓{{ formatNumber(row.output_tokens) }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="费用" width="110">
              <template #default="{ row }">
                <span class="cost-text">¥{{ formatMoney(row.cost_cny) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="latency_ms" label="延迟" width="90">
              <template #default="{ row }">
                <span :class="['latency-text', getLatencyClass(row.latency_ms)]">
                  {{ row.latency_ms ?? '-' }}ms
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="80">
              <template #default="{ row }">
                <el-tag
                  :type="statusTagType(row.status)"
                  size="small"
                  effect="dark"
                  round
                >
                  {{ statusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="时间" width="170">
              <template #default="{ row }">
                <span class="time-text">{{ formatTime(row.created_at) }}</span>
              </template>
            </el-table-column>
          </el-table>

          <div class="pagination-wrap" v-if="recordsTotal > 0">
            <el-pagination
              v-model:current-page="currentPage"
              v-model:page-size="pageSize"
              :total="recordsTotal"
              :page-sizes="[20, 50, 100]"
              layout="total, sizes, prev, pager, next"
              @change="loadRecords"
            />
          </div>
        </el-tab-pane>

        <!-- 使用量分析 -->
        <el-tab-pane label="使用分析" name="analysis">
          <div class="analysis-grid">
            <!-- 按模型 -->
            <div class="analysis-card">
              <h4 class="analysis-card__title">按模型分布</h4>
              <div class="breakdown-list">
                <div
                  v-for="item in overview.by_model"
                  :key="item.model_name + item.provider"
                  class="breakdown-item"
                >
                  <div class="breakdown-item__header">
                    <span class="breakdown-item__name">{{ item.model_name }}</span>
                    <span class="breakdown-item__provider">{{ item.provider }}</span>
                  </div>
                  <div class="breakdown-item__bar-wrap">
                    <div
                      class="breakdown-item__bar"
                      :style="{ width: getBarWidth(item.total_tokens, maxModelTokens) + '%' }"
                    ></div>
                  </div>
                  <div class="breakdown-item__stats">
                    <span>{{ formatNumber(item.call_count) }} 次调用</span>
                    <span>{{ formatNumber(item.total_tokens) }} tokens</span>
                    <span>¥{{ formatMoney(item.total_cost_cny) }}</span>
                  </div>
                </div>
                <el-empty v-if="!overview.by_model.length" description="暂无数据" :image-size="60" />
              </div>
            </div>

            <!-- 按 Agent -->
            <div class="analysis-card">
              <h4 class="analysis-card__title">按 Agent 分布</h4>
              <div class="breakdown-list">
                <div
                  v-for="item in overview.by_agent"
                  :key="item.agent_name"
                  class="breakdown-item"
                >
                  <div class="breakdown-item__header">
                    <span class="breakdown-item__name">{{ item.agent_name || '未知' }}</span>
                  </div>
                  <div class="breakdown-item__bar-wrap">
                    <div
                      class="breakdown-item__bar breakdown-item__bar--agent"
                      :style="{ width: getBarWidth(item.total_tokens, maxAgentTokens) + '%' }"
                    ></div>
                  </div>
                  <div class="breakdown-item__stats">
                    <span>{{ formatNumber(item.call_count) }} 次调用</span>
                    <span>{{ formatNumber(item.total_tokens) }} tokens</span>
                    <span>¥{{ formatMoney(item.total_cost_cny) }}</span>
                  </div>
                </div>
                <el-empty v-if="!overview.by_agent.length" description="暂无数据" :image-size="60" />
              </div>
            </div>
          </div>
        </el-tab-pane>

        <!-- 费用预算 -->
        <el-tab-pane label="费用预算" name="budget">
          <div class="budget-section">
            <div class="budget-config">
              <el-form :inline="true">
                <el-form-item label="日预算 (¥)">
                  <el-input-number v-model="budgetForm.daily_budget_cny" :min="1" :step="50" style="width: 140px" />
                </el-form-item>
                <el-form-item label="月预算 (¥)">
                  <el-input-number v-model="budgetForm.monthly_budget_cny" :min="1" :step="500" style="width: 140px" />
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" :loading="budgetLoading" @click="loadBudget">计算</el-button>
                </el-form-item>
              </el-form>
            </div>

            <div v-if="budget" class="budget-cards">
              <!-- 日预算 -->
              <div class="budget-card">
                <div class="budget-card__header">
                  <span class="budget-card__period">今日</span>
                  <span class="budget-card__date">{{ todayStr }}</span>
                </div>
                <div class="budget-card__progress">
                  <el-progress
                    type="dashboard"
                    :percentage="Math.min(budget.daily_usage_percent, 100)"
                    :color="getBudgetColor(budget.daily_usage_percent)"
                    :stroke-width="8"
                    :width="120"
                  >
                    <template #default="{ percentage }">
                      <span class="budget-percent">{{ percentage.toFixed(1) }}%</span>
                    </template>
                  </el-progress>
                </div>
                <div class="budget-card__details">
                  <div class="budget-detail">
                    <span class="budget-detail__label">已用</span>
                    <span class="budget-detail__value">¥{{ formatMoney(budget.today_cost_cny) }}</span>
                  </div>
                  <div class="budget-detail">
                    <span class="budget-detail__label">剩余</span>
                    <span class="budget-detail__value">¥{{ formatMoney(budget.daily_remaining_cny) }}</span>
                  </div>
                  <div class="budget-detail">
                    <span class="budget-detail__label">调用</span>
                    <span class="budget-detail__value">{{ budget.today_call_count }} 次</span>
                  </div>
                </div>
              </div>

              <!-- 月预算 -->
              <div class="budget-card">
                <div class="budget-card__header">
                  <span class="budget-card__period">本月</span>
                  <span class="budget-card__date">{{ monthStr }}</span>
                </div>
                <div class="budget-card__progress">
                  <el-progress
                    type="dashboard"
                    :percentage="Math.min(budget.monthly_usage_percent, 100)"
                    :color="getBudgetColor(budget.monthly_usage_percent)"
                    :stroke-width="8"
                    :width="120"
                  >
                    <template #default="{ percentage }">
                      <span class="budget-percent">{{ percentage.toFixed(1) }}%</span>
                    </template>
                  </el-progress>
                </div>
                <div class="budget-card__details">
                  <div class="budget-detail">
                    <span class="budget-detail__label">已用</span>
                    <span class="budget-detail__value">¥{{ formatMoney(budget.month_cost_cny) }}</span>
                  </div>
                  <div class="budget-detail">
                    <span class="budget-detail__label">剩余</span>
                    <span class="budget-detail__value">¥{{ formatMoney(budget.monthly_remaining_cny) }}</span>
                  </div>
                  <div class="budget-detail">
                    <span class="budget-detail__label">预估月费</span>
                    <span class="budget-detail__value">¥{{ formatMoney(budget.projected_month_cost_cny) }}</span>
                  </div>
                </div>
              </div>
            </div>

            <el-empty v-else-if="!budgetLoading" description="点击计算查看预算分析" :image-size="80" />
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <!-- 详情抽屉 -->
    <el-drawer
      v-model="detailVisible"
      title="会话详情"
      direction="rtl"
      size="520px"
      class="detail-drawer"
    >
      <template v-if="detailData">
        <div class="detail-section">
          <h4>基本信息</h4>
          <div class="detail-grid">
            <div class="detail-field">
              <span class="detail-field__label">ID</span>
              <span class="detail-field__value">{{ detailData.id }}</span>
            </div>
            <div class="detail-field">
              <span class="detail-field__label">Agent</span>
              <span class="detail-field__value">{{ detailData.agent_name || '-' }}</span>
            </div>
            <div class="detail-field">
              <span class="detail-field__label">模型</span>
              <span class="detail-field__value">{{ detailData.model_name }}</span>
            </div>
            <div class="detail-field">
              <span class="detail-field__label">提供商</span>
              <span class="detail-field__value">{{ detailData.provider }}</span>
            </div>
            <div class="detail-field">
              <span class="detail-field__label">状态</span>
              <el-tag :type="statusTagType(detailData.status)" size="small" effect="dark" round>
                {{ statusLabel(detailData.status) }}
              </el-tag>
            </div>
            <div class="detail-field">
              <span class="detail-field__label">延迟</span>
              <span class="detail-field__value">{{ detailData.latency_ms ?? '-' }}ms</span>
            </div>
          </div>
        </div>

        <div class="detail-section">
          <h4>Token 与费用</h4>
          <div class="token-bar-group">
            <div class="token-bar-item">
              <span class="token-bar-item__label">输入</span>
              <div class="token-bar-item__track">
                <div class="token-bar-item__fill token-bar-item__fill--input" :style="{ width: tokenInputPercent + '%' }"></div>
              </div>
              <span class="token-bar-item__value">{{ formatNumber(detailData.input_tokens) }}</span>
            </div>
            <div class="token-bar-item">
              <span class="token-bar-item__label">输出</span>
              <div class="token-bar-item__track">
                <div class="token-bar-item__fill token-bar-item__fill--output" :style="{ width: tokenOutputPercent + '%' }"></div>
              </div>
              <span class="token-bar-item__value">{{ formatNumber(detailData.output_tokens) }}</span>
            </div>
          </div>
          <div class="detail-cost-row">
            <span>总 Token: <strong>{{ formatNumber(detailData.total_tokens) }}</strong></span>
            <span>费用: <strong>¥{{ formatMoney(detailData.cost_cny) }}</strong> / ${{ formatMoney(detailData.cost_usd) }}</span>
          </div>
        </div>

        <div class="detail-section" v-if="detailData.input_content">
          <h4>输入内容</h4>
          <div class="detail-content-block">{{ detailData.input_content }}</div>
        </div>

        <div class="detail-section" v-if="detailData.output_content">
          <h4>输出内容</h4>
          <div class="detail-content-block">{{ detailData.output_content }}</div>
        </div>

        <div class="detail-section" v-if="detailData.error_message">
          <h4>错误信息</h4>
          <el-alert :title="detailData.error_message" type="error" :closable="false" show-icon />
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getConversations,
  getConversationDetail,
  searchConversations,
  getUsageOverview,
  getCostBudget
} from '@/api/conversation'
import type {
  ConversationLogItem,
  ConversationDetail,
  ConversationStatus,
  UsageOverviewResponse,
  CostBudgetResponse
} from '@/types/conversation'
import { CONVERSATION_STATUS_LABELS } from '@/types/conversation'

// ===== 概览数据 =====
const overview = ref<UsageOverviewResponse>({
  stats: {
    total_input_tokens: 0,
    total_output_tokens: 0,
    total_tokens: 0,
    total_cost_usd: 0,
    total_cost_cny: 0,
    avg_latency_ms: null,
    success_count: 0,
    failed_count: 0,
    total_count: 0
  },
  by_model: [],
  by_agent: []
})

// ===== Tab =====
const activeTab = ref('records')

// ===== 记录列表 =====
const records = ref<ConversationLogItem[]>([])
const recordsTotal = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const recordsLoading = ref(false)

const filters = ref({
  keyword: '',
  search_field: 'both' as string,
  agent_name: '',
  model_name: '',
  status: '' as string
})

// 从概览数据提取筛选选项
const agentOptions = computed(() =>
  [...new Set(overview.value.by_agent.map(a => a.agent_name).filter(Boolean))] as string[]
)
const modelOptions = computed(() =>
  [...new Set(overview.value.by_model.map(m => m.model_name).filter(Boolean))] as string[]
)

// ===== 详情抽屉 =====
const detailVisible = ref(false)
const detailData = ref<ConversationDetail | null>(null)

// ===== 费用预算 =====
const budget = ref<CostBudgetResponse | null>(null)
const budgetLoading = ref(false)
const budgetForm = ref({
  daily_budget_cny: 100,
  monthly_budget_cny: 3000
})

// ===== 计算属性 =====
const maxModelTokens = computed(() =>
  Math.max(...overview.value.by_model.map(m => m.total_tokens), 1)
)
const maxAgentTokens = computed(() =>
  Math.max(...overview.value.by_agent.map(a => a.total_tokens), 1)
)
const tokenInputPercent = computed(() => {
  if (!detailData.value || detailData.value.total_tokens === 0) return 0
  return (detailData.value.input_tokens / detailData.value.total_tokens) * 100
})
const tokenOutputPercent = computed(() => {
  if (!detailData.value || detailData.value.total_tokens === 0) return 0
  return (detailData.value.output_tokens / detailData.value.total_tokens) * 100
})
const todayStr = computed(() => new Date().toLocaleDateString('zh-CN'))
const monthStr = computed(() => {
  const d = new Date()
  return `${d.getFullYear()}年${d.getMonth() + 1}月`
})

// ===== 方法 =====
function formatNumber(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return String(n)
}

function formatMoney(n: number): string {
  if (n >= 1) return n.toFixed(2)
  if (n >= 0.01) return n.toFixed(3)
  if (n > 0) return n.toFixed(5)
  return '0.00'
}

function formatTime(iso: string): string {
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function statusLabel(s: string): string {
  return CONVERSATION_STATUS_LABELS[s as ConversationStatus] || s
}

function statusTagType(s: string): 'success' | 'danger' | 'warning' {
  const map: Record<string, 'success' | 'danger' | 'warning'> = {
    success: 'success',
    failed: 'danger',
    timeout: 'warning'
  }
  return map[s] || 'warning'
}

function getLatencyClass(ms: number | null): string {
  if (ms === null) return ''
  if (ms < 2000) return 'latency-fast'
  if (ms < 5000) return 'latency-normal'
  return 'latency-slow'
}

function getBarWidth(value: number, max: number): number {
  return max > 0 ? (value / max) * 100 : 0
}

function getBudgetColor(percent: number): string {
  if (percent < 60) return 'var(--color-success)'
  if (percent < 85) return 'var(--color-warning)'
  return 'var(--color-danger)'
}

async function loadOverview() {
  try {
    const { data } = await getUsageOverview()
    if (data.code === 200 || data.code === 0) {
      overview.value = data.data
    }
  } catch {
    // 保持默认值
  }
}

async function loadRecords() {
  recordsLoading.value = true
  try {
    const { data } = await getConversations({
      agent_name: filters.value.agent_name || undefined,
      model_name: filters.value.model_name || undefined,
      status: (filters.value.status || undefined) as ConversationStatus | undefined,
      page: currentPage.value,
      page_size: pageSize.value
    })
    if (data.code === 200 || data.code === 0) {
      records.value = data.data.items
      recordsTotal.value = data.data.total
    }
  } catch {
    ElMessage.error('加载会话记录失败')
  } finally {
    recordsLoading.value = false
  }
}

async function handleSearch() {
  if (filters.value.keyword.trim()) {
    recordsLoading.value = true
    try {
      const { data } = await searchConversations({
        keyword: filters.value.keyword.trim(),
        search_field: filters.value.search_field as 'input' | 'output' | 'both',
        page: currentPage.value,
        page_size: pageSize.value
      })
      if (data.code === 200 || data.code === 0) {
        records.value = data.data.items
        recordsTotal.value = data.data.total
      }
    } catch {
      ElMessage.error('搜索失败')
    } finally {
      recordsLoading.value = false
    }
  } else {
    loadRecords()
  }
}

async function showDetail(row: ConversationLogItem) {
  detailVisible.value = true
  detailData.value = null
  try {
    const { data } = await getConversationDetail(row.id)
    if (data.code === 200 || data.code === 0) {
      detailData.value = data.data
    }
  } catch {
    ElMessage.error('加载详情失败')
  }
}

async function loadBudget() {
  budgetLoading.value = true
  try {
    const { data } = await getCostBudget(budgetForm.value)
    if (data.code === 200 || data.code === 0) {
      budget.value = data.data
    }
  } catch {
    ElMessage.error('加载预算分析失败')
  } finally {
    budgetLoading.value = false
  }
}

onMounted(() => {
  loadOverview()
  loadRecords()
})
</script>

<style scoped>
.conversation-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* ===== 概览卡片 ===== */
.overview-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.overview-card {
  position: relative;
  border-radius: var(--radius-lg);
  padding: 20px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  overflow: hidden;
  transition: transform var(--transition-normal), box-shadow var(--transition-normal);
}

.overview-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.overview-card__glow {
  position: absolute;
  top: -20px;
  right: -20px;
  width: 80px;
  height: 80px;
  border-radius: 50%;
  opacity: 0.12;
  filter: blur(20px);
}

.overview-card--tokens .overview-card__glow { background: var(--color-primary); }
.overview-card--cost .overview-card__glow { background: #f59e0b; }
.overview-card--calls .overview-card__glow { background: var(--color-success); }
.overview-card--latency .overview-card__glow { background: #8b5cf6; }

.overview-card__content {
  position: relative;
  z-index: 1;
}

.overview-card__header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--color-text-secondary);
  font-weight: 500;
  margin-bottom: 8px;
}

.overview-card__value {
  font-size: 28px;
  font-weight: 700;
  color: var(--color-text-primary);
  letter-spacing: -0.5px;
  line-height: 1.2;
}

.overview-card__value small {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-secondary);
  margin-left: 2px;
}

.overview-card__sub {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-top: 6px;
}

/* ===== Tab 区域 ===== */
.tab-section {
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border-light);
  padding: 4px 20px 20px;
}

.conversation-tabs :deep(.el-tabs__header) {
  margin-bottom: 16px;
}

.conversation-tabs :deep(.el-tabs__item) {
  font-weight: 500;
  font-size: 14px;
}

.conversation-tabs :deep(.el-tabs__active-bar) {
  height: 3px;
  border-radius: 2px;
}

/* ===== 筛选栏 ===== */
.filter-bar {
  margin-bottom: 16px;
}

.filter-bar .el-form-item {
  margin-bottom: 0;
}

/* ===== 记录表格 ===== */
.records-table {
  border-radius: var(--radius-md);
}

.records-table :deep(.el-table__row) {
  cursor: pointer;
}

.agent-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  font-family: 'SF Mono', 'Fira Code', monospace;
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

.model-text {
  font-size: 13px;
  color: var(--color-text-regular);
}

.token-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.token-total {
  font-weight: 600;
  font-size: 13px;
  color: var(--color-text-primary);
}

.token-detail {
  font-size: 11px;
  color: var(--color-text-secondary);
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.cost-text {
  font-weight: 600;
  font-size: 13px;
  color: #d97706;
}

.latency-fast { color: var(--color-success); }
.latency-normal { color: var(--color-warning); }
.latency-slow { color: var(--color-danger); }

.time-text {
  font-size: 12px;
  color: var(--color-text-secondary);
  font-family: 'SF Mono', 'Fira Code', monospace;
}

/* ===== 分页 ===== */
.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

/* ===== 使用分析 ===== */
.analysis-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.analysis-card {
  padding: 16px;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border-light);
  background: var(--color-bg-page);
}

.analysis-card__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0 0 16px 0;
}

.breakdown-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.breakdown-item__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.breakdown-item__name {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.breakdown-item__provider {
  font-size: 11px;
  color: var(--color-text-secondary);
  padding: 1px 6px;
  border-radius: 3px;
  background: var(--color-border-light);
}

.breakdown-item__bar-wrap {
  height: 6px;
  border-radius: 3px;
  background: var(--color-border-light);
  overflow: hidden;
  margin-bottom: 4px;
}

.breakdown-item__bar {
  height: 100%;
  border-radius: 3px;
  background: linear-gradient(90deg, var(--color-primary), var(--color-primary-light));
  transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
}

.breakdown-item__bar--agent {
  background: linear-gradient(90deg, #8b5cf6, #a78bfa);
}

.breakdown-item__stats {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: var(--color-text-secondary);
}

/* ===== 费用预算 ===== */
.budget-section {
  min-height: 200px;
}

.budget-config {
  margin-bottom: 24px;
}

.budget-cards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.budget-card {
  padding: 24px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border-light);
  background: var(--color-bg-page);
  text-align: center;
}

.budget-card__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.budget-card__period {
  font-size: 16px;
  font-weight: 700;
  color: var(--color-text-primary);
}

.budget-card__date {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.budget-card__progress {
  display: flex;
  justify-content: center;
  margin-bottom: 20px;
}

.budget-percent {
  font-size: 16px;
  font-weight: 700;
}

.budget-card__details {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.budget-detail {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 12px;
  border-radius: var(--radius-sm);
  background: var(--color-bg-card);
}

.budget-detail__label {
  font-size: 13px;
  color: var(--color-text-secondary);
}

.budget-detail__value {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
}

/* ===== 详情抽屉 ===== */
.detail-section {
  margin-bottom: 24px;
}

.detail-section h4 {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin: 0 0 12px 0;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--color-border-light);
}

.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.detail-field {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.detail-field__label {
  font-size: 11px;
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.detail-field__value {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-primary);
}

.token-bar-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

.token-bar-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.token-bar-item__label {
  font-size: 12px;
  color: var(--color-text-secondary);
  width: 32px;
  flex-shrink: 0;
}

.token-bar-item__track {
  flex: 1;
  height: 8px;
  border-radius: 4px;
  background: var(--color-border-light);
  overflow: hidden;
}

.token-bar-item__fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.4s ease;
}

.token-bar-item__fill--input {
  background: linear-gradient(90deg, var(--color-primary), var(--color-primary-light));
}

.token-bar-item__fill--output {
  background: linear-gradient(90deg, #8b5cf6, #a78bfa);
}

.token-bar-item__value,
.token-bar-item span.value {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-primary);
  width: 60px;
  text-align: right;
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.detail-cost-row {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: var(--color-text-regular);
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  background: var(--color-bg-page);
}

.detail-cost-row strong {
  color: var(--color-text-primary);
}

.detail-content-block {
  padding: 12px;
  border-radius: var(--radius-sm);
  background: var(--color-bg-page);
  font-size: 13px;
  line-height: 1.7;
  color: var(--color-text-regular);
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 300px;
  overflow-y: auto;
}

/* ===== 响应式 ===== */
@media (max-width: 1200px) {
  .overview-cards {
    grid-template-columns: repeat(2, 1fr);
  }
  .analysis-grid {
    grid-template-columns: 1fr;
  }
  .budget-cards {
    grid-template-columns: 1fr;
  }
}
</style>
