import type { AxiosResponse } from 'axios'
import request from './index'
import type { ApiResponse, PageResponse } from '@/types/api'
import type {
  Product,
  ProductCreateRequest,
  ProductUpdateRequest,
  ProductQueryParams
} from '@/types/product'

/**
 * 商品 API
 * @description 商品管理相关接口
 */

const BASE_URL = '/products'

/**
 * 获取商品列表
 */
export function getProducts(params: ProductQueryParams): Promise<AxiosResponse<ApiResponse<PageResponse<Product>>>> {
  return request.get(BASE_URL, { params })
}

/**
 * 获取商品详情
 */
export function getProductById(productId: string): Promise<AxiosResponse<ApiResponse<Product>>> {
  return request.get(`${BASE_URL}/${productId}`)
}

/**
 * 创建商品
 */
export function createProduct(data: ProductCreateRequest): Promise<AxiosResponse<ApiResponse<Product>>> {
  return request.post(BASE_URL, data)
}

/**
 * 更新商品
 */
export function updateProduct(productId: string, data: ProductUpdateRequest): Promise<AxiosResponse<ApiResponse<Product>>> {
  return request.put(`${BASE_URL}/${productId}`, data)
}

/**
 * 删除商品
 */
export function deleteProduct(productId: string): Promise<AxiosResponse<ApiResponse<void>>> {
  return request.delete(`${BASE_URL}/${productId}`)
}