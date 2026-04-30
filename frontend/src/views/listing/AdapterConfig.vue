<template>
  <div class="adapter-config">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>适配器配置</span>
          <el-button type="primary" @click="handleCreate">新增配置</el-button>
        </div>
      </template>

      <el-table :data="configs" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="platform" label="平台" width="100">
          <template #default="{ row }">
            <el-tag :type="platformType(row.platform)">{{ row.platform.toUpperCase() }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="shop_id" label="店铺ID" />
        <el-table-column label="凭证" width="200">
          <template #default="{ row }">
            <el-tag
              v-for="key in Object.keys(row.credentials_masked)"
              :key="key"
              size="small"
              style="margin: 2px"
            >
              {{ key }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="updated_at" label="更新时间" width="180" />
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑配置' : '新增配置'"
      width="500px"
    >
      <el-form :model="form" label-width="100px">
        <el-form-item label="平台" v-if="!editingId">
          <el-select v-model="form.platform" placeholder="选择平台" style="width: 100%">
            <el-option label="Amazon" value="amazon" />
            <el-option label="eBay" value="ebay" />
            <el-option label="Shopify" value="shopify" />
          </el-select>
        </el-form-item>
        <el-form-item label="店铺ID" v-if="!editingId">
          <el-input v-model="form.shop_id" placeholder="默认: default" />
        </el-form-item>
        <el-form-item label="凭证 JSON">
          <el-input
            v-model="credentialsJson"
            type="textarea"
            :rows="6"
            placeholder='{"client_id": "...", "client_secret": "..."}'
          />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listAdapterConfigs,
  createAdapterConfig,
  updateAdapterConfig,
  deleteAdapterConfig,
} from '@/api/listing'
import type { AdapterConfigResponse } from '@/types/listing'

const configs = ref<AdapterConfigResponse[]>([])
const loading = ref(false)
const submitting = ref(false)
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const credentialsJson = ref('{}')

const form = reactive({
  platform: 'amazon',
  shop_id: 'default',
  is_active: true,
})

const platformType = (platform: string) => {
  const map: Record<string, string> = { amazon: '', ebay: 'warning', shopify: 'success' }
  return map[platform] || 'info'
}

const parseCredentials = (): Record<string, unknown> | null => {
  try {
    return JSON.parse(credentialsJson.value)
  } catch {
    ElMessage.error('凭证 JSON 格式错误')
    return null
  }
}

const fetchConfigs = async () => {
  loading.value = true
  try {
    const res = await listAdapterConfigs()
    if (res.data.code === 200) {
      configs.value = res.data.data
    }
  } finally {
    loading.value = false
  }
}

const handleCreate = () => {
  editingId.value = null
  form.platform = 'amazon'
  form.shop_id = 'default'
  form.is_active = true
  credentialsJson.value = '{}'
  dialogVisible.value = true
}

const handleEdit = (row: AdapterConfigResponse) => {
  editingId.value = row.id
  form.platform = row.platform
  form.shop_id = row.shop_id
  form.is_active = row.is_active
  credentialsJson.value = '{}'
  dialogVisible.value = true
}

const handleSubmit = async () => {
  const creds = parseCredentials()
  if (!creds) return

  submitting.value = true
  try {
    if (editingId.value) {
      const res = await updateAdapterConfig(editingId.value, {
        credentials: creds,
        is_active: form.is_active,
      })
      if (res.data.code === 200) {
        ElMessage.success('更新成功')
      } else {
        ElMessage.error(res.data.message || '更新失败')
      }
    } else {
      const res = await createAdapterConfig({
        platform: form.platform as 'amazon' | 'ebay' | 'shopify',
        shop_id: form.shop_id,
        credentials: creds,
        is_active: form.is_active,
      })
      if (res.data.code === 200) {
        ElMessage.success('创建成功')
      } else {
        ElMessage.error(res.data.message || '创建失败')
      }
    }
    dialogVisible.value = false
    await fetchConfigs()
  } finally {
    submitting.value = false
  }
}

const handleDelete = async (row: AdapterConfigResponse) => {
  try {
    await ElMessageBox.confirm(`确定删除 ${row.platform}/${row.shop_id} 的配置？`, '确认删除')
    const res = await deleteAdapterConfig(row.id)
    if (res.data.code === 200) {
      ElMessage.success('删除成功')
      await fetchConfigs()
    } else {
      ElMessage.error(res.data.message || '删除失败')
    }
  } catch {
    // User cancelled
  }
}

onMounted(() => {
  fetchConfigs()
})
</script>
