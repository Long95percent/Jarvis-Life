/**
 * PlanProgress — visualizes plan-and-execute steps with status indicators.
 */

import { useAgentStore } from '@/stores'

const statusIcon: Record<string, string> = {
  pending: '',
  running: '',
  completed: '',
  failed: '',
  skipped: '',
}

const statusColor: Record<string, string> = {
  pending: 'text-muted',
  running: 'text-primary-400 animate-pulse-subtle',
  completed: 'text-green-400',
  failed: 'text-red-400',
  skipped: 'text-muted/50',
}

export function PlanProgress() {
  const plan = useAgentStore((s) => s.plan)

  if (plan.length === 0) return null

  const completed = plan.filter((s) => s.status === 'completed').length

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-medium text-muted uppercase tracking-wider">Execution Plan</h3>
        <span className="text-xs text-muted">
          {completed}/{plan.length}
        </span>
      </div>

      {/* Progress bar */}
      <div className="h-1 rounded-full bg-surface-tertiary overflow-hidden">
        <div
          className="h-full ambient-gradient transition-all duration-500"
          style={{ width: `${(completed / plan.length) * 100}%` }}
        />
      </div>

      {/* Steps */}
      <div className="space-y-1">
        {plan.map((step) => (
          <div
            key={step.index}
            className={`flex items-start gap-2 px-3 py-1.5 rounded-lg text-xs
              ${step.status === 'running' ? 'bg-surface-secondary' : ''}`}
          >
            <span className={`shrink-0 mt-0.5 ${statusColor[step.status]}`}>
              {statusIcon[step.status]}
            </span>
            <span className={step.status === 'skipped' ? 'line-through text-muted/50' : 'text-foreground'}>
              {step.description}
            </span>
            {step.tool && (
              <span className="ml-auto shrink-0 px-1.5 py-0.5 rounded bg-surface-tertiary text-muted text-[10px]">
                {step.tool}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
