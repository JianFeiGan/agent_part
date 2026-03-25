/**
 * 商品类目枚举
 */
export enum ProductCategory {
  DIGITAL = 'digital',
  CLOTHING = 'clothing',
  FOOD = 'food',
  HOME = 'home',
  BEAUTY = 'beauty',
  SPORTS = 'sports',
  OTHER = 'other'
}

/**
 * 商品类目标签映射
 */
export const ProductCategoryLabels: Record<ProductCategory, string> = {
  [ProductCategory.DIGITAL]: '数码电子',
  [ProductCategory.CLOTHING]: '服装鞋包',
  [ProductCategory.FOOD]: '食品饮料',
  [ProductCategory.HOME]: '家居家装',
  [ProductCategory.BEAUTY]: '美妆个护',
  [ProductCategory.SPORTS]: '运动户外',
  [ProductCategory.OTHER]: '其他'
}

/**
 * 卖点类型
 */
export interface SellingPoint {
  title: string
  description: string
  point_type?: string
  priority?: number
  keywords?: string[]
}

/**
 * 商品规格
 */
export interface ProductSpec {
  name: string
  value: string
}

/**
 * 商品信息
 */
export interface Product {
  product_id: string
  name: string
  brand: string | null
  category: ProductCategory
  subcategory: string | null
  description: string
  short_description: string | null
  selling_points: SellingPoint[]
  specifications: ProductSpec[]
  target_audience: string[]
  price_range: [number, number] | null
  existing_images: string[]
  existing_videos: string[]
  tags: string[]
}

/**
 * 商品创建请求
 */
export interface ProductCreateRequest {
  name: string
  brand?: string
  category: ProductCategory
  subcategory?: string
  description: string
  short_description?: string
  selling_points?: SellingPoint[]
  specifications?: ProductSpec[]
  target_audience?: string[]
  price_range?: [number, number]
  existing_images?: string[]
  existing_videos?: string[]
  tags?: string[]
}

/**
 * 商品更新请求
 */
export interface ProductUpdateRequest {
  name?: string
  brand?: string
  category?: ProductCategory
  subcategory?: string
  description?: string
  short_description?: string
  selling_points?: SellingPoint[]
  specifications?: ProductSpec[]
  target_audience?: string[]
  price_range?: [number, number]
  existing_images?: string[]
  existing_videos?: string[]
  tags?: string[]
}

/**
 * 商品查询参数
 */
export interface ProductQueryParams {
  name?: string
  brand?: string
  category?: ProductCategory
  tag?: string
  page?: number
  page_size?: number
}