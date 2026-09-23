import { nextTick } from 'vue'
import type { App } from 'vue'

/** 在 container 内按包含文本查找按钮 */
export function findButton(
  container: HTMLElement,
  text: string
): HTMLButtonElement | undefined {
  return Array.from(container.querySelectorAll('button')).find(b =>
    b.textContent?.includes(text)
  )
}

/** 冲刷微任务队列（fake timers 下也可用，微任务不受时间伪造影响） */
export async function flushMicrotasks(times = 20): Promise<void> {
  for (let i = 0; i < times; i++) await Promise.resolve()
}

/**
 * 宏任务 + 渲染冲刷：setTimeout(0) 让出事件循环，可排空任意长度的
 * 微任务链（如路由多级导航 promise），再 nextTick 等渲染。
 */
export async function flushTasks(times = 5): Promise<void> {
  for (let i = 0; i < times; i++) {
    await new Promise(r => setTimeout(r, 0))
    await nextTick()
  }
}

const mounted: Array<{ app: App; container: HTMLElement }> = []

/** 登记已挂载的应用，配合 unmountAll 在 afterEach 统一清理 */
export function trackMount(app: App, container: HTMLElement): void {
  mounted.push({ app, container })
}

/** 卸载全部已登记应用并移除容器 */
export function unmountAll(): void {
  while (mounted.length) {
    const { app, container } = mounted.pop()!
    app.unmount()
    container.remove()
  }
}
