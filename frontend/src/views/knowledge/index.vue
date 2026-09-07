<template>
  <div class="knowledge-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>知识库管理</span>
          <el-button type="primary" size="small" disabled>上传文档</el-button>
        </div>
      </template>
      <el-empty description="知识库管理功能开发中，敬请期待" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
/** 知识库管理页面（占位） */
</script>

<style scoped>
.knowledge-page {
  padding: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
