<template>
  <div class="memory-proposals">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>类目记忆审核</span>
          <el-button type="primary" size="small" :loading="distilling" @click="openDistill">
            从任务提炼
          </el-button>
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
          <el-button type="primary" @click="loadList">查询</el-button>
        </el-form-item>
      </el-form>

      <PageState
        :kind="listKind"
        empty-description="暂无记忆提案，可从已完成任务提炼"
        empty-action-text="从任务提炼"
        error-title="提案列表加载失败"
        :retrying="loading"
        @retry="loadList"
        @empty-action="openDistill"
      >
        <el-table :data="proposals" style="width: 100%">
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
              <template v-if="row.status === 'pending'">
                <el-button type="success" link @click="handleApprove(row)">通过</el-button>
                <el-button type="danger" link @click="handleReject(row)">拒绝</el-button>
              </template>
            </template>
          </el-table-column>
        </el-table>
      </PageState>
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
  distillMemory
} from '@/api/memoryProposals'
import type { MemoryProposal } from '@/api/memoryProposals'
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

const distillForm = ref({ taskId: '', category: '' })

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

async function loadList() {
  loading.value = true
  loadFailed.value = false
  try {
    proposals.value = await listMemoryProposals({
      status: statusFilter.value,
      category: categoryFilter.value || undefined,
      limit: 50
    })
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
  distillVisible.value = true
}

async function handleDistill() {
  if (!distillForm.value.taskId) {
    ElMessage.warning('请填写任务 ID')
    return
  }
  distilling.value = true
  try {
    await distillMemory({
      source_type: 'task_completion',
      source_ref: distillForm.value.taskId,
      generation_result: { task_id: distillForm.value.taskId },
      category: distillForm.value.category || undefined
    })
    ElMessage.success('已生成待审核提案')
    distillVisible.value = false
    statusFilter.value = 'pending'
    await loadList()
  } catch {
    // 拦截器提示
  } finally {
    distilling.value = false
  }
}

async function handleApprove(row: MemoryProposal) {
  try {
    await ElMessageBox.confirm(`通过提案 #${row.id} 并写入类目记忆？`, '确认', { type: 'info' })
    await approveMemoryProposal(row.id)
    ElMessage.success('已通过')
    await loadList()
  } catch {
    // 用户取消
  }
}

async function handleReject(row: MemoryProposal) {
  try {
    const { value } = await ElMessageBox.prompt('请填写拒绝理由', '拒绝提案', {
      inputValidator: (v: string) => (v && v.trim().length > 0) || '理由必填'
    })
    await rejectMemoryProposal(row.id, value.trim())
    ElMessage.success('已拒绝')
    await loadList()
  } catch {
    // 用户取消
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
</style>
