<template>
  <div class="sidebar">
    <!-- Logo -->
    <div class="logo">
      <div class="logo-icon">
        <el-icon :size="24"><PictureFilled /></el-icon>
      </div>
      <transition name="fade-text">
        <span v-show="!isCollapse" class="logo-text">视觉生成器</span>
      </transition>
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

      <el-sub-menu index="listing">
        <template #title>
          <el-icon><Promotion /></el-icon>
          <span>刊登工具</span>
        </template>
        <el-menu-item index="/listing/import">
          <el-icon><Upload /></el-icon>
          <template #title>商品导入</template>
        </el-menu-item>
        <el-menu-item index="/listing/tasks">
          <el-icon><List /></el-icon>
          <template #title>刊登任务</template>
        </el-menu-item>
        <el-menu-item index="/listing/configs">
          <el-icon><Setting /></el-icon>
          <template #title>适配器配置</template>
        </el-menu-item>
      </el-sub-menu>

      <el-sub-menu index="conversation">
        <template #title>
          <el-icon><ChatDotRound /></el-icon>
          <span>AI 会话</span>
        </template>
        <el-menu-item index="/conversation">
          <el-icon><DataLine /></el-icon>
          <template #title>会话记录</template>
        </el-menu-item>
      </el-sub-menu>
    </el-menu>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAppStore } from '@/stores/app'

const route = useRoute()
const appStore = useAppStore()
const activeMenu = computed(() => route.path)
const isCollapse = computed(() => appStore.isCollapse)
</script>

<style scoped>
.sidebar {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--sidebar-bg);
}

/* Logo */
.logo {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  height: 60px;
  padding: 0 16px;
  background: var(--sidebar-bg-dark);
  border-bottom: 1px solid var(--sidebar-divider);
}

.logo-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: linear-gradient(135deg, #3b6df0, #06b6d4);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(59, 109, 240, 0.4);
}

.logo-text {
  font-size: 16px;
  font-weight: 700;
  color: #fff;
  white-space: nowrap;
  letter-spacing: 0.3px;
}

.fade-text-enter-active,
.fade-text-leave-active {
  transition: opacity 0.2s ease;
}

.fade-text-enter-from,
.fade-text-leave-to {
  opacity: 0;
}

/* 菜单 */
.sidebar-menu {
  flex: 1;
  border-right: none !important;
  background-color: var(--sidebar-bg) !important;
  padding-top: 12px;
  overflow-y: auto;

  /* 覆盖 Element Plus 菜单 CSS 变量 */
  --el-menu-active-color: #ffffff !important;
  --el-menu-hover-bg-color: var(--sidebar-hover) !important;
  --el-menu-hover-text-color: #c8d6e5 !important;
  --el-menu-bg-color: var(--sidebar-bg) !important;
  --el-menu-text-color: var(--sidebar-text) !important;
}

.sidebar-menu:not(.el-menu--collapse) {
  width: 220px;
}

/* 菜单项 */
.sidebar-menu .el-menu-item {
  color: var(--sidebar-text) !important;
  height: 42px !important;
  line-height: 42px !important;
  margin: 2px 10px;
  border-radius: 8px !important;
  transition: all var(--transition-fast) !important;
  font-size: 13.5px;
}

.sidebar-menu .el-menu-item:hover {
  background-color: var(--sidebar-hover) !important;
  color: #c8d6e5 !important;
}

.sidebar-menu .el-menu-item.is-active {
  color: #fff !important;
  background: var(--sidebar-active-bg) !important;
  box-shadow: var(--sidebar-active-shadow);
  font-weight: 600;
}

/* 穿透：确保 Element Plus 内部文字节点也继承颜色 */
:deep(.el-menu-item.is-active) {
  color: #fff !important;
}

:deep(.el-menu-item.is-active .el-menu-item__text) {
  color: #fff !important;
}

:deep(.el-menu-item.is-active .el-icon) {
  color: #fff !important;
}

/* 子菜单标题 */
.sidebar-menu .el-sub-menu__title {
  color: var(--sidebar-text) !important;
  height: 42px !important;
  line-height: 42px !important;
  margin: 2px 10px;
  border-radius: 8px !important;
  transition: all var(--transition-fast) !important;
  font-size: 13.5px;
}

.sidebar-menu .el-sub-menu__title:hover {
  background-color: var(--sidebar-hover) !important;
  color: #c8d6e5 !important;
}

/* 展开的子菜单标题也高亮 */
:deep(.el-sub-menu.is-opened > .el-sub-menu__title) {
  color: #c8d6e5 !important;
}

:deep(.el-sub-menu.is-opened > .el-sub-menu__title .el-icon) {
  color: #c8d6e5 !important;
}

/* 子菜单图标颜色 */
.sidebar-menu .el-sub-menu__title .el-icon,
.sidebar-menu .el-menu-item .el-icon {
  color: var(--sidebar-text);
  transition: color var(--transition-fast);
}

.sidebar-menu .el-menu-item:hover .el-icon,
.sidebar-menu .el-sub-menu__title:hover .el-icon {
  color: #c8d6e5;
}

.sidebar-menu .el-menu-item.is-active .el-icon {
  color: #fff;
}

/* 子菜单内嵌菜单 */
:deep(.el-menu) {
  background-color: var(--sidebar-bg) !important;
}

:deep(.el-sub-menu .el-menu) {
  background-color: transparent !important;
}

:deep(.el-sub-menu .el-menu .el-menu-item) {
  padding-left: 48px !important;
  font-size: 13px;
}

:deep(.el-menu--collapse) {
  width: 64px;
}

/* 滚动条 */
.sidebar-menu::-webkit-scrollbar {
  width: 4px;
}

.sidebar-menu::-webkit-scrollbar-thumb {
  background-color: rgba(255, 255, 255, 0.08);
  border-radius: 2px;
}

.sidebar-menu::-webkit-scrollbar-track {
  background-color: transparent;
}
</style>
