import type { AxiosResponse } from 'axios'
import request from './index'
import type { ApiResponse, PageResponse } from '@/types/api'
import type {
  Task,
  TaskDetail,
  TaskCreateRequest,
  TaskQueryParams,
  TaskStatusResponse
} from '@/types/task'

/**
 * 任务 API
 * @description 任务管理相关接口
 */

const BASE_URL = '/tasks'

/**
 * 获取任务列表
 */
export function getTasks(params: TaskQueryParams): Promise<AxiosResponse<ApiResponse<PageResponse<Task>>>> {
  return request.get(BASE_URL, { params })
}

/**
 * 获取任务详情
 */
export function getTaskById(taskId: string): Promise<AxiosResponse<ApiResponse<TaskDetail>>> {
  return request.get(`${BASE_URL}/${taskId}`)
}

/**
 * 获取任务状态
 */
export function getTaskStatus(taskId: string): Promise<AxiosResponse<ApiResponse<TaskStatusResponse>>> {
  return request.get(`${BASE_URL}/${taskId}/status`)
}

/**
 * 创建任务
 */
export function createTask(data: TaskCreateRequest): Promise<AxiosResponse<ApiResponse<{ task_id: string }>>> {
  return request.post(BASE_URL, data)
}

/**
 * 取消任务
 */
export function cancelTask(taskId: string): Promise<AxiosResponse<ApiResponse<{ task_id: string; cancelled: boolean }>>> {
  return request.post(`${BASE_URL}/${taskId}/cancel`)
}

/**
 * 删除任务
 */
export function deleteTask(taskId: string): Promise<AxiosResponse<ApiResponse<void>>> {
  return request.delete(`${BASE_URL}/${taskId}`)
}