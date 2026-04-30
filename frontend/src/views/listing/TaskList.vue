<template>
  <div class="task-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>刊登任务</span>
        </div>
      </template>

      <el-table :data="tasks" v-loading="loading" stripe>
        <el-table-column prop="task_id" label="任务ID" width="80" />
        <el-table-column prop="product_sku" label="商品SKU" />
        <el-table-column label="目标平台">
          <template #default="{ row }">
            <el-tag
              v-for="p in row.target_platforms"
              :key="p"
              size="small"
              style="margin-right: 4px"
            >
              {{ p }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="320">
          <template #default="{ row }">
            <el-button size="small" @click="handleCompliance(row.task_id)">
              合规检查
            </el-button>
            <el-button size="small" type="primary" @click="handlePush(row.task_id)">
              推送刊登
            </el-button>
            <el-button size="small" @click="$router.push({ name: 'ListingTaskDetail', params: { id: row.task_id } })">
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div style="margin-top: 16px">
        <el-button type="primary" @click="showCreateDialog = true">
          创建任务
        </el-button>
        <el-button @click="fetchTasks">刷新</el-button>
      </div>
    </el-card>

    <!-- 创建任务对话框 -->
    <el-dialog v-model="showCreateDialog" title="创建刊登任务" width="500px">
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="商品SKU">
          <el-select v-model="createForm.product_sku" filterable placeholder="选择商品">
            <el-option
              v-for="p in products"
              :key="p.sku"
              :label="`${p.sku} - ${p.title}`"
              :value="p.sku"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="目标平台">
          <el-checkbox-group v-model="createForm.target_platforms">
            <el-checkbox value="amazon">Amazon</el-checkbox>
            <el-checkbox value="ebay">eBay</el-checkbox>
            <el-checkbox value="shopify">Shopify</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreateTask" :loading="creating">
          创建
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listTasks,
  listProducts,
  createTask,
  runComplianceCheck,
  pushListing,
} from '@/api/listing'
import type {
  ListingTaskResponse,
  ProductResponse,
  CreateListingTaskRequest,
} from '@/types/listing'

const tasks = ref<ListingTaskResponse[]>([])
const products = ref<ProductResponse[]>([])
const loading = ref(false)
const creating = ref(false)
const showCreateDialog = ref(false)

const createForm = reactive<CreateListingTaskRequest>({
  product_sku: '',
  target_platforms: [],
})

const statusType = (status: string): string => {
  const map: Record<string, string> = {
    completed: 'success',
    published: 'success',
    reviewing: 'info',
    generating: 'warning',
    pending: 'warning',
    failed: 'danger',
    partial: 'warning',
  }
  return map[status] || 'info'
}

const fetchTasks = async () => {
  loading.value = true
  try {
    const res = await listTasks()
    if (res.data.code === 200) {
      tasks.value = res.data.data
    }
  } finally {
    loading.value = false
  }
}

const fetchProducts = async () => {
  const res = await listProducts()
  if (res.data.code === 200) {
    products.value = res.data.data
  }
}

const handleCreateTask = async () => {
  if (!createForm.product_sku || createForm.target_platforms.length === 0) {
    ElMessage.warning('请选择商品和目标平台')
    return
  }
  creating.value = true
  try {
    const res = await createTask(createForm)
    if (res.data.code === 200) {
      ElMessage.success('任务创建成功')
      showCreateDialog.value = false
      fetchTasks()
    } else {
      ElMessage.error(res.data.message || '创建失败')
    }
  } finally {
    creating.value = false
  }
}

const handleCompliance = async (taskId: number) => {
  try {
    await ElMessageBox.confirm('确定对该任务执行合规检查？', '提示')
    const res = await runComplianceCheck(taskId)
    if (res.data.code === 200) {
      ElMessage.success('合规检查完成')
      fetchTasks()
    } else {
      ElMessage.error(res.data.message || '合规检查失败')
    }
  } catch {
    // User cancelled
  }
}

const handlePush = async (taskId: number) => {
  try {
    await ElMessageBox.confirm('确定推送该任务的刊登？', '提示')
    const res = await pushListing(taskId)
    if (res.data.code === 200) {
      ElMessage.success('推送完成')
      fetchTasks()
    } else {
      ElMessage.error(res.data.message || '推送失败')
    }
  } catch {
    // User cancelled
  }
}

onMounted(() => {
  fetchTasks()
  fetchProducts()
})
</script>
