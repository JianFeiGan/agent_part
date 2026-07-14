// frontend/src/workflow/node-renderer.ts

import type { AgentLog } from '@/types/task'
import { NODE_MAP } from '@/workflow/topology'
import type { WorkflowNode } from '@/workflow/topology'

/**
 * G6 自定义节点渲染函数。
 */

/** 状态对应的视觉配置 */
const STATUS_STYLE: Record<string, {
  borderColor: string
  bgColor: string
  badgeBg: string
  badgeColor: string
  badgeText: string
  opacity: number
  shadow: string
}> = {
  completed: {
    borderColor: '#238636',
    bgColor: '#1a1a2e',
    badgeBg: '#238636',
    badgeColor: '#ffffff',
    badgeText: '✓',
    opacity: 1,
    shadow: 'none',
  },
  running: {
    borderColor: '#58a6ff',
    bgColor: '#1a1a2e',
    badgeBg: '#1f6feb',
    badgeColor: '#ffffff',
    badgeText: '●',
    opacity: 1,
    shadow: '0 0 12px rgba(88,166,255,0.4)',
  },
  failed: {
    borderColor: '#f85149',
    bgColor: '#1a1a2e',
    badgeBg: '#f85149',
    badgeColor: '#ffffff',
    badgeText: '✗',
    opacity: 1,
    shadow: '0 0 8px rgba(248,81,73,0.3)',
  },
  pending: {
    borderColor: '#30363d',
    bgColor: '#1a1a2e',
    badgeBg: '#30363d',
    badgeColor: '#8b949e',
    badgeText: '○',
    opacity: 0.5,
    shadow: 'none',
  },
}

/** 格式化耗时 */
function formatLatency(ms: number | null): string {
  if (ms === null) return ''
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

/** 格式化 token 数 */
function formatTokens(tokens: number): string {
  if (tokens === 0) return ''
  if (tokens >= 1000) return `${(tokens / 1000).toFixed(1)}k`
  return `${tokens} tok`
}

/** 格式化费用 */
function formatCost(cost: number): string {
  if (cost === 0) return ''
  return `¥${cost.toFixed(3)}`
}

/**
 * 生成 G6 节点的 style 配置。
 */
export function getAgentNodeStyle(
  nodeId: string,
  log: AgentLog | null | undefined,
  isSelected: boolean,
): Record<string, unknown> {
  const nodeDef: WorkflowNode | undefined = NODE_MAP.get(nodeId)
  const status = log?.status ?? 'pending'
  const style = STATUS_STYLE[status] ?? STATUS_STYLE.pending

  // 构建底部指标行
  const metrics: string[] = []
  if (log) {
    const latency = formatLatency(log.latency_ms)
    const tokens = formatTokens(log.total_tokens)
    const cost = formatCost(log.cost_cny)
    if (latency) metrics.push(latency)
    if (tokens) metrics.push(tokens)
    if (cost) metrics.push(cost)
  }
  const metricsText = metrics.length ? metrics.join(' · ') : (status === 'pending' ? '等待中' : '')

  return {
    size: [220, 72],
    style: {
      fill: style.bgColor,
      stroke: isSelected ? '#ffffff' : style.borderColor,
      lineWidth: isSelected ? 3 : 2,
      radius: 12,
      shadowColor: style.shadow !== 'none' ? style.borderColor : 'transparent',
      shadowBlur: style.shadow !== 'none' ? 12 : 0,
      opacity: style.opacity,
    },
    labelText: `${nodeDef?.role ?? nodeId}\n${nodeDef?.label ?? nodeId}`,
    labelPlacement: 'center',
    labelOffsetY: -8,
    labelLineHeight: 18,
    labelStyle: {
      fontSize: 10,
      fill: nodeDef?.color ?? '#c9d1d9',
      textAlign: 'left',
    },
    badges: [
      {
        position: 'topRight',
        type: 'text',
        text: style.badgeText,
        size: [20, 20],
        style: {
          fill: style.badgeBg,
          stroke: style.badgeBg,
          radius: 10,
          fontSize: 10,
          fillText: style.badgeColor,
        },
      },
    ],
    bottomLabelText: metricsText,
    bottomLabelPlacement: 'bottom',
    bottomLabelStyle: {
      fontSize: 10,
      fill: '#8b949e',
    },
  }
}

/**
 * 生成 G6 边的 style 配置。
 */
export function getEdgeStyle(sourceStatus: string): Record<string, unknown> {
  const isCompleted = sourceStatus === 'completed'
  return {
    stroke: isCompleted ? '#636e72' : '#30363d',
    lineWidth: isCompleted ? 2 : 1,
    lineDash: isCompleted ? [] : [4, 4],
    endArrow: {
      type: 'triangle',
      size: 6,
      fill: isCompleted ? '#636e72' : '#30363d',
    },
  }
}
