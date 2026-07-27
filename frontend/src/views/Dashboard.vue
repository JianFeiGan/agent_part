<template>
  <div class="dashboard">
    <!-- 统计卡片 -->
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-card__body">
          <div class="stat-card__info">
            <span class="stat-card__label">商品总数</span>
            <span class="stat-card__value">{{ statistics.totalProducts }}</span>
          </div>
          <div class="stat-card__icon stat-card__icon--blue">
            <el-icon :size="22"><Goods /></el-icon>
          </div>
        </div>
        <div class="stat-card__footer">
          <span class="stat-card__trend">累计</span>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-card__body">
          <div class="stat-card__info">
            <span class="stat-card__label">任务总数</span>
            <span class="stat-card__value">{{ statistics.totalTasks }}</span>
          </div>
          <div class="stat-card__icon stat-card__icon--green">
            <el-icon :size="22"><List /></el-icon>
          </div>
        </div>
        <div class="stat-card__footer">
          <span class="stat-card__trend">累计</span>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-card__body">
          <div class="stat-card__info">
            <span class="stat-card__label">处理中</span>
            <span class="stat-card__value">{{ statistics.processingTasks }}</span>
          </div>
          <div class="stat-card__icon stat-card__icon--amber">
            <el-icon :size="22"><Loading /></el-icon>
          </div>
        </div>
        <div class="stat-card__footer">
          <span class="stat-card__trend">进行中</span>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-card__body">
          <div class="stat-card__info">
            <span class="stat-card__label">失败任务</span>
            <span class="stat-card__value">{{ statistics.failedTasks }}</span>
          </div>
          <div class="stat-card__icon stat-card__icon--red">
            <el-icon :size="22"><CircleClose /></el-icon>
          </div>
        </div>
        <div class="stat-card__footer">
          <span class="stat-card__trend">需关注</span>
        </div>
      </div>
    </div>

    <!-- 快捷操作 -->
    <div class="section-card">
      <div class="section-card__header">
        <h3 class="section-card__title">快捷操作</h3>
      </div>
      <div class="quick-actions">
        <div class="action-item" @click="navigateTo('/products/create')">
          <div class="action-item__icon action-item__icon--primary">
            <el-icon :size="20"><Plus /></el-icon>
          </div>
          <span class="action-item__label">创建商品</span>
        </div>
        <div class="action-item" @click="navigateTo('/tasks/create')">
          <div class="action-item__icon action-item__icon--green">
            <el-icon :size="20"><Plus /></el-icon>
          </div>
          <span class="action-item__label">创建任务</span>
        </div>
        <div class="action-item" @click="navigateTo('/products')">
          <div class="action-item__icon action-item__icon--amber">
            <el-icon :size="20"><Goods /></el-icon>
          </div>
          <span class="action-item__label">商品管理</span>
        </div>
        <div class="action-item" @click="navigateTo('/tasks')">
          <div class="action-item__icon action-item__icon--purple">
            <el-icon :size="20"><List /></el-icon>
          </div>
          <span class="action-item__label">任务管理</span>
        </div>
      </div>
    </div>

    <!-- 最近任务 -->
    <div class="section-card">
      <div class="section-card__header">
        <h3 class="section-card__title">最近任务</h3>
        <el-button type="primary" link @click="navigateTo('/tasks')">查看全部 →</el-button>
      </div>
      <el-table :data="recentTasks" style="width: 100%" class="task-table">
        <el-table-column prop="task_id" label="任务ID" width="140">
          <template #default="{ row }">
            <span class="mono-text">{{ row.task_id }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="product_id" label="商品ID" width="140">
          <template #default="{ row }">
            <span class="mono-text">{{ row.product_id || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="task_type" label="类型" width="130">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ row.task_type || '-' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <span :class="['status-dot', `status-dot--${row.status}`]"></span>
            {{ getStatusLabel(row.status) }}
          </template>
        </el-table-column>
        <el-table-column prop="progress" label="进度" width="160">
          <template #default="{ row }">
            <el-progress
              :percentage="row.progress"
              :stroke-width="6"
              :color="getProgressColor(row.status)"
              :show-text="true"
            />
          </template>
        </el-table-column>
        <el-table-column prop="current_step" label="步骤">
          <template #default="{ row }">
            <span class="step-text">{{ row.current_step }}</span>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { TaskStatusLabels } from '@/types/task'
import { getDashboardStats } from '@/api/dashboard'
import type { RecentTaskItem } from '@/types/dashboard'

const router = useRouter()

const statistics = ref({
  totalProducts: 0,
  totalTasks: 0,
  processingTasks: 0,
  failedTasks: 0
})

const recentTasks = ref<RecentTaskItem[]>([])

const getStatusLabel = (status: string) => {
  return TaskStatusLabels[status as keyof typeof TaskStatusLabels] || status
}

const getProgressColor = (status: string) => {
  const map: Record<string, string> = {
    completed: 'var(--color-success)',
    failed: 'var(--color-danger)',
    running: 'var(--color-primary)',
  }
  return map[status] || 'var(--color-info)'
}

const navigateTo = (path: string) => { router.push(path) }

const loadDashboard = async () => {
  try {
    const data = await getDashboardStats()
    statistics.value = {
      totalProducts: data.total_products,
      totalTasks: data.total_tasks,
      processingTasks: data.running_tasks,
      failedTasks: data.failed_tasks
    }
    recentTasks.value = data.recent_tasks
  } catch {
    // 保持默认值
  }
}

onMounted(() => { loadDashboard() })
</script>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* ===== 统计卡片行 ===== */
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.stat-card {
  position: relative;
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
  padding: 20px;
  border: 1px solid var(--color-border-light);
  transition: all var(--transition-normal);
  overflow: hidden;
}

.stat-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  opacity: 0;
  transition: opacity var(--transition-normal);
}

.stat-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--shadow-md);
}

.stat-card:hover::before {
  opacity: 1;
}

.stat-card:nth-child(1)::before { background: linear-gradient(90deg, #3b6df0, #06b6d4); }
.stat-card:nth-child(2)::before { background: linear-gradient(90deg, #10b981, #34d399); }
.stat-card:nth-child(3)::before { background: linear-gradient(90deg, #f59e0b, #fbbf24); }
.stat-card:nth-child(4)::before { background: linear-gradient(90deg, #ef4444, #f87171); }

.stat-card__body {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.stat-card__label {
  font-size: 13px;
  color: var(--color-text-secondary);
  font-weight: 500;
}

.stat-card__value {
  font-size: 30px;
  font-weight: 700;
  color: var(--color-text-primary);
  line-height: 1.3;
  letter-spacing: -0.5px;
}

.stat-card__info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-card__icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-card__icon--blue  { background: linear-gradient(135deg, rgba(59,109,240,0.12), rgba(6,182,212,0.08)); color: var(--color-primary); }
.stat-card__icon--green { background: linear-gradient(135deg, rgba(16,185,129,0.12), rgba(52,211,153,0.08)); color: var(--color-success); }
.stat-card__icon--amber { background: linear-gradient(135deg, rgba(245,158,11,0.12), rgba(251,191,36,0.08)); color: var(--color-warning); }
.stat-card__icon--red   { background: linear-gradient(135deg, rgba(239,68,68,0.12), rgba(248,113,113,0.08)); color: var(--color-danger);  }

.stat-card__footer {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--color-border-light);
}

.stat-card__trend {
  font-size: 12px;
  color: var(--color-text-secondary);
}

/* ===== 通用区块卡片 ===== */
.section-card {
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border-light);
  padding: 20px;
  transition: box-shadow var(--transition-normal);
}

.section-card:hover {
  box-shadow: var(--shadow-sm);
}

.section-card__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-card__title {
  font-size: 15px;
  font-weight: 700;
  color: var(--color-text-primary);
  margin: 0;
}

/* ===== 快捷操作 ===== */
.quick-actions {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.action-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 20px 12px;
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: all var(--transition-normal);
  border: 1px solid var(--color-border-light);
  background: var(--color-bg-card);
}

.action-item:hover {
  background: var(--color-primary-bg);
  border-color: var(--color-primary);
  transform: translateY(-2px);
  box-shadow: var(--shadow-primary);
}

.action-item__icon {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.action-item__icon--primary { background: linear-gradient(135deg, rgba(59,109,240,0.12), rgba(6,182,212,0.08)); color: var(--color-primary); }
.action-item__icon--green   { background: linear-gradient(135deg, rgba(16,185,129,0.12), rgba(52,211,153,0.08)); color: var(--color-success); }
.action-item__icon--amber   { background: linear-gradient(135deg, rgba(245,158,11,0.12), rgba(251,191,36,0.08)); color: var(--color-warning); }
.action-item__icon--purple  { background: linear-gradient(135deg, rgba(139,92,246,0.12), rgba(167,139,250,0.08)); color: #8b5cf6; }

.action-item__label {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-regular);
}

/* ===== 表格 ===== */
.task-table .mono-text {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 12px;
  color: var(--color-text-secondary);
}

.status-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  margin-right: 6px;
  vertical-align: middle;
}

.status-dot--pending  { background: var(--color-info); }
.status-dot--running  { background: var(--color-warning); animation: pulse 1.5s infinite; }
.status-dot--completed { background: var(--color-success); }
.status-dot--failed   { background: var(--color-danger); }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.step-text {
  font-size: 13px;
  color: var(--color-text-secondary);
}
</style>
