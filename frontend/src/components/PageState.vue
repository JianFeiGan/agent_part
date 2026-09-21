<template>
  <div class="page-state" :class="`page-state--${kind}`">
    <el-skeleton v-if="kind === 'loading'" :rows="rows" animated />

    <el-empty v-else-if="kind === 'empty'" :description="emptyDescription">
      <slot name="empty-action">
        <el-button v-if="emptyActionText" type="primary" @click="$emit('empty-action')">
          {{ emptyActionText }}
        </el-button>
      </slot>
    </el-empty>

    <div v-else-if="kind === 'error'" class="page-state__error">
      <el-alert :title="errorTitle" type="error" show-icon :closable="false" />
      <el-button type="primary" @click="$emit('retry')" :loading="retrying">
        {{ retryText }}
      </el-button>
    </div>

    <slot v-else />
  </div>
</template>

<script setup lang="ts">
import type { PageKind } from '@/utils/pageState'

/**
 * 主链路共享页面三态：loading / empty / error / ready。
 * error 只提供驻留信息与重试，全局弹错由 axios 拦截器负责。
 */
withDefaults(
  defineProps<{
    kind: PageKind
    emptyDescription?: string
    emptyActionText?: string
    errorTitle?: string
    retryText?: string
    retrying?: boolean
    rows?: number
  }>(),
  {
    emptyDescription: '暂无数据',
    emptyActionText: '',
    errorTitle: '加载失败，请稍后重试',
    retryText: '重试',
    retrying: false,
    rows: 4
  }
)

defineEmits<{
  retry: []
  'empty-action': []
}>()
</script>

<style scoped>
.page-state__error {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 12px;
  padding: 24px 0;
}
</style>
