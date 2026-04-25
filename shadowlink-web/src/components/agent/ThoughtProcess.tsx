/**
 * ThoughtProcess — displays the agent's internal reasoning chain.
 */

import { useAgentStore } from '@/stores'

export function ThoughtProcess() {
  const steps = useAgentStore((s) => s.steps)
  const currentThought = useAgentStore((s) => s.currentThought)
  const isRunning = useAgentStore((s) => s.isRunning)

  if (steps.length === 0 && !currentThought) return null

  return (
    <div className="space-y-2">
      <h3 className="text-xs font-medium text-muted uppercase tracking-wider">Thought Process</h3>
      <div className="space-y-1.5 max-h-[300px] overflow-y-auto">
        {steps
          .filter((s) => s.stepType === 'thought' || s.stepType === 'reflection')
          .map((step, i) => (
            <div key={i} className="px-3 py-2 rounded-lg bg-surface-secondary text-xs text-muted leading-relaxed">
              <span className="text-primary-400 font-medium mr-1.5">
                {step.stepType === 'reflection' ? 'Reflect' : 'Think'}:
              </span>
              {step.content}
            </div>
          ))}

        {/* Streaming thought */}
        {isRunning && currentThought && (
          <div className="px-3 py-2 rounded-lg bg-surface-secondary text-xs text-muted leading-relaxed border border-primary-500/20">
            <span className="text-primary-400 font-medium mr-1.5">Thinking:</span>
            {currentThought}
            <span className="inline-block w-1.5 h-3 ml-0.5 bg-primary-400 animate-pulse-subtle" />
          </div>
        )}
      </div>
    </div>
  )
}
