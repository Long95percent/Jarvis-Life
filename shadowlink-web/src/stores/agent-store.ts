/**
 * Agent execution store — tracks agent steps, plan, tool calls, and streaming state.
 */

import { create } from 'zustand'
import { immer } from 'zustand/middleware/immer'
import type { AgentStep, PlanStep, AgentStrategy } from '@/types'

interface AgentState {
  /** Current execution session ID */
  sessionId: string | null
  /** Active agent strategy */
  strategy: AgentStrategy | null
  /** Accumulated steps for the current execution */
  steps: AgentStep[]
  /** Plan steps (for plan-and-execute strategy) */
  plan: PlanStep[]
  /** Whether the agent is currently running */
  isRunning: boolean
  /** Aggregated token count */
  totalTokens: number
  /** Aggregated latency */
  totalLatencyMs: number
  /** Current thought / streaming thought text */
  currentThought: string

  // Actions
  startExecution: (sessionId: string, strategy: AgentStrategy) => void
  addStep: (step: AgentStep) => void
  setPlan: (plan: PlanStep[]) => void
  updatePlanStep: (index: number, status: PlanStep['status']) => void
  setCurrentThought: (thought: string) => void
  finishExecution: () => void
  resetExecution: () => void
}

export const useAgentStore = create<AgentState>()(
  immer((set) => ({
    sessionId: null,
    strategy: null,
    steps: [],
    plan: [],
    isRunning: false,
    totalTokens: 0,
    totalLatencyMs: 0,
    currentThought: '',

    startExecution: (sessionId, strategy) =>
      set((s) => {
        s.sessionId = sessionId
        s.strategy = strategy
        s.steps = []
        s.plan = []
        s.isRunning = true
        s.totalTokens = 0
        s.totalLatencyMs = 0
        s.currentThought = ''
      }),

    addStep: (step) =>
      set((s) => {
        s.steps.push(step)
        s.totalTokens += step.tokenCount
        s.totalLatencyMs += step.latencyMs
      }),

    setPlan: (plan) =>
      set((s) => { s.plan = plan }),

    updatePlanStep: (index, status) =>
      set((s) => {
        const step = s.plan.find((p) => p.index === index)
        if (step) step.status = status
      }),

    setCurrentThought: (thought) =>
      set((s) => { s.currentThought = thought }),

    finishExecution: () =>
      set((s) => { s.isRunning = false }),

    resetExecution: () =>
      set((s) => {
        s.sessionId = null
        s.strategy = null
        s.steps = []
        s.plan = []
        s.isRunning = false
        s.totalTokens = 0
        s.totalLatencyMs = 0
        s.currentThought = ''
      }),
  })),
)
