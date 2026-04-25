/**
 * StatusBar — bottom bar showing agent status, token count, mode info.
 */

import { useAgentStore, useAmbientStore } from '@/stores'

export function StatusBar() {
  const isRunning = useAgentStore((s) => s.isRunning)
  const totalTokens = useAgentStore((s) => s.totalTokens)
  const strategy = useAgentStore((s) => s.strategy)
  const activeModeId = useAmbientStore((s) => s.activeModeId)

  return (
    <footer className="flex items-center justify-between h-7 px-4 border-t border-surface-tertiary bg-surface text-xs text-muted shrink-0">
      <div className="flex items-center gap-3">
        {/* Agent status indicator */}
        <div className="flex items-center gap-1.5">
          <span
            className={`w-2 h-2 rounded-full ${isRunning ? 'bg-green-400 animate-pulse-subtle' : 'bg-surface-tertiary'}`}
          />
          <span>{isRunning ? `Running (${strategy})` : 'Idle'}</span>
        </div>

        {totalTokens > 0 && (
          <span>{totalTokens.toLocaleString()} tokens</span>
        )}
      </div>

      <div className="flex items-center gap-3">
        <span className="capitalize">{activeModeId.replace('-', ' ')}</span>
        <span>ShadowLink v3.0</span>
      </div>
    </footer>
  )
}
