import { useCallback, useEffect, useMemo, useState } from 'react'
import { Brain, Clock, Heart, Loader2, MapPin, ShieldCheck, Sparkles, UserRound } from 'lucide-react'
import {
  jarvisSettingsApi,
  type ShadowProfile,
  type UserProfile,
} from '@/services/jarvisSettingsApi'
import { jarvisMemoryApi, type JarvisMemory } from '@/services/jarvisMemoryApi'

interface PersonaData {
  profile: UserProfile | null
  shadowProfile: ShadowProfile | null
  memories: JarvisMemory[]
}

function formatList(items?: string[]) {
  if (!items || items.length === 0) return '暂未填写'
  return items.join('、')
}

function formatDateTime(value?: string | number | null) {
  if (!value) return '暂无记录'
  const date = typeof value === 'number' ? new Date(value * 1000) : new Date(value)
  if (Number.isNaN(date.getTime())) return '暂无记录'
  return date.toLocaleString('zh-CN', { hour12: false })
}

function stringifyPreference(value: unknown) {
  if (value === null || value === undefined || value === '') return '暂无'
  if (Array.isArray(value)) return value.length > 0 ? value.join('、') : '暂无'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function getMemoryKindLabel(kind: string) {
  const labels: Record<string, string> = {
    preference: '偏好',
    profile: '资料',
    habit: '习惯',
    schedule: '日程',
    care: '关怀',
  }
  return labels[kind] || kind || '记忆'
}

export function KnowledgePage() {
  const [data, setData] = useState<PersonaData>({
    profile: null,
    shadowProfile: null,
    memories: [],
  })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadPersona = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [profile, shadowProfile, memories] = await Promise.all([
        jarvisSettingsApi.getProfile(),
        jarvisSettingsApi.getShadowProfile(),
        jarvisMemoryApi.listMemories({ limit: 12 }),
      ])
      setData({ profile, shadowProfile, memories })
    } catch (err) {
      setError((err as Error).message || '个人画像加载失败，请稍后重试。')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadPersona()
  }, [loadPersona])

  const preferenceEntries = useMemo(() => {
    const preferences = data.shadowProfile?.preferences || {}
    return Object.entries(preferences).filter(([, value]) => value !== null && value !== undefined)
  }, [data.shadowProfile])

  const profile = data.profile

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        <section className="surface-card p-6 border border-surface-tertiary">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.25em] text-primary-400 font-semibold">Persona Profile</p>
              <h1 className="mt-2 text-2xl font-semibold text-foreground flex items-center gap-2">
                <Brain size={24} /> 个人画像
              </h1>
              <p className="mt-2 text-sm text-muted max-w-2xl">
                Jarvis 根据你的基础设置、长期记忆和日常互动整理出的理解。这里暂时替代知识库面板，不直接访问后端路径。
              </p>
            </div>
            <button
              type="button"
              onClick={loadPersona}
              disabled={loading}
              className="px-3 py-2 rounded-lg bg-surface-secondary text-sm text-foreground hover:bg-surface-tertiary disabled:opacity-60"
            >
              {loading ? '刷新中…' : '刷新画像'}
            </button>
          </div>
        </section>

        {error && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
            {error}
          </div>
        )}

        {loading ? (
          <div className="surface-card p-10 flex items-center justify-center gap-3 text-muted">
            <Loader2 size={20} className="animate-spin" /> 正在读取个人画像…
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="surface-card p-5 border border-surface-tertiary">
                <div className="flex items-center gap-2 text-sm text-muted mb-2">
                  <UserRound size={16} /> 基础资料
                </div>
                <p className="text-xl font-semibold text-foreground">{profile?.name || '未设置姓名'}</p>
                <p className="mt-1 text-sm text-muted">{profile?.occupation || '未设置职业'}</p>
              </div>
              <div className="surface-card p-5 border border-surface-tertiary">
                <div className="flex items-center gap-2 text-sm text-muted mb-2">
                  <MapPin size={16} /> 位置与时区
                </div>
                <p className="text-base font-medium text-foreground">{profile?.location?.label || '未设置位置'}</p>
                <p className="mt-1 text-sm text-muted">{profile?.location?.timezone || '未设置时区'}</p>
              </div>
              <div className="surface-card p-5 border border-surface-tertiary">
                <div className="flex items-center gap-2 text-sm text-muted mb-2">
                  <Clock size={16} /> 作息节律
                </div>
                <p className="text-base font-medium text-foreground">
                  {profile?.sleep_schedule?.bedtime || '--:--'} - {profile?.sleep_schedule?.wake || '--:--'}
                </p>
                <p className="mt-1 text-sm text-muted">睡觉时间 - 起床时间</p>
              </div>
            </div>

            <section className="surface-card p-6 border border-surface-tertiary space-y-4">
              <div className="flex items-center gap-2">
                <Heart size={18} className="text-primary-400" />
                <h2 className="text-lg font-semibold text-foreground">你主动告诉 Jarvis 的信息</h2>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                <div className="rounded-lg bg-surface-secondary p-4">
                  <p className="text-muted mb-1">兴趣方向</p>
                  <p className="text-foreground">{formatList(profile?.interests)}</p>
                </div>
                <div className="rounded-lg bg-surface-secondary p-4">
                  <p className="text-muted mb-1">饮食限制</p>
                  <p className="text-foreground">{formatList(profile?.diet_restrictions)}</p>
                </div>
              </div>
            </section>

            <section className="surface-card p-6 border border-surface-tertiary space-y-4">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <Sparkles size={18} className="text-primary-400" />
                  <h2 className="text-lg font-semibold text-foreground">系统学习到的偏好</h2>
                </div>
                <span className="text-xs text-muted">
                  互动 {data.shadowProfile?.interaction_count || 0} 次 · 更新于 {formatDateTime(data.shadowProfile?.last_updated)}
                </span>
              </div>
              {preferenceEntries.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {preferenceEntries.map(([key, value]) => (
                    <div key={key} className="rounded-lg bg-surface-secondary p-4 text-sm">
                      <p className="text-muted mb-1">{key}</p>
                      <p className="text-foreground break-words">{stringifyPreference(value)}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted">暂时还没有学习到稳定偏好。继续与 Jarvis 对话后，这里会逐步丰富。</p>
              )}
            </section>

            <section className="surface-card p-6 border border-surface-tertiary space-y-4">
              <div className="flex items-center gap-2">
                <Brain size={18} className="text-primary-400" />
                <h2 className="text-lg font-semibold text-foreground">长期记忆摘要</h2>
              </div>
              {data.memories.length > 0 ? (
                <div className="space-y-3">
                  {data.memories.map((memory) => (
                    <article key={memory.id} className="rounded-lg bg-surface-secondary p-4">
                      <div className="flex items-center justify-between gap-3 mb-2">
                        <span className="text-xs px-2 py-1 rounded-full bg-surface-tertiary text-muted">
                          {getMemoryKindLabel(memory.memory_kind)}
                        </span>
                        <span className="text-xs text-muted">重要度 {memory.importance.toFixed(2)}</span>
                      </div>
                      <p className="text-sm text-foreground leading-6">{memory.content}</p>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted">暂无长期记忆。后续对话、日程和关怀模块产生的稳定信息会在这里展示。</p>
              )}
            </section>

            <section className="rounded-xl border border-primary-500/20 bg-primary-500/10 p-4 text-sm text-muted flex gap-3">
              <ShieldCheck size={18} className="text-primary-400 shrink-0 mt-0.5" />
              <p>
                隐私说明：本页只展示通过服务层读取到的画像信息。你可以在设置页关闭 Shadow Learner，或在记忆面板删除不想保留的长期记忆。
              </p>
            </section>
          </>
        )}
      </div>
    </div>
  )
}
