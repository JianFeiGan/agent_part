<template>
  <div class="task-detail">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>任务详情 #{{ taskId }}</span>
          <el-button @click="$router.push({ name: 'ListingTaskList' })">
            返回列表
          </el-button>
        </div>
      </template>

      <el-descriptions :column="2" border v-if="task">
        <el-descriptions-item label="任务ID">{{ task.task_id }}</el-descriptions-item>
        <el-descriptions-item label="商品SKU">{{ task.product_sku }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusType(task.status)">{{ task.status }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="目标平台">
          <el-tag
            v-for="p in task.target_platforms"
            :key="p"
            size="small"
            style="margin-right: 4px"
          >
            {{ p }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- 合规报告 -->
    <el-card v-if="complianceReports" style="margin-top: 20px">
      <template #header>
        <span>合规报告</span>
      </template>

      <el-tabs>
        <el-tab-pane
          v-for="(report, platform) in complianceReports"
          :key="platform"
          :label="platform.toUpperCase()"
        >
          <el-alert
            :title="`整体结果: ${report.overall.toUpperCase()}`"
            :type="
              report.overall === 'pass'
                ? 'success'
                : report.overall === 'fail'
                  ? 'error'
                  : 'warning'
            "
            show-icon
            :closable="false"
            style="margin-bottom: 16px"
          />

          <el-table
            :data="report.text_issues"
            v-if="report.text_issues.length"
            style="margin-bottom: 16px"
          >
            <el-table-column prop="severity" label="严重度" width="80">
              <template #default="{ row }">
                <el-tag
                  :type="row.severity === 'fail' ? 'danger' : 'warning'"
                  size="small"
                >
                  {{ row.severity }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="rule" label="规则" width="100" />
            <el-table-column prop="field" label="字段" width="100" />
            <el-table-column prop="message" label="问题描述" />
            <el-table-column prop="suggestion" label="建议" />
          </el-table>

          <el-table
            :data="report.image_issues"
            v-if="report.image_issues.length"
          >
            <el-table-column prop="severity" label="严重度" width="80">
              <template #default="{ row }">
                <el-tag
                  :type="row.severity === 'fail' ? 'danger' : 'warning'"
                  size="small"
                >
                  {{ row.severity }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="rule" label="规则" width="100" />
            <el-table-column prop="field" label="字段" />
            <el-table-column prop="message" label="问题描述" />
          </el-table>

          <div v-if="report.forbidden_words?.length">
            <h4>禁词检测</h4>
            <el-tag
              v-for="word in report.forbidden_words"
              :key="word"
              type="danger"
              style="margin-right: 4px"
            >
              {{ word }}
            </el-tag>
          </div>

          <el-empty
            v-if="
              !report.text_issues.length &&
              !report.image_issues.length &&
              !report.forbidden_words?.length
            "
            description="全部通过"
          />
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 推送结果 -->
    <el-card v-if="pushResults" style="margin-top: 20px">
      <template #header>
        <span>推送结果</span>
      </template>
      <el-table :data="pushResults">
        <el-table-column prop="platform" label="平台" width="100" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.success ? 'success' : 'danger'">
              {{ row.success ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="listing_id" label="刊登ID" />
        <el-table-column prop="url" label="链接">
          <template #default="{ row }">
            <a v-if="row.url" :href="row.url" target="_blank">{{ row.url }}</a>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="error" label="错误信息" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import {
  getComplianceReport,
  getPushResults,
  listTasks,
} from '@/api/listing'
import type {
  ComplianceReportResponse,
  PushResultResponse,
  ListingTaskResponse,
} from '@/types/listing'

const route = useRoute()
const taskId = Number(route.params.id)
const task = ref<ListingTaskResponse | null>(null)
const complianceReports = ref<Record<string, ComplianceReportResponse> | null>(
  null
)
const pushResults = ref<PushResultResponse[] | null>(null)

const statusType = (status: string): string => {
  const map: Record<string, string> = {
    completed: 'success',
    published: 'success',
    reviewing: 'info',
    pending: 'warning',
    failed: 'danger',
    partial: 'warning',
  }
  return map[status] || 'info'
}

onMounted(async () => {
  // 获取任务详情
  const tasksRes = await listTasks()
  if (tasksRes.data.code === 200) {
    task.value =
      tasksRes.data.data.find((t) => t.task_id === taskId) || null
  }

  // 获取合规报告
  try {
    const compRes = await getComplianceReport(taskId)
    if (compRes.data.code === 200) {
      complianceReports.value = compRes.data.data
    }
  } catch {
    // 无合规报告
  }

  // 获取推送结果
  try {
    const pushRes = await getPushResults(taskId)
    if (pushRes.data.code === 200) {
      pushResults.value = pushRes.data.data
    }
  } catch {
    // 无推送结果
  }
})
</script>
