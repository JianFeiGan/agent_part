/**
 * API 响应通用类型
 */
export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T
}

/**
 * 分页请求参数
 */
export interface PageParams {
  page: number
  page_size: number
}

/**
 * 分页响应数据
 */
export interface PageResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

/**
 * 通用 ID 参数
 */
export interface IdParams {
  id: number | string
}