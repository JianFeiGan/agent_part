<template>
  <el-container class="layout-container">
    <!-- 侧边栏 -->
    <el-aside :width="sidebarWidth" class="layout-aside">
      <Sidebar />
    </el-aside>

    <!-- 主内容区 -->
    <el-container>
      <!-- 头部 -->
      <el-header class="layout-header">
        <div class="header-left">
          <el-icon class="collapse-btn" @click="toggleCollapse">
            <component :is="isCollapse ? 'Expand' : 'Fold'" />
          </el-icon>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="currentRoute.meta?.title">
              {{ currentRoute.meta.title }}
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <el-dropdown>
            <span class="user-info">
              <el-avatar :size="32" icon="User" class="user-avatar" />
              <span class="username">管理员</span>
              <el-icon class="arrow-icon"><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item>个人中心</el-dropdown-item>
                <el-dropdown-item>设置</el-dropdown-item>
                <el-dropdown-item divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <!-- 主体内容 -->
      <el-main class="layout-main">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAppStore } from '@/stores/app'
import Sidebar from './Sidebar.vue'

const route = useRoute()
const appStore = useAppStore()
const currentRoute = computed(() => route)
const isCollapse = computed(() => appStore.isCollapse)
const sidebarWidth = computed(() => appStore.sidebarWidth)
const toggleCollapse = () => { appStore.toggleCollapse() }
</script>

<style scoped>
.layout-container {
  height: 100vh;
  width: 100%;
}

.layout-aside {
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
  box-shadow: 4px 0 16px rgba(0, 0, 0, 0.12);
}

.layout-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--color-border-light);
  padding: 0 24px;
  height: 60px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.collapse-btn {
  font-size: 20px;
  cursor: pointer;
  color: var(--color-text-secondary);
  transition: all var(--transition-fast);
  padding: 6px;
  border-radius: 8px;
}

.collapse-btn:hover {
  color: var(--color-primary);
  background-color: var(--color-primary-bg);
}

.header-right {
  display: flex;
  align-items: center;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: var(--color-text-regular);
  padding: 6px 12px;
  border-radius: 10px;
  transition: all var(--transition-fast);
}

.user-info:hover {
  background-color: var(--color-primary-bg);
  color: var(--color-primary);
}

.user-avatar {
  background: linear-gradient(135deg, #3b6df0, #06b6d4);
  box-shadow: 0 2px 6px rgba(59, 109, 240, 0.3);
}

.username {
  font-size: 14px;
  font-weight: 600;
}

.arrow-icon {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.layout-main {
  background-color: var(--color-bg-page);
  padding: 24px;
  overflow-y: auto;
}
</style>
