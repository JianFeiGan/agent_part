/**
 * 资产管理 API 封装。
 * 对应后端 /api/v1/assets/* 路由。
 *
 * 返回值为 `ApiResponse.data`，错误由全局拦截器统一处理并 reject。
 */
import request from './index'
import type { AssetItem, AssetQueryParams } from '@/types/assets'

const BASE_URL = '/assets'

/**
 * 获取资源列表。
 */
export async function listAssets(params?: AssetQueryParams): Promise<AssetItem[]> {
  const res = await request.get(BASE_URL, { params })
  return res.data.data
}

/**
 * 获取单个资源。
 */
export async function getAsset(assetId: number): Promise<AssetItem> {
  const res = await request.get(`${BASE_URL}/${assetId}`)
  return res.data.data
}

/**
 * 删除资源。
 */
export async function deleteAsset(assetId: number): Promise<void> {
  const res = await request.delete(`${BASE_URL}/${assetId}`)
  return res.data.data
}
