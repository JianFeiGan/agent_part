<template>
  <div ref="containerRef" class="agent-dag" />
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { Graph } from '@antv/g6'
import { useWorkbenchStore } from '@/stores/workbench'
import { WORKFLOW_TOPOLOGY } from '@/workflow/topology'
import { getAgentNodeStyle, getEdgeStyle } from '@/workflow/node-renderer'
import type { AgentLog } from '@/types/task'

/**
 * Agent DAG 流程图组件。
 * 使用 AntV G6 渲染工作流拓扑，节点状态随 store 变化实时更新。
 */

const store = useWorkbenchStore()
const containerRef = ref<HTMLDivElement>()
let graph: Graph | null = null

/** 初始化 G6 图实例 */
function initGraph() {
  if (!containerRef.value) return

  const container = containerRef.value
  const width = container.offsetWidth
  const height = container.offsetHeight

  // 构建初始节点数据
  const nodes = WORKFLOW_TOPOLOGY.nodes.map(node => {
    const log = store.agentLogMap.get(node.id)
    const isSelected = store.selectedAgentId === node.id
    const style = getAgentNodeStyle(node.id, log, isSelected)
    return {
      id: node.id,
      data: {
        label: node.label,
        ...style,
      },
    }
  })

  // 构建初始边数据
  const edges = WORKFLOW_TOPOLOGY.edges.map(edge => {
    const sourceLog = store.agentLogMap.get(edge.source)
    const style = getEdgeStyle(sourceLog?.status ?? 'pending')
    return {
      source: edge.source,
      target: edge.target,
      data: { ...style },
    }
  })

  graph = new Graph({
    container,
    width,
    height,
    autoFit: 'view',
    padding: [30, 30, 30, 30],
    layout: {
      type: 'dagre',
      rankdir: 'TB',
      nodesep: 50,
      ranksep: 70,
    },
    node: {
      style: (model: any) => {
        const nodeId = model.id as string
        const log: AgentLog | undefined = store.agentLogMap.get(nodeId)
        const isSelected = store.selectedAgentId === nodeId
        return getAgentNodeStyle(nodeId, log, isSelected)
      },
    },
    edge: {
      style: (model: any) => {
        const sourceId = model.source as string
        const sourceLog = store.agentLogMap.get(sourceId)
        return getEdgeStyle(sourceLog?.status ?? 'pending')
      },
    },
    behaviors: ['drag-canvas', 'zoom-canvas'],
  })

  graph.setData({ nodes, edges })
  graph.render()

  // 节点点击事件
  graph.on('node:click', (event: any) => {
    const nodeId = event.target?.id
    if (nodeId) {
      store.selectAgent(nodeId)
    }
  })
}

/** 响应 store 变化更新图 */
function updateGraph() {
  if (!graph) return

  const nodes = WORKFLOW_TOPOLOGY.nodes.map(node => {
    const log = store.agentLogMap.get(node.id)
    const isSelected = store.selectedAgentId === node.id
    const style = getAgentNodeStyle(node.id, log, isSelected)
    return {
      id: node.id,
      data: {
        label: node.label,
        ...style,
      },
    }
  })

  const edges = WORKFLOW_TOPOLOGY.edges.map(edge => {
    const sourceLog = store.agentLogMap.get(edge.source)
    const style = getEdgeStyle(sourceLog?.status ?? 'pending')
    return {
      source: edge.source,
      target: edge.target,
      data: { ...style },
    }
  })

  graph.setData({ nodes, edges })
  graph.render()
}

/** 响应窗口大小变化 */
function handleResize() {
  if (!graph || !containerRef.value) return
  graph.resize(containerRef.value.offsetWidth, containerRef.value.offsetHeight)
}

onMounted(() => {
  initGraph()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (graph) {
    graph.destroy()
    graph = null
  }
})

// 监听 store 变化更新图
watch(
  () => [store.agentLogMap, store.selectedAgentId],
  updateGraph,
  { deep: true },
)
</script>

<style scoped>
.agent-dag {
  width: 100%;
  height: 100%;
  min-height: 400px;
  background: #0f0f23;
  border-radius: 8px;
  overflow: hidden;
}
</style>
