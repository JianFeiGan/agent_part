<template>
  <div class="memory-proposals">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>类目记忆审核</span>
          <el-tooltip
            v-if="showWriteActions"
            :disabled="canWrite"
            :content="writeDisabledTip"
            placement="top"
          >
            <span>
              <el-button
                type="primary"
                size="small"
                :loading="distilling"
                :disabled="!canWrite"
                @click="openDistill"
              >
                从任务提炼
              </el-button>
            </span>
          </el-tooltip>
        </div>
      </template>

      <el-form :inline="true">
        <el-form-item label="状态">
          <el-select v-model="statusFilter" clearable placeholder="全部" style="width: 140px">
            <el-option label="待审核" value="pending" />
            <el-option label="已通过" value="applied" />
            <el-option label="已拒绝" value="rejected" />
          </el-select>
        </el-form-item>
        <el-form-item label="类目">
          <el-input v-model="categoryFilter" clearable placeholder="类目" style="width: 160px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
        </el-form-item>
      </el-form>

      <PageState
        :kind="listKind"
        empty-description="暂无记忆提案，可从已完成任务提炼"
        :empty-action-text="showWriteActions ? '从任务提炼' : ''"
        error-title="提案列表加载失败"
        :retrying="loading"
        @retry="loadList"
        @empty-action="openDistill"
      >
        <el-table :data="pagedProposals" style="width: 100%">
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="category" label="类目" width="120" />
          <el-table-column prop="summary" label="摘要" min-width="200" show-overflow-tooltip />
          <el-table-column prop="confidence" label="置信度" width="100">
            <template #default="{ row }">{{ (row.confidence * 100).toFixed(0) }}%</template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="statusTag(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="170">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="160" fixed="right">
            <template #default="{ row }">
              <el-button type="primary" link @click="openDetail(row)">详情</el-button>
              <template v-if="row.status === 'pending' && showWriteActions">
                <el-tooltip :disabled="canWrite" :content="writeDisabledTip" placement="top">
                  <span class="action-btn">
                    <el-button
                      type="success"
                      link
                      :disabled="!canWrite"
                      @click="handleApprove(row)"
                    >
                      通过
                    </el-button>
                  </span>
                </el-tooltip>
                <el-tooltip :disabled="canWrite" :content="writeDisabledTip" placement="top">
                  <span class="action-btn">
                    <el-button
                      type="danger"
                      link
                      :disabled="!canWrite"
                      @click="handleReject(row)"
                    >
                      拒绝
                    </el-button>
                  </span>
                </el-tooltip>
              </template>
            </template>
          </el-table-column>
        </el-table>
      </PageState>

      <!-- 后端 list 仅支持 limit/status/category，此处对已拉取列表做客户端分页 -->
      <el-pagination
        v-if="total > 0"
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        class="pagination"
      />
    </el-card>

    <el-dialog v-model="detailVisible" title="提案详情" width="720px">
      <template v-if="current">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="ID">{{ current.id }}</el-descriptions-item>
          <el-descriptions-item label="类目">{{ current.category }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ statusLabel(current.status) }}</el-descriptions-item>
          <el-descriptions-item label="置信度">{{ (current.confidence * 100).toFixed(0) }}%</el-descriptions-item>
          <el-descriptions-item label="来源" :span="2">
            {{ current.source_type }} / {{ current.source_ref || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="摘要" :span="2">{{ current.summary || '-' }}</el-descriptions-item>
        </el-descriptions>
        <h4>最佳实践</h4>
        <ul>
          <li v-for="(item, i) in current.best_practices" :key="i">{{ item }}</li>
        </ul>
        <h4>负面模式</h4>
        <ul>
          <li v-for="(item, i) in current.negative_patterns" :key="i">{{ item }}</li>
        </ul>
        <h4>风格指南</h4>
        <pre class="json-block">{{ prettyJson(current.style_guidelines) }}</pre>
        <h4>性能提示</h4>
        <pre class="json-block">{{ prettyJson(current.performance_hints) }}</pre>
      </template>
    </el-dialog>

    <el-dialog v-model="distillVisible" title="从任务提炼记忆" width="520px">
      <el-form label-width="100px">
        <el-form-item label="任务 ID" required>
          <el-input v-model="distillForm.taskId" placeholder="task_xxx" />
        </el-form-item>
        <el-form-item label="类目">
          <el-input v-model="distillForm.category" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="distillVisible = false">取消</el-button>
        <el-button type="primary" :loading="distilling" @click="handleDistill">提炼</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listMemoryProposals,
  approveMemoryProposal,
  rejectMemoryProposal,
  distillMemory,
  readAuthScopes,
  hasMemoryWrite,
  isForbiddenError,
  buildDistillGenerationResult
} from '@/api/memoryProposals'
import type { MemoryProposal } from '@/api/memoryProposals'
import { getTaskById } from '@/api/tasks'
import { formatTime } from '@/utils/format'
import PageState from '@/components/PageState.vue'

/** 类目记忆 HITL 审核页 */
const loading = ref(false)
const loadFailed = ref(false)
const distilling = ref(false)
const detailVisible = ref(false)
const distillVisible = ref(false)

const proposals = ref<MemoryProposal[]>([])
const current = ref<MemoryProposal | null>(null)
const statusFilter = ref<string | undefined>('pending')
const categoryFilter = ref('')

// 客户端分页（后端 list 只有 limit，没有 page）
const page = ref(1)
const pageSize = ref(10)
const LIST_LIMIT = 100

const distillForm = ref({ taskId: '', category: '' })

// 权限门控：已知 scope 无 write → 隐藏；仅感知到 403 → 禁用+提示
const knownScopes = readAuthScopes()
const writeDeniedBy403 = ref(false)
const showWriteActions = computed(() => hasMemoryWrite(knownScopes))
const canWrite = computed(() => showWriteActions.value && !writeDeniedBy403.value)
const writeDisabledTip = computed(() =>
  writeDeniedBy403.value ? '上次写入被拒绝（403），当前账号可能缺少 memory:write' : '无 memory:write 权限'
)

const total = computed(() => proposals.value.length)
const pagedProposals = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return proposals.value.slice(start, start + pageSize.value)
})

const listKind = computed<'loading' | 'empty' | 'error' | 'ready'>(() => {
  if (loading.value && !proposals.value.length) return 'loading'
  if (loadFailed.value && !proposals.value.length) return 'error'
  if (!proposals.value.length) return 'empty'
  return 'ready'
})

function statusLabel(status: string) {
  const map: Record<string, string> = {
    pending: '待审核',
    applied: '已通过',
    rejected: '已拒绝'
  }
  return map[status] ?? status
}

function statusTag(status: string) {
  const map: Record<string, string> = {
    pending: 'warning',
    applied: 'success',
    rejected: 'info'
  }
  return map[status] ?? 'info'
}

function prettyJson(value: unknown): string {
  if (value == null) return '-'
  if (typeof value === 'object' && Object.keys(value as object).length === 0) return '{}'
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

function noteWriteError(error: unknown) {
  if (isForbiddenError(error)) {
    writeDeniedBy403.value = true
  }
}

function handleSearch() {
  page.value = 1
  loadList()
}

async function loadList() {
  loading.value = true
  loadFailed.value = false
  try {
    proposals.value = await listMemoryProposals({
      status: statusFilter.value,
      category: categoryFilter.value || undefined,
      limit: LIST_LIMIT
    })
    // 数据变少时回退页码，避免停在空页
    const maxPage = Math.max(1, Math.ceil(proposals.value.length / pageSize.value))
    if (page.value > maxPage) page.value = maxPage
  } catch {
    loadFailed.value = true
  } finally {
    loading.value = false
  }
}

function openDetail(row: MemoryProposal) {
  current.value = row
  detailVisible.value = true
}

function openDistill() {
  if (!canWrite.value) return
  distillVisible.value = true
}

async function handleDistill() {
  if (!distillForm.value.taskId) {
    ElMessage.warning('请填写任务 ID')
    return
  }
  distilling.value = true
  const taskId = distillForm.value.taskId.trim()
  try {
    // 先拉真实任务详情，再组装 generation_result（不再只传 { task_id }）
    const taskDetail = await getTaskById(taskId)
    const generationResult = buildDistillGenerationResult(taskDetail, taskId)
    await distillMemory({
      source_type: 'task_completion',
      source_ref: taskId,
      generation_result: generationResult,
      category: distillForm.value.category || undefined
    })
    ElMessage.success('已生成待审核提案')
    distillVisible.value = false
    statusFilter.value = 'pending'
    page.value = 1
    await loadList()
  } catch (error) {
    noteWriteError(error)
  } finally {
    distilling.value = false
  }
}

async function handleApprove(row: MemoryProposal) {
  if (!canWrite.value) return
  try {
    // 可选摘要覆盖：预填原摘要，清空则不覆盖
    const { value } = await ElMessageBox.prompt(
      `通过提案 #${row.id} 并写入类目记忆？可修改摘要（留空使用原摘要）。`,
      '确认通过',
      {
        confirmButtonText: '通过',
        cancelButtonText: '取消',
        inputValue: row.summary ?? '',
        inputPlaceholder: '摘要（可选）'
      }
    )
    const summary = typeof value === 'string' ? value.trim() : ''
    await approveMemoryProposal(row.id, summary ? { summary } : undefined)
    ElMessage.success('已通过')
    await loadList()
  } catch (error) {
    noteWriteError(error)
  }
}

async function handleReject(row: MemoryProposal) {
  if (!canWrite.value) return
  try {
    const { value } = await ElMessageBox.prompt('请填写拒绝理由', '拒绝提案', {
      inputValidator: (v: string) => (v && v.trim().length > 0) || '理由必填'
    })
    await rejectMemoryProposal(row.id, value.trim())
    ElMessage.success('已拒绝')
    await loadList()
  } catch (error) {
    noteWriteError(error)
  }
}

onMounted(loadList)
</script>

<style scoped>
.memory-proposals {
  padding: 0;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
h4 {
  margin: 12px 0 6px;
  font-weight: 500;
}
.json-block {
  margin: 0 0 8px;
  padding: 10px 12px;
  background: var(--el-fill-color-light);
  border-radius: 4px;
  font-size: 12px;
  line-height: 1.5;
  max-height: 240px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
.pagination {
  margin-top: 12px;
  justify-content: flex-end;
}
.action-btn {
  display: inline-block;
}
</style>
