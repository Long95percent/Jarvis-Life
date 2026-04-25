/**
 * AgentPanel — right-side panel showing agent execution details:
 * thought process, tool calls, and plan progress.
 */

import { useAgentStore } from '@/stores'
import { ThoughtProcess } from './ThoughtProcess'
import { ToolCallCard } from './ToolCallCard'
import { PlanProgress } from './PlanProgress'

export function AgentPanel() {
  const steps = useAgentStore((s) => s.steps)
  const strategy = useAgentStore((s) => s.strategy)
  const isRunning = useAgentStore((s) => s.isRunning)
  const totalTokens = useAgentStore((s) => s.totalTokens)
  const totalLatencyMs = useAgentStore((s) => s.totalLatencyMs)

  const toolSteps = steps.filter((s) => s.stepType === 'tool_call')

  return (
    <div className="flex flex-col h-full border-l border-surface-tertiary bg-surface">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-surface-tertiary">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-medium text-foreground">Agent</h2>
          {strategy && (
            <span className="px-1.5 py-0.5 text-[10px] rounded bg-surface-secondary text-muted uppercase">
              {strategy}
            </span>
          )}
        </div>
        {isRunning && (
          <span className="flex items-center gap-1.5 text-xs text-primary-400">
            <span className="w-1.5 h-1.5 rounded-full bg-primary-400 animate-pulse-subtle" />
            Running
          </span>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {steps.length === 0 && !isRunning ? (
          <p className="text-sm text-muted text-center py-8">
            Agent activity will appear here during execution.
          </p>
        ) : (
          <>
            <PlanProgress />
            <ThoughtProcess />

            {/* Tool calls */}
            {toolSteps.length > 0 && (
              <div className="space-y-2">
                <h3 className="text-xs font-medium text-muted uppercase tracking-wider">Tool Calls</h3>
                <div className="space-y-1.5">
                  {toolSteps.map((step, i) => (
                    <ToolCallCard key={i} step={step} />
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Footer stats */}
      {totalTokens > 0 && (
        <div className="px-4 py-2 border-t border-surface-tertiary flex items-center justify-between text-[10px] text-muted">
          <span>{totalTokens.toLocaleString()} tokens</span>
          <span>{(totalLatencyMs / 1000).toFixed(1)}s</span>
          <span>{steps.length} steps</span>
        </div>
      )}
    </div>
  )
}
