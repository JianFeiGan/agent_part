/**
 * 仪表盘类型定义。
 *
 * @author ganjianfei
 * @version 1.0.0
 * 2026-06-12
 */

/** 最近任务条目 */
export interface RecentTaskItem {
  task_id: string
  product_id: string | null
  task_type: string | null
  status: string
  progress: number
  current_step: string
  created_at: string | null
  updated_at: string | null
}

/** 仪表盘统计数据 */
export interface DashboardStats {
  total_products: number
  total_tasks: number
  running_tasks: number
  failed_tasks: number
  recent_tasks: RecentTaskItem[]
}
