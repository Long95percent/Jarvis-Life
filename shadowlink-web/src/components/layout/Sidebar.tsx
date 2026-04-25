/**
 * Sidebar — top-level navigation + mode switcher.
 *
 * Streamlined to the three primary destinations: Jarvis, Knowledge, Settings.
 * Chat / Brainstorm have been folded into Jarvis (private chat + roundtable).
 */

import { Link, useLocation } from 'react-router-dom'
import { ModeSwitcher } from '../ambient/ModeSwitcher'

const navItems = [
  { path: '/jarvis', label: 'Jarvis', icon: '🎩' },
  { path: '/knowledge', label: '知识库', icon: '📚' },
  { path: '/settings', label: '设置', icon: '⚙️' },
]

interface SidebarProps {
  collapsed: boolean
}

export function Sidebar({ collapsed }: SidebarProps) {
  const location = useLocation()

  return (
    <aside
      className="flex flex-col border-r border-surface-tertiary bg-surface transition-all duration-300"
      style={{ width: collapsed ? 0 : 'var(--sidebar-width)' }}
    >
      {!collapsed && (
        <>
          {/* Logo / Brand */}
          <div className="flex items-center gap-2 px-4 py-4 border-b border-surface-tertiary">
            <div className="w-8 h-8 rounded-lg ambient-gradient flex items-center justify-center text-white font-bold text-sm">
              J
            </div>
            <span className="font-semibold text-foreground truncate">Jarvis · Be IronMan</span>
          </div>

          {/* Mode Switcher */}
          <div className="px-3 py-2">
            <ModeSwitcher />
          </div>

          {/* Top-level Nav */}
          <nav className="px-2 py-1 flex-1">
            <ul className="space-y-0.5">
              {navItems.map((item) => {
                const isActive = location.pathname.startsWith(item.path)
                return (
                  <li key={item.path}>
                    <Link
                      to={item.path}
                      className={`flex items-center gap-2 w-full text-left px-3 py-2 rounded-lg text-sm transition-colors
                        ${
                          isActive
                            ? 'bg-surface-secondary text-foreground'
                            : 'text-muted hover:bg-surface-secondary hover:text-foreground'
                        }`}
                    >
                      <span className="text-base">{item.icon}</span>
                      <span className="truncate">{item.label}</span>
                    </Link>
                  </li>
                )
              })}
            </ul>
          </nav>
        </>
      )}
    </aside>
  )
}
