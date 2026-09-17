/**
 * 任务创建页商品预选逻辑。
 *
 * 从 URL query 解析预选商品并在商品加载完成后应用，
 * 仅当预选商品存在于已加载列表时才写入表单，避免选中不存在的商品。
 */
import type { LocationQuery } from 'vue-router'
import type { Product } from '@/types/product'
import type { TaskCreateRequest } from '@/types/task'

/** 从 URL query 解析预选商品 ID；缺失或为空返回 null */
export function resolvePreselectedProductId(query: LocationQuery): string | null {
  const raw = query.product_id
  const id = Array.isArray(raw) ? raw[0] : raw
  return id ? String(id) : null
}

/**
 * 应用 URL 商品预选。
 *
 * @returns 是否成功预选（商品不存在于列表时返回 false）
 */
export function applyProductPrefill(
  form: Pick<TaskCreateRequest, 'product_id'>,
  products: Pick<Product, 'product_id'>[],
  query: LocationQuery
): boolean {
  const id = resolvePreselectedProductId(query)
  if (!id) return false
  if (!products.some(p => p.product_id === id)) return false
  form.product_id = id
  return true
}
