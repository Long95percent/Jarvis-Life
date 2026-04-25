/** Agent execution types */

export type AgentStrategy = 'direct' | 'react' | 'plan_execute' | 'supervisor' | 'hierarchical' | 'swarm' | 'hermes'

export type StreamEventType =
  | 'token'
  | 'thought'
  | 'action'
  | 'observation'
  | 'plan'
  | 'step_start'
  | 'step_result'
  | 'tool_call'
  | 'tool_result'
  | 'rag_context'
  | 'error'
  | 'done'
  | 'heartbeat'

export interface StreamEvent {
  event: StreamEventType
  data: Record<string, unknown>
  sessionId: string
  stepId?: string
  timestamp: number
}

export interface AgentStep {
  stepType: string
  content: string
  toolName?: string
  toolInput?: Record<string, unknown>
  toolOutput?: string
  tokenCount: number
  latencyMs: number
}

export interface PlanStep {
  index: number
  description: string
  tool?: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped'
}

export interface AgentExecution {
  sessionId: string
  strategy: AgentStrategy
  steps: AgentStep[]
  plan?: PlanStep[]
  isRunning: boolean
  totalTokens: number
  totalLatencyMs: number
}

export interface ToolInfo {
  name: string
  description: string
  category: string
  isAsync: boolean
  requiresConfirmation: boolean
}

export interface LLMConfig {
  id: string
  name: string
  baseUrl: string
  model: string
  apiKey: string
  temperature: number
  maxTokens: number
}
