/**
 * 前端通用格式化与展示映射。
 *
 * 集中存放跨视图复用的纯函数，避免同一份映射在多个视图里各写一遍。
 */
import { TaskStatusLabels, TaskStatus } from '@/types/task'

/** Element Plus 标签语义类型 */
export type TagType = 'primary' | 'success' | 'info' | 'warning' | 'danger'

/**
 * 格式化 ISO 时间字符串为 `YYYY-MM-DD HH:mm:ss`。
 *
 * @param time - ISO 时间字符串，可能为空
 * @returns 格式化后的时间；空值返回 `-`
 */
export function formatTime(time: string | null | undefined): string {
  if (!time) return '-'
  return time.replace('T', ' ').substring(0, 19)
}

/**
 * 生成任务状态 → Element Plus 标签类型的映射。
 */
const TaskStatusTagTypes: Record<TaskStatus, TagType> = {
  [TaskStatus.PENDING]: 'info',
  [TaskStatus.RUNNING]: 'warning',
  [TaskStatus.COMPLETED]: 'success',
  [TaskStatus.FAILED]: 'danger',
  [TaskStatus.CANCELLED]: 'info'
}

/**
 * 获取生成任务状态的中文标签。
 *
 * @param status - 任务状态，可能为空或后端新增的未知值
 * @returns 中文标签；未知状态原样返回，空值返回 `-`
 */
export function getTaskStatusLabel(status: string | null | undefined): string {
  if (!status) return '-'
  return TaskStatusLabels[status as TaskStatus] ?? status
}

/**
 * 获取生成任务状态对应的 Element Plus 标签类型。
 *
 * @param status - 任务状态
 * @returns 标签类型；未知状态回退为 `info`
 */
export function getTaskStatusTagType(status: string | null | undefined): TagType {
  if (!status) return 'info'
  return TaskStatusTagTypes[status as TaskStatus] ?? 'info'
}
