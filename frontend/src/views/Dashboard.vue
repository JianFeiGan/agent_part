<template>
  <div class="dashboard">
    <el-row :gutter="20">
      <!-- 统计卡片 -->
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background-color: #409eff;">
              <el-icon :size="32"><Goods /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ statistics.totalProducts }}</div>
              <div class="stat-label">商品总数</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background-color: #67c23a;">
              <el-icon :size="32"><List /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ statistics.totalTasks }}</div>
              <div class="stat-label">任务总数</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background-color: #e6a23c;">
              <el-icon :size="32"><Loading /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ statistics.processingTasks }}</div>
              <div class="stat-label">处理中</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background-color: #f56c6c;">
              <el-icon :size="32"><CircleClose /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ statistics.failedTasks }}</div>
              <div class="stat-label">失败任务</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 快捷操作 -->
    <el-card class="quick-actions mt-20">
      <template #header>
        <span>快捷操作</span>
      </template>
      <el-row :gutter="20">
        <el-col :span="6">
          <el-button type="primary" size="large" @click="navigateTo('/products/create')">
            <el-icon><Plus /></el-icon>
            创建商品
          </el-button>
        </el-col>
        <el-col :span="6">
          <el-button type="success" size="large" @click="navigateTo('/tasks/create')">
            <el-icon><Plus /></el-icon>
            创建任务
          </el-button>
        </el-col>
        <el-col :span="6">
          <el-button size="large" @click="navigateTo('/products')">
            <el-icon><Goods /></el-icon>
            商品管理
          </el-button>
        </el-col>
        <el-col :span="6">
          <el-button size="large" @click="navigateTo('/tasks')">
            <el-icon><List /></el-icon>
            任务管理
          </el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- 最近任务 -->
    <el-card class="recent-tasks mt-20">
      <template #header>
        <div class="card-header">
          <span>最近任务</span>
          <el-button type="primary" link @click="navigateTo('/tasks')">
            查看全部
          </el-button>
        </div>
      </template>
      <el-table :data="recentTasks" style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="任务名称" />
        <el-table-column prop="type" label="类型" width="120">
          <template #default="{ row }">
            <el-tag>{{ getTaskTypeLabel(row.type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="progress" label="进度" width="150">
          <template #default="{ row }">
            <el-progress
              :percentage="row.progress"
              :status="row.status === 'completed' ? 'success' : row.status === 'failed' ? 'exception' : undefined"
            />
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { TaskType, TaskStatus, TaskTypeLabels, TaskStatusLabels } from '@/types/task'
import type { Task } from '@/types/task'

/**
 * 仪表盘页面
 * @description 首页仪表盘，展示统计数据和快捷操作
 */

const router = useRouter()

// 统计数据
const statistics = ref({
  totalProducts: 0,
  totalTasks: 0,
  processingTasks: 0,
  failedTasks: 0
})

// 最近任务列表
const recentTasks = ref<Task[]>([])

// 获取任务类型标签
const getTaskTypeLabel = (type: TaskType) => {
  return TaskTypeLabels[type] || type
}

// 获取任务状态标签
const getStatusLabel = (status: TaskStatus) => {
  return TaskStatusLabels[status] || status
}

// 获取状态标签类型
const getStatusType = (status: TaskStatus) => {
  const typeMap: Record<TaskStatus, string> = {
    [TaskStatus.PENDING]: 'info',
    [TaskStatus.PROCESSING]: 'warning',
    [TaskStatus.COMPLETED]: 'success',
    [TaskStatus.FAILED]: 'danger'
  }
  return typeMap[status] || 'info'
}

// 导航到指定页面
const navigateTo = (path: string) => {
  router.push(path)
}

// 加载统计数据
const loadStatistics = async () => {
  // TODO: 调用 API 获取统计数据
  // 模拟数据
  statistics.value = {
    totalProducts: 128,
    totalTasks: 256,
    processingTasks: 12,
    failedTasks: 3
  }
}

// 加载最近任务
const loadRecentTasks = async () => {
  // TODO: 调用 API 获取最近任务
  // 模拟数据
  recentTasks.value = [
    {
      id: 1,
      name: '商品主图生成',
      type: TaskType.IMAGE_GENERATION,
      status: TaskStatus.COMPLETED,
      product_id: 1,
      product_name: '测试商品',
      config: {},
      progress: 100,
      created_at: '2024-01-15 10:30:00',
      updated_at: '2024-01-15 10:35:00'
    },
    {
      id: 2,
      name: '宣传视频生成',
      type: TaskType.VIDEO_GENERATION,
      status: TaskStatus.PROCESSING,
      product_id: 2,
      product_name: '示例商品',
      config: {},
      progress: 65,
      created_at: '2024-01-15 11:00:00',
      updated_at: '2024-01-15 11:15:00'
    }
  ]
}

onMounted(() => {
  loadStatistics()
  loadRecentTasks()
})
</script>

<style scoped>
.dashboard {
  padding: 0;
}

.stat-card {
  margin-bottom: 20px;
}

.stat-content {
  display: flex;
  align-items: center;
  gap: 16px;
}

.stat-icon {
  width: 64px;
  height: 64px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
  color: #303133;
  line-height: 1.2;
}

.stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 4px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.quick-actions .el-button {
  width: 100%;
}
</style>