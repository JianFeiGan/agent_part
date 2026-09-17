<template>
  <div class="task-workbench" v-loading="store.loading">
    <WorkbenchHeader
      :connection-label="connectionLabel"
      :connection-mode="connectionMode"
      @cancel="handleCancel"
    />

    <PageState
      :kind="pageKind"
      empty-description="任务详情为空"
      error-title="任务详情加载失败"
      @retry="reload"
    >
      <div class="workbench-main">
        <!-- 默认：任务概览（运营优先） -->
        <el-card class="overview-card" shadow="never">
          <template #header>
            <div class="overview-header">
              <span>任务概览</span>
              <el-button link type="primary" @click="showDiagnostics = !showDiagnostics">
                {{ showDiagnostics ? '收起诊断' : '展开 Agent 诊断' }}
              </el-button>
            </div>
          </template>

          <div class="overview-grid">
            <div class="overview-item">
              <span class="label">状态</span>
              <el-tag :type="getTaskStatusTagType(store.taskDetail?.status)">
                {{ getTaskStatusLabel(store.taskDetail?.status) }}
              </el-tag>
            </div>
            <div class="overview-item">
              <span class="label">进度</span>
              <el-progress
                :percentage="store.taskDetail?.progress ?? 0"
                :status="progressStatus"
                style="width: 160px"
              />
            </div>
            <div class="overview-item">
              <span class="label">当前阶段</span>
              <span>{{ stepLabel }}</span>
            </div>
            <div class="overview-item">
              <span class="label">实时通道</span>
              <span>{{ connectionLabel }}</span>
            </div>
            <div class="overview-item">
              <span class="label">Token</span>
              <span>{{ store.totalTokens }}</span>
            </div>
            <div class="overview-item">
              <span class="label">费用</span>
              <span>¥{{ store.totalCost.toFixed(3) }}</span>
            </div>
          </div>

          <el-alert
            v-if="store.taskDetail?.status === TaskStatus.FAILED && store.taskDetail.error_message"
            class="overview-error"
            type="error"
            :title="store.taskDetail.error_message"
            show-icon
            :closable="false"
          />
        </el-card>

        <!-- 资产结果：完成态优先可见 -->
        <el-card v-if="isTerminal" class="results-card" shadow="never">
          <template #header>
            <span>生成结果</span>
          </template>

          <div v-if="!hasAssets" class="asset-empty">
            <el-empty description="暂无图片或视频资产" :image-size="80" />
          </div>

          <template v-else>
            <div v-if="store.taskDetail?.images?.length" class="result-section">
              <h4>图片</h4>
              <div class="image-grid">
                <div
                  v-for="img in store.taskDetail.images"
                  :key="img.image_id"
                  class="asset-tile"
                >
                  <el-image
                    v-if="img.url"
                    :src="img.url"
                    :preview-src-list="imageUrls"
                    fit="cover"
                    class="result-image"
                  />
                  <div v-else class="asset-broken">图片地址不可用</div>
                  <el-button
                    size="small"
                    type="primary"
                    link
                    :disabled="!img.url"
                    @click="handleDownload(img.url, `${img.image_id || 'image'}.png`)"
                  >
                    下载
                  </el-button>
                </div>
              </div>
            </div>

            <div v-if="store.taskDetail?.video?.url" class="result-section">
              <h4>视频</h4>
              <video :src="store.taskDetail.video.url" controls class="result-video" />
              <div>
                <el-button
                  size="small"
                  type="primary"
                  @click="handleDownload(store.taskDetail.video.url, `${store.taskDetail.video.video_id || 'video'}.mp4`)"
                >
                  下载视频
                </el-button>
              </div>
            </div>
            <div v-else-if="store.taskDetail?.video" class="asset-broken">
              视频地址不可用
            </div>
          </template>
        </el-card>

        <!-- 二级诊断：默认折叠 -->
        <el-card v-show="showDiagnostics" class="diagnostics-card" shadow="never">
          <template #header>
            <span>Agent 执行诊断</span>
          </template>
          <div class="workbench-body">
            <div class="workbench-left">
              <AgentDAG />
            </div>
            <div class="workbench-right">
              <AgentDetailPanel />
            </div>
          </div>
        </el-card>
      </div>
    </PageState>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { cancelTask } from '@/api/tasks'
import { useWorkbenchStore } from '@/stores/workbench'
import { useTaskStatusCoordinator } from '@/composables/useTaskStatusCoordinator'
import { downloadFile } from '@/utils/download'
import { resolvePageKind } from '@/utils/pageState'
import { getTaskStatusLabel, getTaskStatusTagType } from '@/utils/format'
import { TaskStatus, isTerminalTaskStatus } from '@/types/task'
import PageState from '@/components/PageState.vue'
import WorkbenchHeader from '@/components/workbench/WorkbenchHeader.vue'
import AgentDAG from '@/components/workbench/AgentDAG.vue'
import AgentDetailPanel from '@/components/workbench/AgentDetailPanel.vue'

/**
 * 任务工作台：默认概览优先，Agent 诊断二级展开。
 */

const route = useRoute()
const store = useWorkbenchStore()
const taskId = route.params.id as string

const showDiagnostics = ref(false)
const loadError = ref(false)

const { connectionLabel, connectionMode } = useTaskStatusCoordinator(taskId, {
  onFirstLoadError: () => {
    loadError.value = true
  }
})

const isTerminal = computed(() => isTerminalTaskStatus(store.taskDetail?.status))

const hasAssets = computed(() => {
  const d = store.taskDetail
  return !!(d?.images?.length || d?.video?.url)
})

const imageUrls = computed(() =>
  (store.taskDetail?.images ?? []).map(i => i.url).filter(Boolean)
)

const progressStatus = computed(() => {
  const s = store.taskDetail?.status
  if (s === TaskStatus.COMPLETED) return 'success' as const
  if (s === TaskStatus.FAILED || s === TaskStatus.CANCELLED) return 'exception' as const
  return undefined
})

const stepLabel = computed(() => store.taskDetail?.current_step || '-')

const pageKind = computed(() =>
  resolvePageKind({
    loading: store.loading,
    failed: loadError.value,
    hasData: !!store.taskDetail
  })
)

async function reload() {
  loadError.value = false
  try {
    await store.loadTask(taskId)
  } catch {
    loadError.value = true
  }
}

async function handleDownload(url: string, filename: string) {
  try {
    await downloadFile(url, filename)
    ElMessage.success('已开始下载')
  } catch {
    ElMessage.error('下载失败')
  }
}

async function handleCancel() {
  try {
    await ElMessageBox.confirm('确定要取消该任务吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await cancelTask(taskId)
    ElMessage.success('任务已取消')
    await store.loadTask(taskId)
  } catch {
    // 用户取消或请求失败
  }
}
</script>

<style scoped>
.task-workbench {
  padding: 0;
}
.workbench-main {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.overview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.overview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px 16px;
}
.overview-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.overview-item .label {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.overview-error {
  margin-top: 12px;
}
.image-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}
.asset-tile {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}
.result-image {
  width: 160px;
  height: 160px;
  border-radius: 6px;
  background: var(--el-fill-color-light);
}
.result-video {
  width: min(640px, 100%);
  max-height: 360px;
  background: #000;
  border-radius: 6px;
}
.asset-broken {
  color: var(--el-color-warning);
  font-size: 13px;
  padding: 12px;
}
.workbench-body {
  display: flex;
  gap: 12px;
  min-height: 420px;
  background: #1e1e1e;
  border-radius: 8px;
  padding: 12px;
}
.workbench-left {
  flex: 1.2;
  min-width: 0;
}
.workbench-right {
  flex: 1;
  min-width: 280px;
}
.result-section h4 {
  margin: 0 0 8px;
  font-weight: 500;
}
</style>
