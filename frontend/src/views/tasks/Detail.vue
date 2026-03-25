<template>
  <div class="task-detail">
    <el-card v-loading="loading">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <el-button link @click="router.back()">
              <el-icon><ArrowLeft /></el-icon>
              返回
            </el-button>
            <span class="task-title">任务详情</span>
          </div>
          <div class="header-right">
            <el-button
              v-if="task?.status === 'running'"
              type="warning"
              @click="handleCancel"
            >
              取消任务
            </el-button>
          </div>
        </div>
      </template>

      <template v-if="task">
        <!-- 任务状态 -->
        <div class="status-section">
          <el-descriptions :column="4" border>
            <el-descriptions-item label="任务ID">{{ task.task_id }}</el-descriptions-item>
            <el-descriptions-item label="商品ID">{{ task.product_id }}</el-descriptions-item>
            <el-descriptions-item label="任务类型">
              <el-tag>{{ getTaskTypeLabel(task.task_type) }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="getStatusType(task.status)">
                {{ getStatusLabel(task.status) }}
              </el-tag>
            </el-descriptions-item>
          </el-descriptions>

          <!-- 进度条 -->
          <div v-if="task.status === 'running'" class="progress-section">
            <div class="progress-label">处理进度 - {{ getStepLabel(task.current_step) }}</div>
            <el-progress
              :percentage="task.progress || 0"
              :stroke-width="20"
              :text-inside="true"
            />
          </div>
        </div>

        <!-- 已完成步骤 -->
        <el-divider>执行进度</el-divider>
        <div class="timeline-section">
          <el-timeline>
            <el-timeline-item
              v-for="log in agentLogs"
              :key="log.step"
              :type="getLogStatusType(log.status)"
              :hollow="log.status === 'pending'"
            >
              <el-card>
                <h4>{{ log.agent_name }}</h4>
                <div class="log-details">
                  <p class="log-status">
                    <el-tag :type="getLogStatusTagType(log.status)" size="small">
                      {{ getLogStatusLabel(log.status) }}
                    </el-tag>
                  </p>
                  <p v-if="log.start_time" class="log-time">
                    <span class="time-label">开始:</span>
                    {{ formatTime(log.start_time) }}
                  </p>
                  <p v-if="log.end_time" class="log-time">
                    <span class="time-label">结束:</span>
                    {{ formatTime(log.end_time) }}
                  </p>
                  <p v-if="log.output_summary" class="log-summary">
                    {{ log.output_summary }}
                  </p>
                  <p v-if="log.message && log.status === 'failed'" class="log-error">
                    <el-text type="danger">{{ log.message }}</el-text>
                  </p>
                </div>
              </el-card>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-if="!agentLogs.length" description="暂无执行日志" />
        </div>

        <!-- 生成结果 -->
        <template v-if="task.status === 'completed' && (task.images?.length || task.video)">
          <el-divider>生成结果</el-divider>

          <!-- 图片结果 -->
          <div v-if="task.images?.length" class="result-section">
            <h4>生成的图片</h4>
            <div class="image-grid">
              <el-image
                v-for="img in task.images"
                :key="img.image_id"
                :src="img.url"
                :preview-src-list="task.images.map(i => i.url)"
                fit="cover"
                class="result-image"
              >
                <template #placeholder>
                  <div class="image-placeholder">加载中...</div>
                </template>
              </el-image>
            </div>
          </div>

          <!-- 视频结果 -->
          <div v-if="task.video" class="result-section">
            <h4>生成的视频</h4>
            <video
              :src="task.video.url"
              controls
              class="result-video"
            />
          </div>
        </template>

        <!-- 错误信息 -->
        <template v-if="task.status === 'failed' && task.error_message">
          <el-divider>错误信息</el-divider>
          <el-alert
            :title="task.error_message"
            type="error"
            show-icon
            :closable="false"
          />
        </template>
      </template>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getTaskById, cancelTask } from '@/api/tasks'
import type { TaskDetail, AgentLog } from '@/types/task'

/**
 * 任务详情页面
 */

const router = useRouter()
const route = useRoute()

// 任务 ID
const taskId = route.params.id as string

// 加载状态
const loading = ref(false)

// 任务详情
const task = ref<TaskDetail | null>(null)

// 轮询定时器
let pollTimer: ReturnType<typeof setInterval> | null = null

// Agent 日志列表
const agentLogs = computed<AgentLog[]>(() => {
  if (!task.value?.agent_logs?.length) {
    // 如果没有日志，返回工作流步骤的默认日志
    return workflowSteps.map(step => ({
      agent_name: step.label,
      step: step.key,
      start_time: null,
      end_time: null,
      status: task.value?.completed_steps?.includes(step.key)
        ? 'completed'
        : task.value?.current_step === step.key
          ? 'running'
          : 'pending',
      message: null,
      output_summary: null
    }))
  }
  return task.value.agent_logs
})

// 工作流步骤
const workflowSteps = [
  { key: 'requirement_analysis', label: '需求分析' },
  { key: 'creative_planning', label: '创意策划' },
  { key: 'visual_design', label: '视觉设计' },
  { key: 'image_generation', label: '图片生成' },
  { key: 'video_generation', label: '视频生成' },
  { key: 'quality_review', label: '质量审核' }
]

// Agent 日志状态标签
const logStatusLabels: Record<string, string> = {
  'pending': '待执行',
  'running': '执行中',
  'completed': '已完成',
  'failed': '失败'
}

const getLogStatusLabel = (status: string) => logStatusLabels[status] || status

const getLogStatusType = (status: string) => {
  const typeMap: Record<string, string> = {
    'pending': 'info',
    'running': 'primary',
    'completed': 'success',
    'failed': 'danger'
  }
  return typeMap[status] || 'info'
}

const getLogStatusTagType = (status: string) => {
  const typeMap: Record<string, string> = {
    'pending': 'info',
    'running': 'warning',
    'completed': 'success',
    'failed': 'danger'
  }
  return typeMap[status] || 'info'
}

// 格式化时间
const formatTime = (time: string | null) => {
  if (!time) return '-'
  return time.replace('T', ' ').substring(0, 19)
}

// 任务类型标签
const taskTypeLabels: Record<string, string> = {
  'image_only': '图片生成',
  'video_only': '视频生成',
  'image_and_video': '图片+视频'
}

// 状态标签
const statusLabels: Record<string, string> = {
  'pending': '待处理',
  'running': '运行中',
  'completed': '已完成',
  'failed': '失败'
}

const getTaskTypeLabel = (type: string) => taskTypeLabels[type] || type
const getStatusLabel = (status: string) => statusLabels[status] || status

const getStatusType = (status: string) => {
  const typeMap: Record<string, string> = {
    'pending': 'info',
    'running': 'warning',
    'completed': 'success',
    'failed': 'danger'
  }
  return typeMap[status] || 'info'
}

const stepLabels: Record<string, string> = {
  'init': '初始化',
  'orchestration': '编排调度',
  'requirement_analysis': '需求分析',
  'creative_planning': '创意策划',
  'visual_design': '视觉设计',
  'image_generation': '图片生成',
  'video_generation': '视频生成',
  'quality_review': '质量审核',
  'completed': '已完成',
  'error': '错误',
  'cancelled': '已取消'
}

const getStepLabel = (step: string) => stepLabels[step] || step

// 加载任务详情
const loadTask = async () => {
  try {
    const response = await getTaskById(taskId)
    if (response.data.code === 200) {
      task.value = response.data.data
    } else {
      ElMessage.error(response.data.message || '加载任务详情失败')
    }
  } catch (error) {
    console.error('加载任务详情失败:', error)
    ElMessage.error('加载任务详情失败')
  }
}

// 轮询任务进度
const startPolling = () => {
  if (task.value?.status === 'running') {
    pollTimer = setInterval(async () => {
      await loadTask()
      if (task.value?.status !== 'running' && pollTimer) {
        clearInterval(pollTimer)
        pollTimer = null
      }
    }, 3000)
  }
}

// 取消任务
const handleCancel = async () => {
  try {
    await ElMessageBox.confirm('确定要取消该任务吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    const response = await cancelTask(taskId)
    if (response.data.code === 200) {
      ElMessage.success('任务已取消')
      await loadTask()
    } else {
      ElMessage.error(response.data.message || '取消失败')
    }
  } catch {
    // 用户取消
  }
}

onMounted(async () => {
  loading.value = true
  await loadTask()
  loading.value = false
  startPolling()
})

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
  }
})
</script>

<style scoped>
.task-detail {
  padding: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.task-title {
  font-size: 18px;
  font-weight: 600;
}

.status-section {
  margin-bottom: 20px;
}

.progress-section {
  margin-top: 20px;
  padding: 20px;
  background-color: #f5f7fa;
  border-radius: 8px;
}

.progress-label {
  font-size: 14px;
  color: #606266;
  margin-bottom: 10px;
}

.timeline-section,
.result-section {
  margin-bottom: 20px;
}

.log-details {
  margin-top: 8px;
}

.log-status {
  margin-bottom: 8px;
}

.log-time {
  font-size: 12px;
  color: #909399;
  margin: 4px 0;
}

.time-label {
  color: #606266;
  margin-right: 4px;
}

.log-summary {
  font-size: 14px;
  color: #67c23a;
  margin-top: 8px;
}

.log-error {
  margin-top: 8px;
}

.image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
}

.result-image {
  width: 100%;
  height: 200px;
  border-radius: 8px;
}

.image-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  background-color: #f5f7fa;
}

.result-video {
  max-width: 100%;
  max-height: 500px;
  border-radius: 8px;
}
</style>