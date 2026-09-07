/**
 * 资产管理模块类型定义。
 *
 * 对应后端 /api/v1/assets/* 路由。
 */

/** 资产类型 */
export type AssetType = 'image' | 'video' | 'document'

/** 资产生成渠道 */
export type AssetProvider = 'dashscope' | 'kling' | 'mock' | string

/** 资源项（后端 AssetResponse） */
export interface AssetItem {
  asset_id: number
  product_id: string | null
  task_id: string | null
  asset_type: AssetType
  provider: AssetProvider
  url: string
  mime_type: string | null
  file_size: number | null
  width: number | null
  height: number | null
  duration: number | null
  is_mock: boolean
  status: string
  created_at: string
}

/** 资产列表查询参数（GET /assets） */
export interface AssetQueryParams {
  product_id?: string
  task_id?: string
  asset_type?: AssetType
  limit?: number
}
