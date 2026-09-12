import { describe, it, expect } from 'vitest'
import { createEmptyAgentLog, AgentLogStatus } from '@/types/task'

describe('createEmptyAgentLog', () => {
  it('补齐 AgentLog 全部必填字段，避免合成日志导致类型失败', () => {
    const log = createEmptyAgentLog({ agent_name: '需求分析', step: 'requirement_analysis' })

    expect(log.agent_name).toBe('需求分析')
    expect(log.step).toBe('requirement_analysis')
    expect(log.status).toBe(AgentLogStatus.PENDING)
    expect(log.input_data).toBeNull()
    expect(log.output_data).toBeNull()
    expect(log.prompt_template).toBeNull()
    expect(log.prompt_variables).toBeNull()
    expect(log.input_tokens).toBe(0)
    expect(log.output_tokens).toBe(0)
    expect(log.total_tokens).toBe(0)
    expect(log.cost_cny).toBe(0)
    expect(log.latency_ms).toBeNull()
    expect(log.model_name).toBeNull()
    expect(log.provider).toBeNull()
    expect(log.child_calls).toEqual([])
    expect(log.start_time).toBeNull()
    expect(log.end_time).toBeNull()
    expect(log.message).toBeNull()
    expect(log.output_summary).toBeNull()
  })

  it('partial 覆盖默认值', () => {
    const log = createEmptyAgentLog({
      agent_name: '创意策划',
      step: 'creative_planning',
      status: 'running',
      input_tokens: 120,
      child_calls: [{ call_type: 'llm', name: 'qwen', input: null, output: null, latency_ms: 10 }]
    })

    expect(log.status).toBe('running')
    expect(log.input_tokens).toBe(120)
    expect(log.child_calls).toHaveLength(1)
  })
})
