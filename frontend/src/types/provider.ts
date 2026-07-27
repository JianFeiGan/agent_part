/**
 * Description: 模型厂商管理相关的 TypeScript 类型定义。
 * @author ganjianfei
 * @version 1.0.0
 * 2026-07-22
 */

/** 厂商类型 */
export type ProviderType = 'llm' | 'image' | 'video'

/** 协议类型 */
export type ProtocolType = 'openai_compatible' | 'custom_rest'

/** 创建模型厂商请求 */
export interface ModelProviderCreate {
  name: string
  display_name: string
  provider_type: ProviderType
  base_url: string
  api_key?: string
  extra_credentials?: Record<string, unknown>
  default_model: string
  supported_models?: string[]
  model_config_extra?: Record<string, unknown>
  protocol?: ProtocolType
  is_active?: boolean
  is_default?: boolean
}

/** 更新模型厂商请求 */
export interface ModelProviderUpdate {
  display_name?: string
  base_url?: string
  api_key?: string
  extra_credentials?: Record<string, unknown>
  default_model?: string
  supported_models?: string[]
  model_config_extra?: Record<string, unknown>
  protocol?: ProtocolType
  is_active?: boolean
}

/** 模型厂商响应 */
export interface ModelProviderResponse {
  id: number
  name: string
  display_name: string
  provider_type: ProviderType
  base_url: string
  api_key_masked: string
  default_model: string
  supported_models: string[]
  protocol: ProtocolType
  is_active: boolean
  is_default: boolean
  created_at: string | null
  updated_at: string | null
}

/** 测试连接响应 */
export interface ModelProviderTestResponse {
  success: boolean
  message: string
  latency_ms: number | null
}
