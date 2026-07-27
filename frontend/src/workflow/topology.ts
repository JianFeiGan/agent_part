/**
 * 工作流拓扑定义。
 *
 * 定义商品视觉生成工作流的节点和边关系，
 * 用于 AntV G6 渲染 DAG 流程图。
 */

/** 工作流节点定义 */
export interface WorkflowNode {
  /** 节点 ID，对应 Agent step key */
  id: string
  /** 英文角色名（大写，显示在卡片顶部） */
  role: string
  /** 中文标签 */
  label: string
  /** 节点颜色（用于边框、连线、状态指示） */
  color: string
}

/** 工作流边定义 */
export interface WorkflowEdge {
  /** 源节点 ID */
  source: string
  /** 目标节点 ID */
  target: string
  /** 条件描述（可选，用于条件路由） */
  condition?: string
}

/** 商品视觉生成工作流拓扑 */
export const WORKFLOW_TOPOLOGY = {
  nodes: [
    { id: 'orchestrator', role: 'ORCHESTRATOR', label: '编排调度', color: '#6c5ce7' },
    { id: 'requirement_analyzer', role: 'ANALYZER', label: '需求分析', color: '#00cec9' },
    { id: 'creative_planner', role: 'PLANNER', label: '创意策划', color: '#fdcb6e' },
    { id: 'visual_designer', role: 'DESIGNER', label: '视觉设计', color: '#e17055' },
    { id: 'image_generator', role: 'IMAGE GEN', label: '图片生成', color: '#58a6ff' },
    { id: 'video_generator', role: 'VIDEO GEN', label: '视频生成', color: '#a29bfe' },
    { id: 'quality_reviewer', role: 'REVIEWER', label: '质量审核', color: '#55efc4' },
  ] as WorkflowNode[],
  edges: [
    { source: 'orchestrator', target: 'requirement_analyzer' },
    { source: 'requirement_analyzer', target: 'creative_planner' },
    { source: 'creative_planner', target: 'visual_designer' },
    { source: 'visual_designer', target: 'image_generator', condition: 'image_only | image_and_video' },
    { source: 'visual_designer', target: 'video_generator', condition: 'video_only' },
    { source: 'image_generator', target: 'video_generator', condition: 'image_and_video' },
    { source: 'image_generator', target: 'quality_reviewer', condition: 'image_only' },
    { source: 'video_generator', target: 'quality_reviewer' },
  ] as WorkflowEdge[],
} as const

/** 节点 ID 到节点定义的映射 */
export const NODE_MAP = new Map(
  WORKFLOW_TOPOLOGY.nodes.map(node => [node.id, node])
)

/** 获取节点的上游节点 ID 列表 */
export function getUpstreamNodeIds(nodeId: string): string[] {
  return WORKFLOW_TOPOLOGY.edges
    .filter(edge => edge.target === nodeId)
    .map(edge => edge.source)
}

/** 获取节点的下游节点 ID 列表 */
export function getDownstreamNodeIds(nodeId: string): string[] {
  return WORKFLOW_TOPOLOGY.edges
    .filter(edge => edge.source === nodeId)
    .map(edge => edge.target)
}
