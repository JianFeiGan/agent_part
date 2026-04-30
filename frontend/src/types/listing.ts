/**
 * Description: 刊登工具相关的 TypeScript 类型定义。
 * @author ganjianfei
 * @version 1.0.0
 * 2026-04-25
 */

export type Platform = 'amazon' | 'ebay' | 'shopify'

export type ComplianceStatus = 'pass' | 'fail' | 'warning'

export type TaskStatus =
  | 'pending'
  | 'generating'
  | 'reviewing'
  | 'pushing'
  | 'completed'
  | 'failed'
  | 'published'
  | 'partial'

export interface ProductImportRequest {
  sku: string
  title: string
  description?: string
  category?: string
  brand?: string
  price?: number
  weight?: number
  dimensions?: Record<string, unknown>
  source_images?: Record<string, unknown>[]
  attributes?: Record<string, unknown>
}

export interface ProductResponse {
  sku: string
  title: string
  description: string | null
  category: string | null
  brand: string | null
  source_images: Record<string, unknown>[]
}

export interface CreateListingTaskRequest {
  product_sku: string
  target_platforms: Platform[]
}

export interface ListingTaskResponse {
  task_id: number
  product_sku: string
  target_platforms: string[]
  status: TaskStatus
}

export interface ComplianceIssueResponse {
  severity: ComplianceStatus
  rule: string
  field: string
  message: string
  suggestion: string | null
}

export interface ComplianceReportResponse {
  platform: string
  overall: ComplianceStatus
  image_issues: ComplianceIssueResponse[]
  text_issues: ComplianceIssueResponse[]
  forbidden_words: string[]
}

export interface PushListingRequest {
  platforms?: Platform[]
}

export interface PushResultResponse {
  platform: string
  success: boolean
  listing_id: string | null
  url: string | null
  error: string | null
}

export interface PushResponse {
  task_id: number
  results: PushResultResponse[]
  status: string
}

export interface AdapterConfigCreate {
  platform: Platform
  shop_id?: string
  credentials: Record<string, unknown>
  is_active?: boolean
}

export interface AdapterConfigUpdate {
  credentials?: Record<string, unknown>
  is_active?: boolean
}

export interface AdapterConfigResponse {
  id: number
  platform: string
  shop_id: string
  credentials_masked: Record<string, string>
  is_active: boolean
  created_at: string | null
  updated_at: string | null
}
