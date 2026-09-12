<template>
  <div class="knowledge-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>知识库管理</span>
          <div class="header-actions">
            <el-button size="small" @click="router.push('/knowledge/search')">检索测试</el-button>
            <el-button type="primary" size="small" @click="openCreate">新建文档</el-button>
            <el-button type="success" size="small" @click="fileInput?.click()">上传文件</el-button>
            <input
              ref="fileInput"
              type="file"
              accept=".txt,.md,.csv,.json"
              hidden
              @change="handleUpload"
            />
          </div>
        </div>
      </template>

      <el-row :gutter="12" class="stats-row">
        <el-col :span="8">
          <el-statistic title="文档数" :value="stats.total_documents" />
        </el-col>
        <el-col :span="8">
          <el-statistic title="分块数" :value="stats.total_chunks" />
        </el-col>
        <el-col :span="8">
          <div class="type-stats">
            <el-tag
              v-for="(count, type) in stats.documents_by_type"
              :key="type"
              size="small"
              style="margin: 2px"
            >
              {{ DOC_TYPE_LABELS[type as DocType] || type }}: {{ count }}
            </el-tag>
          </div>
        </el-col>
      </el-row>

      <el-form :inline="true" class="search-form">
        <el-form-item label="类型">
          <el-select v-model="queryParams.doc_type" clearable placeholder="全部类型">
            <el-option
              v-for="(label, value) in DOC_TYPE_LABELS"
              :key="value"
              :label="label"
              :value="value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="类目">
          <el-input v-model="queryParams.category" clearable placeholder="类目" style="width: 160px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">搜索</el-button>
        </el-form-item>
      </el-form>

      <PageState
        :kind="listKind"
        empty-description="知识库为空，上传品牌规范或类目知识以增强生成质量"
        empty-action-text="上传文件"
        error-title="知识库列表加载失败"
        :retrying="loading"
        @retry="loadAll"
        @empty-action="fileInput?.click()"
      >
        <el-table :data="documents" style="width: 100%">
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
          <el-table-column prop="doc_type" label="类型" width="120">
            <template #default="{ row }">
              <el-tag size="small">{{ DOC_TYPE_LABELS[row.doc_type as DocType] || row.doc_type }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="category" label="类目" width="120" />
          <el-table-column prop="version" label="版本" width="80" />
          <el-table-column prop="updated_at" label="更新时间" width="180">
            <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="{ row }">
              <el-button type="danger" link @click="handleDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </PageState>

      <el-pagination
        v-model:current-page="queryParams.page"
        v-model:page-size="queryParams.page_size"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        class="pagination"
        @size-change="loadAll"
        @current-change="loadAll"
      />
    </el-card>

    <el-dialog v-model="createVisible" title="新建知识文档" width="640px">
      <el-form :model="createForm" label-width="90px">
        <el-form-item label="标题" required>
          <el-input v-model="createForm.title" maxlength="255" />
        </el-form-item>
        <el-form-item label="类型" required>
          <el-select v-model="createForm.doc_type" style="width: 100%">
            <el-option
              v-for="(label, value) in DOC_TYPE_LABELS"
              :key="value"
              :label="label"
              :value="value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="类目">
          <el-input v-model="createForm.category" placeholder="可选" />
        </el-form-item>
        <el-form-item label="内容" required>
          <el-input v-model="createForm.content" type="textarea" :rows="8" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleCreate">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getDocuments,
  createDocument,
  uploadDocument,
  deleteDocument,
  getKnowledgeStats
} from '@/api/knowledge'
import { DOC_TYPE_LABELS } from '@/types/knowledge'
import type { DocType, KnowledgeDocument, KnowledgeStats } from '@/types/knowledge'
import { formatTime } from '@/utils/format'
import PageState from '@/components/PageState.vue'

/** 知识库管理：对接真实 /knowledge API（非 graphs 占位） */
const router = useRouter()

const loading = ref(false)
const loadFailed = ref(false)
const submitting = ref(false)
const createVisible = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

const documents = ref<KnowledgeDocument[]>([])
const total = ref(0)
const stats = ref<KnowledgeStats>({
  total_documents: 0,
  total_chunks: 0,
  documents_by_type: {}
})

const queryParams = reactive({
  doc_type: undefined as DocType | undefined,
  category: '',
  page: 1,
  page_size: 10
})

const createForm = reactive({
  title: '',
  doc_type: 'brand_guide' as DocType,
  category: '',
  content: ''
})

const listKind = computed<'loading' | 'empty' | 'error' | 'ready'>(() => {
  if (loading.value && !documents.value.length) return 'loading'
  if (loadFailed.value && !documents.value.length) return 'error'
  if (!documents.value.length) return 'empty'
  return 'ready'
})

async function loadDocuments() {
  loading.value = true
  loadFailed.value = false
  try {
    const page = await getDocuments({
      doc_type: queryParams.doc_type,
      category: queryParams.category || undefined,
      page: queryParams.page,
      page_size: queryParams.page_size
    })
    documents.value = page.documents
    total.value = page.total
  } catch {
    loadFailed.value = true
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  try {
    stats.value = await getKnowledgeStats()
  } catch {
    // 统计失败不阻塞列表
  }
}

function loadAll() {
  void loadDocuments()
  void loadStats()
}

function handleSearch() {
  queryParams.page = 1
  loadAll()
}

function openCreate() {
  createVisible.value = true
}

async function handleCreate() {
  if (!createForm.title || !createForm.content) {
    ElMessage.warning('请填写标题和内容')
    return
  }
  submitting.value = true
  try {
    await createDocument({
      title: createForm.title,
      doc_type: createForm.doc_type,
      category: createForm.category || undefined,
      content: createForm.content
    })
    ElMessage.success('文档已创建')
    createVisible.value = false
    createForm.title = ''
    createForm.content = ''
    loadAll()
  } catch {
    // 拦截器已提示
  } finally {
    submitting.value = false
  }
}

async function handleUpload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  try {
    await uploadDocument(file, createForm.doc_type || 'category_knowledge', createForm.category || undefined)
    ElMessage.success('上传成功')
    loadAll()
  } catch {
    // 拦截器已提示
  } finally {
    input.value = ''
  }
}

async function handleDelete(row: KnowledgeDocument) {
  try {
    await ElMessageBox.confirm(`确定删除文档「${row.title}」？`, '提示', {
      type: 'warning'
    })
    await deleteDocument(row.id)
    ElMessage.success('已删除')
    loadAll()
  } catch {
    // 用户取消
  }
}

onMounted(loadAll)
</script>

<style scoped>
.knowledge-page {
  padding: 0;
}
.card-header,
.header-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header-actions {
  gap: 8px;
}
.stats-row {
  margin-bottom: 12px;
}
.type-stats {
  min-height: 40px;
}
.pagination {
  margin-top: 12px;
  justify-content: flex-end;
}
</style>
