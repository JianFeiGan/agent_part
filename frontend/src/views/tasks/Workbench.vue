<template>
  <div class="task-workbench" v-loading="store.loading">
    <!-- 顶部栏 -->
    <WorkbenchHeader @cancel="handleCancel" />

    <!-- 主内容区：左右分栏 -->
    <div class="workbench-body">
      <!-- 左侧：DAG 流程图 -->
      <div class="workbench-left">
        <AgentDAG />
      </div>
      <!-- 右侧：详情面板 -->
      <div class="workbench-right">
        <AgentDetailPanel />
      </div>
    </div>

    <!-- 底部：生成结果（任务完成时展示） -->
    <div v-if="store.taskDetail?.status === 'completed'" class="workbench-results">
      <el-divider>生成结果</el-divider>
      <div v-if="store.taskDetail.images?.length" class="result-section">
        <h4>生成的图片</h4>
        <div class="image-grid">
          <el-image
            v-for="img in store.taskDetail.images"
            :key="img.image_id"
            :src="img.url"
            :preview-src-list="store.taskDetail.images.map(i => i.url)"
            fit="cover"
            class="result-image"
          />
        </div>
      </div>
      <div v-if="store.taskDetail.video" class="result-section">
        <h4>生成的视频</h4>
        <video :src="store.taskDetail.video.url" controls class="result-video" />
      </div>
    </div>

    <!-- 错误信息 -->
    <div v-if="store.taskDetail?.status === 'failed' && store.taskDetail.error_message" class="workbench-error">
      <el-alert :title="store.taskDetail.error_message" type="error" show-icon :closable="false" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { cancelTask } from '@/api/tasks'
import { useWorkbenchStore } from '@/stores/workbench'
import { useTaskWebSocket } from '@/composables/useTaskWebSocket'
import WorkbenchHeader from '@/components/workbench/WorkbenchHeader.vue'
import AgentDAG from '@/components/workbench/AgentDAG.vue'
import AgentDetailPanel from '@/components/workbench/AgentDetailPanel.vue'

/**
 * Agent 可观测工作台主页面。
 * 左右分栏布局：左侧 DAG 流程图，右侧详情面板。
 * 通过 WebSocket 接收实时事件更新。
 */

const route = useRoute()
const store = useWorkbenchStore()
const taskId = route.params.id as string

// 建立 WebSocket 连接
const { disconnect } = useTaskWebSocket(taskId)

/** 取消任务 */
async function handleCancel() {
  try {
    await ElMessageBox.confirm('确定要取消该任务吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    const response = await cancelTask(taskId)
    if (response.data.code === 200) {
      ElMessage.success('任务已取消')
      disconnect()
      await store.loadTask(taskId)
    } else {
      ElMessage.error(response.data.message || '取消失败')
    }
  } catch {
    // 用户取消
  }
}

onMounted(async () => {
  await store.loadTask(taskId)
})
</script>

<style scoped>
.task-workbench {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 120px);
  background: #0d1117;
  border-radius: 8px;
  overflow: hidden;
}
.workbench-body {
  display: flex;
  flex: 1;
  min-height: 0;
}
.workbench-left {
  flex: 6;
  min-width: 0;
  padding: 12px;
}
.workbench-right {
  flex: 4;
  min-width: 0;
  border-left: 1px solid #2d2d4e;
  overflow-y: auto;
}
.workbench-results {
  padding: 16px;
  border-top: 1px solid #2d2d4e;
  background: #0d1117;
}
.workbench-error {
  padding: 16px;
  border-top: 1px solid #2d2d4e;
}
.result-section {
  margin-bottom: 16px;
}
.result-section h4 {
  color: #c9d1d9;
  margin-bottom: 8px;
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
.result-video {
  max-width: 100%;
  max-height: 300px;
  border-radius: 8px;
}
</style>
