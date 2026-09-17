import { describe, it, expect } from 'vitest'
import type { LocationQuery } from 'vue-router'
import { resolvePreselectedProductId, applyProductPrefill } from '@/composables/useTaskCreatePrefill'
import { useSubmitGuard } from '@/composables/useSubmitGuard'

describe('resolvePreselectedProductId', () => {
  it('URL 携带 product_id 时返回该 ID', () => {
    const query: LocationQuery = { product_id: 'p1' }
    expect(resolvePreselectedProductId(query)).toBe('p1')
  })

  it('无 product_id 时返回 null', () => {
    expect(resolvePreselectedProductId({})).toBeNull()
  })

  it('product_id 为空字符串时返回 null', () => {
    expect(resolvePreselectedProductId({ product_id: '' })).toBeNull()
  })

  it('product_id 为数组（重复参数）时取第一个', () => {
    expect(resolvePreselectedProductId({ product_id: ['p1', 'p2'] })).toBe('p1')
  })
})

describe('applyProductPrefill', () => {
  const products = [{ product_id: 'p1' }, { product_id: 'p2' }]

  it('预选商品在列表中时写入表单', () => {
    const form = { product_id: '' }
    const applied = applyProductPrefill(form, products, { product_id: 'p2' })
    expect(applied).toBe(true)
    expect(form.product_id).toBe('p2')
  })

  it('预选商品不在列表中时不写入（避免选中不存在的商品）', () => {
    const form = { product_id: '' }
    const applied = applyProductPrefill(form, products, { product_id: 'ghost' })
    expect(applied).toBe(false)
    expect(form.product_id).toBe('')
  })

  it('无 URL 上下文时保持手动选择状态', () => {
    const form = { product_id: 'manual' }
    const applied = applyProductPrefill(form, products, {})
    expect(applied).toBe(false)
    expect(form.product_id).toBe('manual')
  })
})

describe('useSubmitGuard', () => {
  it('执行期间拒绝重入，只执行一次', async () => {
    const { submitting, run } = useSubmitGuard()
    let calls = 0
    let release!: () => void
    const blocker = new Promise<void>(resolve => { release = resolve })

    const first = run(async () => {
      calls++
      await blocker
    })
    expect(submitting.value).toBe(true)

    // 提交中再次调用被忽略
    const second = run(async () => { calls++ })
    await expect(second).resolves.toBeUndefined()

    release()
    await first
    expect(calls).toBe(1)
    expect(submitting.value).toBe(false)
  })

  it('失败时复位 submitting 且异常向上抛（表单数据不被触碰）', async () => {
    const { submitting, run } = useSubmitGuard()
    const form = { product_id: 'p1' }

    await expect(run(async () => {
      expect(submitting.value).toBe(true)
      throw new Error('network')
    })).rejects.toThrow('network')

    expect(submitting.value).toBe(false)
    expect(form.product_id).toBe('p1')
  })

  it('成功后返回动作结果', async () => {
    const { run } = useSubmitGuard()
    await expect(run(async () => ({ task_id: 't1' }))).resolves.toEqual({ task_id: 't1' })
  })
})
