import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/api/index', () => {
  return {
    default: {
      get: vi.fn(),
      post: vi.fn(),
      put: vi.fn(),
      delete: vi.fn()
    }
  }
})

import request from '@/api/index'
import { getProducts, getProductById } from '@/api/products'
import { getTasks, getTaskById, createTask } from '@/api/tasks'
import { listModelProviders } from '@/api/providers'

function ok<T>(data: T) {
  return { data: { code: 200, message: 'ok', data } }
}

describe('main-path API unwrap', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('getProducts 返回业务分页数据', async () => {
    const page = { items: [{ product_id: 'p1', name: '手表' }], total: 1, page: 1, page_size: 10, pages: 1 }
    vi.mocked(request.get).mockResolvedValueOnce(ok(page))

    const result = await getProducts({ page: 1, page_size: 10 })
    expect(result).toEqual(page)
    expect(request.get).toHaveBeenCalledWith('/products', { params: { page: 1, page_size: 10 } })
  })

  it('getTaskById 返回任务详情业务数据', async () => {
    const detail = { task_id: 't1', status: 'running' }
    vi.mocked(request.get).mockResolvedValueOnce(ok(detail))

    const result = await getTaskById('t1')
    expect(result).toEqual(detail)
  })

  it('createTask 返回 task_id', async () => {
    vi.mocked(request.post).mockResolvedValueOnce(ok({ task_id: 't1' }))

    const result = await createTask({ product_id: 'p1', task_type: 'image_only' as never })
    expect(result).toEqual({ task_id: 't1' })
  })

  it('getTasks / getProductById 同样解包 data', async () => {
    vi.mocked(request.get)
      .mockResolvedValueOnce(ok({ items: [], total: 0, page: 1, page_size: 10, pages: 0 }))
      .mockResolvedValueOnce(ok({ product_id: 'p1' }))

    expect(await getTasks({ page: 1 })).toEqual({ items: [], total: 0, page: 1, page_size: 10, pages: 0 })
    expect(await getProductById('p1')).toEqual({ product_id: 'p1' })
  })

  it('listModelProviders 返回厂商数组业务数据', async () => {
    const providers = [{ id: 1, name: 'dashscope', provider_type: 'llm' }]
    vi.mocked(request.get).mockResolvedValueOnce(ok(providers))

    const result = await listModelProviders('llm')
    expect(result).toEqual(providers)
    expect(request.get).toHaveBeenCalledWith('/model-providers', { params: { provider_type: 'llm' } })
  })
})
