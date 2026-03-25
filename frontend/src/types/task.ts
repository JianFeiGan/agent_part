/**
 * Agent 执行日志状态枚举
 */
export enum AgentLogStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  COMPLETED = 'completed',
  FAILED = 'failed'
}

/**
 * Agent 执行日志状态标签映射
 */
export const AgentLogStatusLabels: Record<AgentLogStatus, string> = {
  [AgentLogStatus.PENDING]: '待执行',
  [AgentLogStatus.RUNNING]: '执行中',
  [AgentLogStatus.COMPLETED]: '已完成',
  [AgentLogStatus.FAILED]: '失败'
}

/**
 * Agent 执行日志
 */
export interface AgentLog {
  agent_name: string
  step: string
  start_time: string | null
  end_time: string | null
  status: AgentLogStatus | string
  message: string | null
  output_summary: string | null
}

/**
 * 任务类型枚举
 */
export enum TaskType {
  IMAGE_ONLY = 'image_only',
  VIDEO_ONLY = 'video_only',
  IMAGE_AND_VIDEO = 'image_and_video'
}

/**
 * 任务类型标签映射
 */
export const TaskTypeLabels: Record<TaskType, string> = {
  [TaskType.IMAGE_ONLY]: '图片生成',
  [TaskType.VIDEO_ONLY]: '视频生成',
  [TaskType.IMAGE_AND_VIDEO]: '图片+视频'
}

/**
 * 任务状态枚举
 */
export enum TaskStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  COMPLETED = 'completed',
  FAILED = 'failed'
}

/**
 * 任务状态标签映射
 */
export const TaskStatusLabels: Record<TaskStatus, string> = {
  [TaskStatus.PENDING]: '待处理',
  [TaskStatus.RUNNING]: '运行中',
  [TaskStatus.COMPLETED]: '已完成',
  [TaskStatus.FAILED]: '失败'
}

/**
 * 任务信息（列表项）
 */
export interface Task {
  task_id: string
  product_id: string
  status: TaskStatus
  progress: number
  current_step: string
  error_message?: string | null
  created_at: string
  updated_at: string
  request?: TaskRequest
}

/**
 * 任务详情
 */
export interface TaskDetail {
  task_id: string
  product_id: string
  task_type: TaskType
  status: TaskStatus
  progress: number
  current_step: string
  completed_steps: string[]
  agent_logs: AgentLog[]
  images: ImageResult[]
  video: VideoResult | null
  quality_reports: QualityReport[]
  error_message: string | null
  created_at: string
  updated_at: string
  state?: Record<string, unknown>
}

/**
 * 图片结果
 */
export interface ImageResult {
  image_id: string
  image_type: string
  url: string
  status: string
}

/**
 * 视频结果
 */
export interface VideoResult {
  video_id: string
  url: string
  duration: number
  status: string
}

/**
 * 质量报告
 */
export interface QualityReport {
  report_id: string
  overall_score: number
  issues: string[]
  recommendations: string[]
}

/**
 * 任务请求配置
 */
export interface TaskRequest {
  task_id: string
  task_type: TaskType
  image_types: string[]
  image_count_per_type: number
  video_duration: number
  video_style: string
  style_preference: string | null
  color_preference: string | null
  quality_level: string
}

/**
 * 任务创建请求
 */
export interface TaskCreateRequest {
  product_id: string
  task_type: TaskType
  image_types?: string[]
  image_count_per_type?: number
  video_duration?: number
  video_style?: string
  style_preference?: string
  color_preference?: string
  quality_level?: string
}

/**
 * 任务状态响应
 */
export interface TaskStatusResponse {
  task_id: string
  status: TaskStatus
  progress: number
  current_step: string
  created_at: string
  updated_at: string
}

/**
 * 任务查询参数
 */
export interface TaskQueryParams {
  product_id?: string
  task_type?: TaskType
  status?: TaskStatus
  page?: number
  page_size?: number
}