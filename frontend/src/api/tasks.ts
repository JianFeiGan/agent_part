/**
 * 生成任务 API。
 *
 * 返回值为 `ApiResponse.data`，错误由全局拦截器统一处理并 reject。
 * 注意：本模块只服务「生成任务」，不要与刊登任务 `api/listing.ts` 混用。
 */
import request from './index'
import type { PageResponse } from '@/types/api'
import type {
  Task,
  TaskDetail,
  TaskCreateRequest,
  TaskQueryParams,
  TaskStatusResponse
} from '@/types/task'

const BASE_URL = '/tasks'

/** 获取任务列表 */
export async function getTasks(params: TaskQueryParams): Promise<PageResponse<Task>> {
  const res = await request.get(BASE_URL, { params })
  return res.data.data
}

/** 获取任务详情 */
export async function getTaskById(taskId: string): Promise<TaskDetail> {
  const res = await request.get(`${BASE_URL}/${taskId}`)
  return res.data.data
}

/** 获取任务轻量状态（轮询用） */
export async function getTaskStatus(taskId: string): Promise<TaskStatusResponse> {
  const res = await request.get(`${BASE_URL}/${taskId}/status`)
  return res.data.data
}

/** 创建任务 */
export async function createTask(
  data: TaskCreateRequest
): Promise<{ task_id: string }> {
  const res = await request.post(BASE_URL, data)
  return res.data.data
}

/** 取消任务 */
export async function cancelTask(
  taskId: string
): Promise<{ task_id: string; cancelled: boolean }> {
  const res = await request.post(`${BASE_URL}/${taskId}/cancel`)
  return res.data.data
}

/** 删除任务 */
export async function deleteTask(taskId: string): Promise<void> {
  const res = await request.delete(`${BASE_URL}/${taskId}`)
  return res.data.data
}
