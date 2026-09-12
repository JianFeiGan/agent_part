/**
 * 商品 API。
 *
 * 返回值为 `ApiResponse.data`，错误由全局拦截器统一处理并 reject。
 */
import request from './index'
import type { PageResponse } from '@/types/api'
import type {
  Product,
  ProductCreateRequest,
  ProductUpdateRequest,
  ProductQueryParams
} from '@/types/product'

const BASE_URL = '/products'

/** 获取商品列表 */
export async function getProducts(
  params: ProductQueryParams
): Promise<PageResponse<Product>> {
  const res = await request.get(BASE_URL, { params })
  return res.data.data
}

/** 获取商品详情 */
export async function getProductById(productId: string): Promise<Product> {
  const res = await request.get(`${BASE_URL}/${productId}`)
  return res.data.data
}

/** 创建商品 */
export async function createProduct(data: ProductCreateRequest): Promise<Product> {
  const res = await request.post(BASE_URL, data)
  return res.data.data
}

/** 更新商品 */
export async function updateProduct(
  productId: string,
  data: ProductUpdateRequest
): Promise<Product> {
  const res = await request.put(`${BASE_URL}/${productId}`, data)
  return res.data.data
}

/** 删除商品 */
export async function deleteProduct(productId: string): Promise<void> {
  const res = await request.delete(`${BASE_URL}/${productId}`)
  return res.data.data
}
