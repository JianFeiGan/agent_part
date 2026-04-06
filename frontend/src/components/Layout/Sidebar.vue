<template>
  <div class="sidebar">
    <!-- Logo -->
    <div class="logo">
      <el-icon :size="32" color="#409eff">
        <PictureFilled />
      </el-icon>
      <span v-show="!isCollapse" class="logo-text">视觉生成器</span>
    </div>

    <!-- 导航菜单 -->
    <el-menu
      :default-active="activeMenu"
      :collapse="isCollapse"
      :collapse-transition="false"
      class="sidebar-menu"
      router
    >
      <el-menu-item index="/dashboard">
        <el-icon><Odometer /></el-icon>
        <template #title>仪表盘</template>
      </el-menu-item>

      <el-sub-menu index="products">
        <template #title>
          <el-icon><Goods /></el-icon>
          <span>商品管理</span>
        </template>
        <el-menu-item index="/products">
          <el-icon><List /></el-icon>
          <template #title>商品列表</template>
        </el-menu-item>
        <el-menu-item index="/products/create">
          <el-icon><Plus /></el-icon>
          <template #title>创建商品</template>
        </el-menu-item>
      </el-sub-menu>

      <el-sub-menu index="tasks">
        <template #title>
          <el-icon><List /></el-icon>
          <span>任务管理</span>
        </template>
        <el-menu-item index="/tasks">
          <el-icon><Document /></el-icon>
          <template #title>任务列表</template>
        </el-menu-item>
        <el-menu-item index="/tasks/create">
          <el-icon><Plus /></el-icon>
          <template #title>创建任务</template>
        </el-menu-item>
      </el-sub-menu>

      <el-sub-menu index="knowledge">
        <template #title>
          <el-icon><Collection /></el-icon>
          <span>知识库</span>
        </template>
        <el-menu-item index="/knowledge">
          <el-icon><Folder /></el-icon>
          <template #title>文档管理</template>
        </el-menu-item>
        <el-menu-item index="/knowledge/search">
          <el-icon><Search /></el-icon>
          <template #title>检索测试</template>
        </el-menu-item>
      </el-sub-menu>
    </el-menu>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAppStore } from '@/stores/app'

/**
 * 侧边栏组件
 * @description 导航菜单侧边栏
 */

const route = useRoute()
const appStore = useAppStore()

// 当前激活的菜单
const activeMenu = computed(() => route.path)

// 侧边栏折叠状态
const isCollapse = computed(() => appStore.isCollapse)
</script>

<style scoped>
.sidebar {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: #304156;
}

.logo {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  height: 60px;
  padding: 0 16px;
  background-color: #263445;
}

.logo-text {
  font-size: 18px;
  font-weight: 600;
  color: #fff;
  white-space: nowrap;
}

.sidebar-menu {
  flex: 1;
  border-right: none;
  background-color: #304156;
}

.sidebar-menu:not(.el-menu--collapse) {
  width: 220px;
}

/* 覆盖 Element Plus 默认样式 */
.sidebar-menu .el-menu-item {
  color: #bfcbd9;
}

.sidebar-menu .el-menu-item:hover {
  background-color: #263445;
}

.sidebar-menu .el-menu-item.is-active {
  color: #409eff;
  background-color: #263445;
}

.sidebar-menu .el-sub-menu__title {
  color: #bfcbd9;
}

.sidebar-menu .el-sub-menu__title:hover {
  background-color: #263445;
}

:deep(.el-menu) {
  background-color: #304156;
}

:deep(.el-menu--collapse) {
  width: 64px;
}
</style>