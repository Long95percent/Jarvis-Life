/**
 * SettingsPage — tabbed shell for LLM providers, user profile, and agent config.
 *
 * - Tab 1 (AI 模型):   existing LLM provider mgmt (preserved, extracted to SettingsLLM).
 * - Tab 2 (个人资料): user profile -> /api/v1/jarvis/profile.
 * - Tab 3 (智能体):    per-agent toggles + interrupt budgets -> /api/v1/jarvis/agent-config/*.
 */

import { useState } from 'react'
import { ArrowLeft, Cpu, User, Users } from 'lucide-react'
import { Link } from 'react-router-dom'
import { SettingsLLM } from '@/components/settings/SettingsLLM'
import { SettingsProfile } from '@/components/settings/SettingsProfile'
import { SettingsAgents } from '@/components/settings/SettingsAgents'

type Tab = 'llm' | 'profile' | 'agents'

const TABS: Array<{ id: Tab; label: string; Icon: typeof Cpu }> = [
  { id: 'llm', label: 'AI 模型', Icon: Cpu },
  { id: 'profile', label: '个人资料', Icon: User },
  { id: 'agents', label: '智能体', Icon: Users },
]

export function SettingsPage() {
  const [tab, setTab] = useState<Tab>('llm')
  return (
    <div className="flex h-full bg-surface-tertiary">
      {/* Sidebar tabs */}
      <aside className="w-56 border-r border-surface-tertiary bg-surface flex flex-col">
        <div className="px-4 py-5 border-b border-surface-tertiary flex items-center gap-3">
          <Link
            to="/jarvis"
            className="p-1.5 rounded-md hover:bg-surface-secondary text-muted"
            title="返回"
          >
            <ArrowLeft size={18} />
          </Link>
          <h1 className="text-lg font-semibold">设置</h1>
        </div>
        <nav className="flex-1 p-2 space-y-1">
          {TABS.map(({ id, label, Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                tab === id
                  ? 'bg-primary-500/10 text-primary-400 font-medium'
                  : 'text-muted hover:bg-surface-secondary'
              }`}
            >
              <Icon size={16} />
              {label}
            </button>
          ))}
        </nav>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto p-8">
          {tab === 'llm' && <SettingsLLM />}
          {tab === 'profile' && <SettingsProfile />}
          {tab === 'agents' && <SettingsAgents />}
        </div>
      </main>
    </div>
  )
}
