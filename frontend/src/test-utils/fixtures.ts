import { TaskStatus, TaskType } from '@/types/task'
import { ProductCategory } from '@/types/product'
import type { Product } from '@/types/product'
import type { Task, TaskDetail, TaskStatusResponse } from '@/types/task'

/** 构造一条字段完整的 TaskDetail，覆盖需要差异化的字段即可 */
export function makeDetail(overrides: Partial<TaskDetail> = {}): TaskDetail {
  return {
    task_id: 't1',
    product_id: 'p1',
    task_type: TaskType.IMAGE_ONLY,
    status: TaskStatus.RUNNING,
    progress: 0,
    current_step: 'orchestrator',
    completed_steps: [],
    agent_logs: [],
    images: [],
    video: null,
    quality_reports: [],
    error_message: null,
    created_at: '2026-09-17T00:00:00Z',
    updated_at: '2026-09-17T00:00:00Z',
    ...overrides
  }
}

/** 构造轻量状态快照（轮询路径） */
export function makeStatus(overrides: Partial<TaskStatusResponse> = {}): TaskStatusResponse {
  return {
    task_id: 't1',
    status: TaskStatus.RUNNING,
    progress: 0,
    current_step: '',
    created_at: '2026-09-17T00:00:00Z',
    updated_at: '2026-09-17T00:00:00Z',
    ...overrides
  }
}

/** 构造任务列表项 */
export function makeTask(overrides: Partial<Task> = {}): Task {
  return {
    task_id: 't1',
    product_id: 'p1',
    status: TaskStatus.RUNNING,
    progress: 10,
    current_step: 'orchestrator',
    error_message: null,
    created_at: '2026-09-17T00:00:00Z',
    updated_at: '2026-09-17T00:00:00Z',
    ...overrides
  }
}

/** 构造商品 */
export function makeProduct(overrides: Partial<Product> = {}): Product {
  return {
    product_id: 'p1',
    name: '无线降噪耳机',
    brand: 'ACME',
    category: ProductCategory.DIGITAL,
    subcategory: null,
    description: '旗舰级主动降噪',
    short_description: null,
    selling_points: [],
    specifications: [],
    target_audience: [],
    price_range: null,
    existing_images: [],
    existing_videos: [],
    tags: ['数码'],
    ...overrides
  }
}
