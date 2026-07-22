<template>
  <div class="model-providers">
    <!-- 筛选栏 -->
    <el-card style="margin-bottom: 16px">
      <div class="filter-bar">
        <el-radio-group v-model="filterType" @change="loadProviders">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button value="llm">LLM</el-radio-button>
          <el-radio-button value="image">图片</el-radio-button>
          <el-radio-button value="video">视频</el-radio-button>
        </el-radio-group>
        <el-button type="primary" @click="handleCreate">
          <el-icon><Plus /></el-icon>
          新增厂商
        </el-button>
      </div>
    </el-card>

    <!-- 厂商列表 -->
    <el-card>
      <el-table :data="providers" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="display_name" label="厂商名称" width="120" />
        <el-table-column prop="provider_type" label="类型" width="80">
          <template #default="{ row }">
            <el-tag :type="providerTypeTag(row.provider_type)">
              {{ providerTypeLabel(row.provider_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="default_model" label="默认模型" width="180" />
        <el-table-column prop="base_url" label="API 基址" min-width="240" show-overflow-tooltip />
        <el-table-column prop="api_key_masked" label="API Key" width="140" />
        <el-table-column prop="protocol" label="协议" width="140">
          <template #default="{ row }">
            <el-tag size="small" :type="row.protocol === 'openai_compatible' ? '' : 'warning'">
              {{ row.protocol === 'openai_compatible' ? 'OpenAI 兼容' : '自定义 REST' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="默认" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.is_default" type="warning" size="small">默认</el-tag>
            <el-button v-else size="small" text type="primary" @click="handleSetDefault(row)">
              设为默认
            </el-button>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleTest(row)" :loading="row._testing">
              测试
            </el-button>
            <el-button size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑厂商' : '新增厂商'"
      width="600px"
      destroy-on-close
    >
      <el-form :model="form" :rules="formRules" ref="formRef" label-width="120px">
        <el-form-item label="厂商标识" prop="name" v-if="!editingId">
          <el-input v-model="form.name" placeholder="如: sensenova, dashscope, kling" />
        </el-form-item>
        <el-form-item label="显示名称" prop="display_name">
          <el-input v-model="form.display_name" placeholder="如: 商汤科技" />
        </el-form-item>
        <el-form-item label="厂商类型" prop="provider_type" v-if="!editingId">
          <el-select v-model="form.provider_type" placeholder="选择类型" style="width: 100%">
            <el-option label="LLM（文本）" value="llm" />
            <el-option label="图片生成" value="image" />
            <el-option label="视频生成" value="video" />
          </el-select>
        </el-form-item>
        <el-form-item label="API 基址" prop="base_url">
          <el-input v-model="form.base_url" placeholder="https://api.example.com/v1" />
        </el-form-item>
        <el-form-item label="API Key" prop="api_key">
          <el-input
            v-model="form.api_key"
            type="password"
            show-password
            :placeholder="editingId ? '留空则不更新' : '输入 API Key'"
          />
        </el-form-item>
        <el-form-item label="默认模型" prop="default_model">
          <el-input v-model="form.default_model" placeholder="如: sensenova-6.7-flash-lite" />
        </el-form-item>
        <el-form-item label="协议类型" prop="protocol">
          <el-select v-model="form.protocol" style="width: 100%">
            <el-option label="OpenAI 兼容" value="openai_compatible" />
            <el-option label="自定义 REST" value="custom_rest" />
          </el-select>
        </el-form-item>
        <el-form-item label="支持模型列表">
          <el-input
            v-model="supportedModelsStr"
            type="textarea"
            :rows="3"
            placeholder="每行一个模型名，如:&#10;sensenova-6.7-flash-lite&#10;deepseek-v4-flash"
          />
        </el-form-item>
        <el-form-item label="额外凭证">
          <el-input
            v-model="extraCredentialsStr"
            type="textarea"
            :rows="3"
            placeholder='JSON 格式，如:&#10;{"secret_key": "xxx"}'
          />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
        <el-form-item label="设为默认">
          <el-switch v-model="form.is_default" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">保存</el-button>
      </template>
    </el-dialog>

    <!-- 测试结果对话框 -->
    <el-dialog v-model="testResultVisible" title="连接测试结果" width="400px">
      <el-result
        :icon="testResult?.success ? 'success' : 'error'"
        :title="testResult?.success ? '连接成功' : '连接失败'"
        :sub-title="testResult?.message"
      >
        <template #extra v-if="testResult?.latency_ms">
          <el-tag>延迟: {{ testResult.latency_ms }}ms</el-tag>
        </template>
      </el-result>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import {
  listModelProviders,
  createModelProvider,
  updateModelProvider,
  deleteModelProvider,
  setDefaultModelProvider,
  testModelProvider,
} from '@/api/providers'
import type {
  ModelProviderResponse,
  ModelProviderCreate,
  ModelProviderUpdate,
  ProviderType,
} from '@/types/provider'

/** 厂商列表（带 _testing 标记） */
type ProviderRow = ModelProviderResponse & { _testing?: boolean }

const loading = ref(false)
const providers = ref<ProviderRow[]>([])
const filterType = ref('')

const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const submitting = ref(false)
const formRef = ref<FormInstance>()

const testResultVisible = ref(false)
const testResult = ref<{ success: boolean; message: string; latency_ms: number | null } | null>(null)

/** 表单数据 */
const form = reactive<ModelProviderCreate & { api_key: string }>({
  name: '',
  display_name: '',
  provider_type: 'llm',
  base_url: '',
  api_key: '',
  default_model: '',
  protocol: 'openai_compatible',
  supported_models: [],
  extra_credentials: {},
  is_active: true,
  is_default: false,
})

/** 表单校验规则 */
const formRules: FormRules = {
  name: [{ required: true, message: '请输入厂商标识', trigger: 'blur' }],
  display_name: [{ required: true, message: '请输入显示名称', trigger: 'blur' }],
  provider_type: [{ required: true, message: '请选择厂商类型', trigger: 'change' }],
  base_url: [{ required: true, message: '请输入 API 基址', trigger: 'blur' }],
  default_model: [{ required: true, message: '请输入默认模型', trigger: 'blur' }],
  protocol: [{ required: true, message: '请选择协议类型', trigger: 'change' }],
}

/** 支持模型列表（文本格式，每行一个） */
const supportedModelsStr = computed({
  get: () => (form.supported_models || []).join('\n'),
  set: (val: string) => {
    form.supported_models = val.split('\n').map(s => s.trim()).filter(Boolean)
  },
})

/** 额外凭证（JSON 文本格式） */
const extraCredentialsStr = computed({
  get: () => {
    try {
      return JSON.stringify(form.extra_credentials || {}, null, 2)
    } catch {
      return '{}'
    }
  },
  set: (val: string) => {
    try {
      form.extra_credentials = JSON.parse(val)
    } catch {
      // 解析失败不更新
    }
  },
})

/** 厂商类型标签 */
function providerTypeLabel(type: ProviderType): string {
  const map: Record<ProviderType, string> = { llm: 'LLM', image: '图片', video: '视频' }
  return map[type] || type
}

/** 厂商类型标签颜色 */
function providerTypeTag(type: ProviderType): string {
  const map: Record<ProviderType, string> = { llm: '', image: 'success', video: 'warning' }
  return map[type] || ''
}

/** 加载厂商列表 */
async function loadProviders() {
  loading.value = true
  try {
    const { data } = await listModelProviders(filterType.value || undefined)
    if (data.data) {
      providers.value = data.data.map(p => ({ ...p, _testing: false }))
    }
  } catch {
    ElMessage.error('加载厂商列表失败')
  } finally {
    loading.value = false
  }
}

/** 新增厂商 */
function handleCreate() {
  editingId.value = null
  Object.assign(form, {
    name: '',
    display_name: '',
    provider_type: 'llm',
    base_url: '',
    api_key: '',
    default_model: '',
    protocol: 'openai_compatible',
    supported_models: [],
    extra_credentials: {},
    is_active: true,
    is_default: false,
  })
  dialogVisible.value = true
}

/** 编辑厂商 */
function handleEdit(row: ProviderRow) {
  editingId.value = row.id
  Object.assign(form, {
    name: row.name,
    display_name: row.display_name,
    provider_type: row.provider_type,
    base_url: row.base_url,
    api_key: '', // 编辑时不回显 API Key
    default_model: row.default_model,
    protocol: row.protocol,
    supported_models: row.supported_models || [],
    extra_credentials: {},
    is_active: row.is_active,
    is_default: row.is_default,
  })
  dialogVisible.value = true
}

/** 提交表单 */
async function handleSubmit() {
  if (!formRef.value) return
  await formRef.value.validate()

  submitting.value = true
  try {
    if (editingId.value) {
      // 更新
      const updateData: ModelProviderUpdate = {
        display_name: form.display_name,
        base_url: form.base_url,
        default_model: form.default_model,
        protocol: form.protocol,
        is_active: form.is_active,
        supported_models: form.supported_models,
      }
      if (form.api_key) {
        updateData.api_key = form.api_key
      }
      await updateModelProvider(editingId.value, updateData)
      ElMessage.success('更新成功')
    } else {
      // 创建
      await createModelProvider(form)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    await loadProviders()
  } catch {
    ElMessage.error('操作失败')
  } finally {
    submitting.value = false
  }
}

/** 删除厂商 */
async function handleDelete(row: ProviderRow) {
  try {
    await ElMessageBox.confirm(
      `确定删除厂商「${row.display_name}」？此操作不可恢复。`,
      '删除确认',
      { type: 'warning' }
    )
    await deleteModelProvider(row.id)
    ElMessage.success('删除成功')
    await loadProviders()
  } catch {
    // 用户取消
  }
}

/** 设为默认 */
async function handleSetDefault(row: ProviderRow) {
  try {
    await setDefaultModelProvider(row.id)
    ElMessage.success('设置默认成功')
    await loadProviders()
  } catch {
    ElMessage.error('设置默认失败')
  }
}

/** 测试连接 */
async function handleTest(row: ProviderRow) {
  const idx = providers.value.findIndex(p => p.id === row.id)
  if (idx >= 0) providers.value[idx]._testing = true

  try {
    const { data } = await testModelProvider(row.id)
    testResult.value = data.data || null
    testResultVisible.value = true
  } catch {
    testResult.value = { success: false, message: '请求失败', latency_ms: null }
    testResultVisible.value = true
  } finally {
    if (idx >= 0) providers.value[idx]._testing = false
  }
}

onMounted(() => {
  loadProviders()
})
</script>

<style scoped>
.model-providers {
  padding: 0;
}

.filter-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
