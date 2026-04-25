/**
 * TopBar — Jarvis branding, strategy badge, sidebar toggle, settings.
 */

import { useSettingsStore, useAgentStore } from '@/stores'
import { Link } from 'react-router-dom'

export function TopBar() {
  const toggleSidebar = useSettingsStore((s) => s.toggleSidebar)
  const strategy = useAgentStore((s) => s.strategy)

  return (
    <header className="flex items-center justify-between h-12 px-4 border-b border-surface-tertiary bg-surface shrink-0">
      <div className="flex items-center gap-3">
        {/* Sidebar toggle */}
        <button
          onClick={toggleSidebar}
          className="p-1.5 rounded-md hover:bg-surface-secondary transition-colors text-muted"
          aria-label="Toggle sidebar"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M3 12h18M3 6h18M3 18h18" />
          </svg>
        </button>

        {/* Title */}
        <h1 className="text-sm font-medium text-foreground truncate max-w-[300px]">
          Jarvis · Be IronMan
        </h1>

        {/* Strategy badge */}
        {strategy && (
          <span className="px-2 py-0.5 text-xs rounded-full bg-surface-secondary text-muted">
            {strategy}
          </span>
        )}
      </div>

      <div className="flex items-center gap-2">
        {/* Settings gear */}
        <Link
          to="/settings"
          className="p-1.5 rounded-md hover:bg-surface-secondary transition-colors text-muted"
          aria-label="Settings"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
            <circle cx="12" cy="12" r="3" />
          </svg>
        </Link>
      </div>
    </header>
  )
}
