async function requestJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api/v1/jarvis${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return await res.json() as T
}

export interface CareTrigger {
  trigger_type: string
  severity: string
  description?: string
}

export interface CareTrendPoint {
  date: string
  mood_score: number | null
  stress_score: number | null
  energy_score: number | null
  sleep_risk_score: number | null
  schedule_pressure_score: number | null
  dominant_emotions: string[]
  risk_flags: string[]
  summary?: string | null
  confidence: number
}

export interface CareTrendDetail {
  date?: string
  snapshot: CareTrendPoint
  stress_signals: Array<Record<string, unknown>>
  behavior_observations: Array<Record<string, unknown>>
  emotion_observations: Array<Record<string, unknown>>
  care_triggers: CareTrigger[]
  positive_events: string[]
  negative_events: string[]
  explanations: string[]
}

export interface CareTrendsResponse {
  tracking_enabled?: boolean
  range: string
  start: string
  end: string
  series: CareTrendPoint[]
  details: Record<string, CareTrendDetail>
}

export const jarvisCareApi = {
  getCareSettings(): Promise<{ psychological_tracking_enabled: boolean }> {
    return requestJSON('/care/settings')
  },

  setPsychologicalTracking(enabled: boolean): Promise<{ psychological_tracking_enabled: boolean }> {
    return requestJSON('/care/settings/tracking', {
      method: 'PATCH',
      body: JSON.stringify({ enabled }),
    })
  },

  clearCareData(): Promise<{ deleted: Record<string, number> }> {
    return requestJSON('/care/data', { method: 'DELETE' })
  },

  getCareTrends(params?: { range?: 'week' | 'month' | 'year'; end?: string }): Promise<CareTrendsResponse> {
    const query = new URLSearchParams()
    if (params?.range) query.set('range', params.range)
    if (params?.end) query.set('end', params.end)
    const suffix = query.toString() ? `?${query.toString()}` : ''
    return requestJSON(`/care/trends${suffix}`)
  },

  getCareDayDetail(day: string): Promise<CareTrendDetail> {
    return requestJSON(`/care/days/${encodeURIComponent(day)}`)
  },

  sendCareFeedback(id: string, payload: { feedback: 'helpful' | 'too_frequent' | 'not_needed' | 'snooze' | 'handled'; snooze_minutes?: number }): Promise<{ message: Record<string, unknown> | null; intervention: Record<string, unknown> | null }> {
    return requestJSON(`/messages/${encodeURIComponent(id)}/care-feedback`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
}
