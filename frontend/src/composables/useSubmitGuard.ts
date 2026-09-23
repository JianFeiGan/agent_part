/**
 * 提交防重守卫。
 *
 * 包裹提交动作：执行期间 `submitting` 为 true 并拒绝重入，
 * 无论成功失败都会在结束后复位，失败不触碰表单数据。
 */
import { ref } from 'vue'

export function useSubmitGuard() {
  const submitting = ref(false)

  /**
   * 执行提交动作；进行中重复调用直接返回 undefined。
   * 异常会向上抛，由调用方或全局拦截器处理。
   */
  async function run<T>(fn: () => Promise<T>): Promise<T | undefined> {
    if (submitting.value) return undefined
    submitting.value = true
    try {
      return await fn()
    } finally {
      submitting.value = false
    }
  }

  return { submitting, run }
}
