async function requestJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return await res.json() as T
}

export interface JarvisLocation {
  lat: number
  lng: number
  label: string
  timezone: string
  timezone_source: 'auto' | 'manual' | string
}

export interface SleepSchedule {
  bedtime: string
  wake: string
}

export interface UserProfile {
  name: string
  pronouns: string
  occupation: string
  location: JarvisLocation
  sleep_schedule: SleepSchedule
  diet_restrictions: string[]
  interests: string[]
}

export interface WeatherPreview {
  temperature_c?: number
  weather_code?: number
  wind_kmh?: number
  precipitation_mm?: number
  is_good_weather?: boolean
  error?: string
}

export interface JarvisTimeContext {
  timezone: string
  timezone_abbr: string
  utc_offset: string
  local_iso: string
  local_date: string
  local_time: string
  location_label?: string | null
}

export interface LocationSuggestion extends Partial<JarvisLocation> {
  weather?: WeatherPreview
  label_error?: string
}

export interface AgentCfg {
  enabled: boolean
  interrupt_budget: number
}

export interface AgentConfigResponse {
  agents: Record<string, AgentCfg>
  shadow_learner_enabled: boolean
}

export interface ShadowProfile {
  preferences: Record<string, unknown>
  interaction_count: number
  last_updated: string | null
}

export interface BrowserLocationPayload {
  lat: number
  lng: number
  browser_timezone: string
  current_label?: string
}

export interface CityLocationPayload {
  city_name: string
  browser_timezone: string
}

export const jarvisSettingsApi = {
  getProfile(): Promise<UserProfile> {
    return requestJSON<UserProfile>('/api/v1/jarvis/profile')
  },

  updateProfile(profile: UserProfile): Promise<UserProfile> {
    return requestJSON<UserProfile>('/api/v1/jarvis/profile', {
      method: 'PATCH',
      body: JSON.stringify(profile),
    })
  },

  resolveBrowserLocation(payload: BrowserLocationPayload): Promise<LocationSuggestion> {
    return requestJSON<LocationSuggestion>('/api/v1/jarvis/time/browser-location', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  resolveCityLocation(payload: CityLocationPayload): Promise<LocationSuggestion> {
    return requestJSON<LocationSuggestion>('/api/v1/jarvis/time/city-location', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  getTimeContext(browserTimezone?: string): Promise<JarvisTimeContext> {
    const query = browserTimezone ? `?browser_timezone=${encodeURIComponent(browserTimezone)}` : ''
    return requestJSON<JarvisTimeContext>(`/api/v1/jarvis/time/context${query}`)
  },

  getAgentConfig(): Promise<AgentConfigResponse> {
    return requestJSON<AgentConfigResponse>('/api/v1/jarvis/agent-config')
  },

  updateAgentConfig(agentId: string, patch: Partial<AgentCfg>): Promise<void> {
    return requestJSON<void>(`/api/v1/jarvis/agent-config/${encodeURIComponent(agentId)}`, {
      method: 'PATCH',
      body: JSON.stringify(patch),
    })
  },

  async getShadowProfile(): Promise<ShadowProfile | null> {
    const res = await fetch('/api/v1/jarvis/shadow/profile')
    if (!res.ok) return null
    return await res.json() as ShadowProfile
  },

  toggleShadowLearner(enabled: boolean): Promise<AgentConfigResponse> {
    return requestJSON<AgentConfigResponse>('/api/v1/jarvis/agent-config/shadow/toggle', {
      method: 'PATCH',
      body: JSON.stringify({ enabled }),
    })
  },
}
