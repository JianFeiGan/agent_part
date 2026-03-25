import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

/**
 * 应用状态管理
 * @description 管理应用全局状态，如侧边栏折叠、主题等
 */
export const useAppStore = defineStore('app', () => {
  // 状态
  const isCollapse = ref(false)
  const isLoading = ref(false)
  const theme = ref<'light' | 'dark'>('light')

  // 计算属性
  const sidebarWidth = computed(() => isCollapse.value ? '64px' : '220px')

  // 方法
  /**
   * 切换侧边栏折叠状态
   */
  function toggleCollapse() {
    isCollapse.value = !isCollapse.value
  }

  /**
   * 设置加载状态
   */
  function setLoading(loading: boolean) {
    isLoading.value = loading
  }

  /**
   * 切换主题
   */
  function toggleTheme() {
    theme.value = theme.value === 'light' ? 'dark' : 'light'
    // 可以在这里添加主题切换的逻辑
    document.documentElement.setAttribute('data-theme', theme.value)
  }

  return {
    // 状态
    isCollapse,
    isLoading,
    theme,
    // 计算属性
    sidebarWidth,
    // 方法
    toggleCollapse,
    setLoading,
    toggleTheme
  }
})