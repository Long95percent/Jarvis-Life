/**
 * SettingsAgents — per-agent enable/disable + interrupt-budget tuning
 * plus the Shadow preference-learner master toggle.
 *
 * Auto-save with 500ms debounce on slider changes (so dragging doesn't
 * hammer the API), immediate save on toggle. This was chosen over a
 * per-card "保存" button because toggles/sliders are intrinsically
 * transient — users expect them to stick the moment they release.
 */

import { useEffect, useRef, useState } from 'react'
import { Check, Loader2 } from 'lucide-react'
import { jarvisSettingsApi } from '@/services/jarvisSettingsApi'
import { JARVIS_AGENTS } from '@/components/jarvis/agentMeta'

interface AgentCfg {
  enabled: boolean
  interrupt_budget: number
}

interface AgentConfigResponse {
  agents: Record<string, AgentCfg>
  shadow_learner_enabled: boolean
}

interface ShadowProfile {
  preferences: Record<string, unknown>
  interaction_count: number
  last_updated: string | null
}

const CORE_AGENT_IDS = ['alfred', 'maxwell', 'nora', 'mira', 'leo'] as const

export function SettingsAgents() {
  const [cfg, setCfg] = useState<AgentConfigResponse>({
    agents: {},
    shadow_learner_enabled: true,
  })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [savedAgent, setSavedAgent] = useState<string | null>(null)
  const [shadowSaved, setShadowSaved] = useState(false)
  const [shadowProfile, setShadowProfile] = useState<ShadowProfile | null>(null)

  // Debounce timers keyed by agent_id
  const debounceRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map())

  useEffect(() => {
    let alive = true
    ;(async () => {
      try {
        const data = await jarvisSettingsApi.getAgentConfig()
        if (alive) setCfg(data)
      } catch (e) {
        if (alive) setError(String(e))
      } finally {
        if (alive) setLoading(false)
      }
    })()
    ;(async () => {
      try {
        const data = await jarvisSettingsApi.getShadowProfile()
        if (alive) setShadowProfile(data)
      } catch {
        // silent — profile is best-effort
      }
    })()
    return () => {
      alive = false
      debounceRef.current.forEach(clearTimeout)
    }
  }, [])

  useEffect(() => {
    if (!savedAgent) return
    const t = setTimeout(() => setSavedAgent(null), 1500)
    return () => clearTimeout(t)
  }, [savedAgent])

  useEffect(() => {
    if (!shadowSaved) return
    const t = setTimeout(() => setShadowSaved(false), 1500)
    return () => clearTimeout(t)
  }, [shadowSaved])

  const saveAgent = async (agentId: string, patch: Partial<AgentCfg>) => {
    try {
      await jarvisSettingsApi.updateAgentConfig(agentId, patch)
      setSavedAgent(agentId)
      setError(null)
    } catch (e) {
      setError(String(e))
    }
  }

  const updateAgent = (agentId: string, patch: Partial<AgentCfg>, debounceMs = 0) => {
    setCfg((c) => ({
      ...c,
      agents: {
        ...c.agents,
        [agentId]: { ...(c.agents[agentId] ?? { enabled: true, interrupt_budget: 3 }), ...patch },
      },
    }))
    // clear any prior timer for this agent
    const existing = debounceRef.current.get(agentId)
    if (existing) clearTimeout(existing)
    if (debounceMs > 0) {
      const t = setTimeout(() => {
        saveAgent(agentId, patch)
        debounceRef.current.delete(agentId)
      }, debounceMs)
      debounceRef.current.set(agentId, t)
    } else {
      saveAgent(agentId, patch)
    }
  }

  const toggleShadow = async (enabled: boolean) => {
    setCfg((c) => ({ ...c, shadow_learner_enabled: enabled }))
    try {
      const data = await jarvisSettingsApi.toggleShadowLearner(enabled)
      setCfg(data)
      setShadowSaved(true)
      setError(null)
    } catch (e) {
      setError(String(e))
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-muted text-sm p-8">
        <Loader2 size={16} className="animate-spin" /> 加载智能体配置...
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-foreground">智能体</h1>
        <p className="text-sm text-muted mt-1">
          控制哪些 agent 会主动打扰你,以及每日打扰次数预算。
        </p>
      </div>

      {error && (
        <div className="px-3 py-2 rounded-md bg-red-500/10 border border-red-500/30 text-red-400 text-xs">
          {error}
        </div>
      )}

      {/* Agent cards */}
      <section className="space-y-3">
        {CORE_AGENT_IDS.map((id) => {
          const meta = JARVIS_AGENTS[id]
          const agent = cfg.agents[id] ?? { enabled: true, interrupt_budget: 3 }
          return (
            <div
              key={id}
              className="surface-card p-5 border border-surface-tertiary space-y-4"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3 min-w-0">
                  <div
                    className="w-10 h-10 rounded-lg flex items-center justify-center text-lg"
                    style={{ backgroundColor: `${meta?.color ?? '#6366f1'}20` }}
                  >
                    {meta?.icon ?? '🤖'}
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-foreground">
                        {meta?.name ?? id}
                      </span>
                      <span className="text-xs text-muted">{meta?.role}</span>
                      {savedAgent === id && (
                        <span className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-green-500/15 text-green-400 text-[10px] font-medium">
                          <Check size={10} /> 已保存
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-muted mt-0.5">
                      每天最多主动打扰 {agent.interrupt_budget} 次
                    </p>
                  </div>
                </div>

                {/* Enable toggle */}
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    className="sr-only peer"
                    checked={agent.enabled}
                    onChange={(e) => updateAgent(id, { enabled: e.target.checked })}
                  />
                  <div className="w-10 h-5 bg-surface-secondary rounded-full peer peer-checked:bg-primary-500 transition-colors" />
                  <div className="absolute left-0.5 top-0.5 w-4 h-4 bg-white rounded-full transition-transform peer-checked:translate-x-5" />
                </label>
              </div>

              {/* Budget slider */}
              <div className={`space-y-2 ${!agent.enabled ? 'opacity-40 pointer-events-none' : ''}`}>
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-muted">
                    打扰预算: {agent.interrupt_budget}
                  </span>
                  <span className="text-[10px] text-muted">0 (安静) — 10 (频繁)</span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={10}
                  step={1}
                  value={agent.interrupt_budget}
                  onChange={(e) =>
                    updateAgent(id, { interrupt_budget: parseInt(e.target.value) || 0 }, 500)
                  }
                  className="w-full accent-primary-500"
                />
              </div>
            </div>
          )
        })}
      </section>

      {/* Shadow learner */}
      <section className="surface-card p-5 border border-surface-tertiary space-y-3">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-medium text-foreground">偏好学习器 (Shadow)</h2>
              {shadowSaved && (
                <span className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-green-500/15 text-green-400 text-[10px] font-medium">
                  <Check size={10} /> 已保存
                </span>
              )}
            </div>
            <p className="text-xs text-muted mt-1 leading-relaxed">
              Shadow 会在后台静默观察你和各 agent 的对话,学习你的偏好,
              逐步让每个 agent 的回复更贴合你。
            </p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer shrink-0">
            <input
              type="checkbox"
              className="sr-only peer"
              checked={cfg.shadow_learner_enabled}
              onChange={(e) => toggleShadow(e.target.checked)}
            />
            <div className="w-10 h-5 bg-surface-secondary rounded-full peer peer-checked:bg-primary-500 transition-colors" />
            <div className="absolute left-0.5 top-0.5 w-4 h-4 bg-white rounded-full transition-transform peer-checked:translate-x-5" />
          </label>
        </div>

        {/* Learned preferences */}
        {shadowProfile && (
          <div className="pt-3 border-t border-surface-tertiary/60 space-y-2">
            <div className="text-xs font-medium text-muted">已学到</div>
            {shadowProfile.interaction_count === 0 ? (
              <p className="text-xs text-muted leading-relaxed">
                还没有学习到任何偏好,多和 agents 聊聊。
              </p>
            ) : (
              <>
                <p className="text-xs text-muted">
                  已观察 {shadowProfile.interaction_count} 次互动
                </p>
                {Object.keys(shadowProfile.preferences).length > 0 && (
                  <div className="space-y-1">
                    <div className="text-xs text-muted">偏好:</div>
                    <ul className="space-y-0.5">
                      {Object.entries(shadowProfile.preferences).map(([k, v]) => (
                        <li
                          key={k}
                          className="text-xs text-foreground pl-3 font-mono"
                        >
                          · {k}: {JSON.stringify(v)}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </section>
    </div>
  )
}

export default SettingsAgents
