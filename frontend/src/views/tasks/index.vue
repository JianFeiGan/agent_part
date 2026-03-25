<template>
  <div class="task-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>任务列表</span>
          <el-button type="primary" @click="handleCreate">
            <el-icon><Plus /></el-icon>
            创建任务
          </el-button>
        </div>
      </template>

      <!-- 搜索表单 -->
      <el-form :inline="true" :model="queryParams" class="search-form">
        <el-form-item label="任务类型">
          <el-select v-model="queryParams.task_type" placeholder="请选择类型" clearable>
            <el-option label="图片生成" value="image_only" />
            <el-option label="视频生成" value="video_only" />
            <el-option label="图片+视频" value="image_and_video" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="queryParams.status" placeholder="请选择状态" clearable>
            <el-option label="待处理" value="pending" />
            <el-option label="运行中" value="running" />
            <el-option label="已完成" value="completed" />
            <el-option label="失败" value="failed" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon>
            搜索
          </el-button>
          <el-button @click="handleReset">
            <el-icon><Refresh /></el-icon>
            重置
          </el-button>
        </el-form-item>
      </el-form>

      <!-- 任务表格 -->
      <el-table
        v-loading="loading"
        :data="taskList"
        style="width: 100%"
      >
        <el-table-column prop="task_id" label="任务ID" width="180" />
        <el-table-column prop="product_id" label="商品ID" width="180" />
        <el-table-column prop="request.task_type" label="类型" width="120">
          <template #default="{ row }">
            <el-tag>{{ getTaskTypeLabel(row.request?.task_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="progress" label="进度" width="180">
          <template #default="{ row }">
            <div class="progress-cell">
              <el-progress
                :percentage="row.progress || 0"
                :status="row.status === 'completed' ? 'success' : row.status === 'failed' ? 'exception' : undefined"
              />
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="current_step" label="当前步骤" width="150">
          <template #default="{ row }">
            {{ getStepLabel(row.current_step) }}
          </template>
        </el-table-column>
        <el-table-column prop="error_message" label="最新状态" width="200">
          <template #default="{ row }">
            <el-tooltip v-if="row.error_message" :content="row.error_message" placement="top">
              <el-text type="danger" truncated>{{ row.error_message }}</el-text>
            </el-tooltip>
            <span v-else-if="row.status === 'running'">{{ getStepLabel(row.current_step) }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="handleDetail(row)">
              详情
            </el-button>
            <el-button
              v-if="row.status === 'running'"
              type="warning"
              link
              @click="handleCancel(row)"
            >
              取消
            </el-button>
            <el-button
              v-if="row.status === 'completed' || row.status === 'failed'"
              type="danger"
              link
              @click="handleDelete(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-model:current-page="queryParams.page"
        v-model:page-size="queryParams.page_size"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        class="pagination"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getTasks, cancelTask, deleteTask } from '@/api/tasks'
import type { Task, TaskQueryParams } from '@/types/task'

/**
 * 任务列表页面
 * @description 任务管理列表，支持搜索、分页、取消、删除等操作
 */

const router = useRouter()

// 加载状态
const loading = ref(false)

// 任务列表
const taskList = ref<Task[]>([])

// 总数
const total = ref(0)

// 查询参数
const queryParams = reactive<TaskQueryParams>({
  task_type: undefined,
  status: undefined,
  page: 1,
  page_size: 10
})

// 任务类型标签映射
const taskTypeLabels: Record<string, string> = {
  'image_only': '图片生成',
  'video_only': '视频生成',
  'image_and_video': '图片+视频'
}

// 任务状态标签映射
const statusLabels: Record<string, string> = {
  'pending': '待处理',
  'running': '运行中',
  'completed': '已完成',
  'failed': '失败'
}

// 步骤标签映射
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

// 获取任务类型标签
const getTaskTypeLabel = (type: string | undefined) => {
  return type ? (taskTypeLabels[type] || type) : '-'
}

// 获取状态标签
const getStatusLabel = (status: string) => {
  return statusLabels[status] || status
}

// 获取状态标签类型
const getStatusType = (status: string) => {
  const typeMap: Record<string, string> = {
    'pending': 'info',
    'running': 'warning',
    'completed': 'success',
    'failed': 'danger'
  }
  return typeMap[status] || 'info'
}

// 获取步骤标签
const getStepLabel = (step: string) => {
  return stepLabels[step] || step
}

// 格式化时间
const formatTime = (time: string) => {
  if (!time) return '-'
  return time.replace('T', ' ').substring(0, 19)
}

// 加载任务列表
const loadTasks = async () => {
  loading.value = true
  try {
    const response = await getTasks(queryParams)
    if (response.data.code === 200) {
      taskList.value = response.data.data.items
      total.value = response.data.data.total
    } else {
      ElMessage.error(response.data.message || '加载任务列表失败')
    }
  } catch (error) {
    console.error('加载任务列表失败:', error)
    ElMessage.error('加载任务列表失败')
  } finally {
    loading.value = false
  }
}

// 搜索
const handleSearch = () => {
  queryParams.page = 1
  loadTasks()
}

// 重置
const handleReset = () => {
  queryParams.task_type = undefined
  queryParams.status = undefined
  queryParams.page = 1
  loadTasks()
}

// 创建任务
const handleCreate = () => {
  router.push('/tasks/create')
}

// 查看详情
const handleDetail = (row: Task) => {
  router.push(`/tasks/${row.task_id}`)
}

// 取消任务
const handleCancel = async (row: Task) => {
  try {
    await ElMessageBox.confirm(`确定要取消任务 "${row.task_id}" 吗？`, '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    const response = await cancelTask(row.task_id)
    if (response.data.code === 200) {
      ElMessage.success('任务已取消')
      loadTasks()
    } else {
      ElMessage.error(response.data.message || '取消失败')
    }
  } catch {
    // 用户取消
  }
}

// 删除任务
const handleDelete = async (row: Task) => {
  try {
    await ElMessageBox.confirm(`确定要删除任务 "${row.task_id}" 吗？`, '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    const response = await deleteTask(row.task_id)
    if (response.data.code === 200) {
      ElMessage.success('删除成功')
      loadTasks()
    } else {
      ElMessage.error(response.data.message || '删除失败')
    }
  } catch {
    // 用户取消
  }
}

// 分页大小变化
const handleSizeChange = (size: number) => {
  queryParams.page_size = size
  loadTasks()
}

// 页码变化
const handleCurrentChange = (page: number) => {
  queryParams.page = page
  loadTasks()
}

onMounted(() => {
  loadTasks()
})
</script>

<style scoped>
.task-list {
  padding: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-form {
  margin-bottom: 20px;
}

.pagination {
  margin-top: 20px;
  justify-content: flex-end;
}

.progress-cell {
  width: 100%;
}
</style>