/**
 * 仪表盘 API 请求。
 *
 * @author ganjianfei
 * @version 1.0.0
 * 2026-06-12
 */

import request from './index'
import type { DashboardStats } from '@/types/dashboard'

/**
 * 获取仪表盘统计数据。
 *
 * @returns 仪表盘统计数据。
 */
export async function getDashboardStats(): Promise<DashboardStats> {
  const response = await request.get('/dashboard/stats')
  return response.data.data
}
