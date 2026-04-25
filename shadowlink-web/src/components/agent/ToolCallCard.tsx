/**
 * ToolCallCard — displays a single tool invocation with input/output.
 */

import { useState } from 'react'
import type { AgentStep } from '@/types'

interface ToolCallCardProps {
  step: AgentStep
}

export function ToolCallCard({ step }: ToolCallCardProps) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="surface-card overflow-hidden text-xs">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-3 py-2 hover:bg-surface-secondary transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="w-5 h-5 rounded flex items-center justify-center bg-primary-500/20 text-primary-400 text-[10px] font-bold">
            T
          </span>
          <span className="font-medium text-foreground">{step.toolName || 'tool_call'}</span>
        </div>
        <div className="flex items-center gap-2 text-muted">
          {step.latencyMs > 0 && <span>{step.latencyMs}ms</span>}
          <svg
            width="12" height="12" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" strokeWidth="2"
            className={`transition-transform ${expanded ? 'rotate-180' : ''}`}
          >
            <path d="m6 9 6 6 6-6" />
          </svg>
        </div>
      </button>

      {expanded && (
        <div className="px-3 pb-3 space-y-2 border-t border-surface-tertiary">
          {step.toolInput && (
            <div>
              <span className="text-muted font-medium">Input:</span>
              <pre className="mt-1 p-2 rounded bg-surface-tertiary text-muted overflow-x-auto">
                {JSON.stringify(step.toolInput, null, 2)}
              </pre>
            </div>
          )}
          {step.toolOutput && (
            <div>
              <span className="text-muted font-medium">Output:</span>
              <pre className="mt-1 p-2 rounded bg-surface-tertiary text-muted overflow-x-auto max-h-[200px]">
                {step.toolOutput}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
