/**
 * SettingsProfile — user profile editor (name, location, sleep, diet, interests).
 *
 * Loads on mount from GET /api/v1/jarvis/profile.
 * Saves via explicit "保存" button -> PATCH /api/v1/jarvis/profile.
 * Explicit save was chosen (over debounced auto-save) because it gives clear
 * save-state feedback in a demo and avoids partial-patch noise while typing.
 */

import { useEffect, useState, type KeyboardEvent } from 'react'
import { Check, Loader2, MapPin, X } from 'lucide-react'
import { jarvisSettingsApi } from '@/services/jarvisSettingsApi'

interface Location {
  lat: number
  lng: number
  label: string
  timezone: string
  timezone_source: 'auto' | 'manual' | string
}

interface SleepSchedule {
  bedtime: string
  wake: string
}

interface UserProfile {
  name: string
  pronouns: string
  occupation: string
  location: Location
  sleep_schedule: SleepSchedule
  diet_restrictions: string[]
  interests: string[]
}

interface WeatherPreview {
  temperature_c?: number
  weather_code?: number
  wind_kmh?: number
  precipitation_mm?: number
  is_good_weather?: boolean
  error?: string
}

interface LocationSuggestion extends Partial<Location> {
  weather?: WeatherPreview
  label_error?: string
}

const EMPTY_PROFILE: UserProfile = {
  name: '',
  pronouns: '',
  occupation: '',
  location: { lat: 35.6762, lng: 139.6503, label: 'Tokyo', timezone: 'Asia/Tokyo', timezone_source: 'auto' },
  sleep_schedule: { bedtime: '23:00', wake: '07:00' },
  diet_restrictions: [],
  interests: [],
}

export function SettingsProfile() {
  const [profile, setProfile] = useState<UserProfile>(EMPTY_PROFILE)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [savedAt, setSavedAt] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [dietInput, setDietInput] = useState('')
  const [interestInput, setInterestInput] = useState('')
  const [geoBusy, setGeoBusy] = useState(false)
  const [cityResolving, setCityResolving] = useState(false)
  const [weatherPreview, setWeatherPreview] = useState<WeatherPreview | null>(null)
  const [locationHint, setLocationHint] = useState<string | null>(null)

  const browserTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Shanghai'
  const notifyProfileChanged = () => window.dispatchEvent(new Event('jarvis:profile-updated'))

  useEffect(() => {
    let alive = true
    ;(async () => {
      try {
        const data = await jarvisSettingsApi.getProfile()
        if (alive) {
          setProfile({
            ...EMPTY_PROFILE,
            ...data,
            location: { ...EMPTY_PROFILE.location, ...(data.location ?? {}) },
            sleep_schedule: { ...EMPTY_PROFILE.sleep_schedule, ...(data.sleep_schedule ?? {}) },
            diet_restrictions: data.diet_restrictions ?? [],
            interests: data.interests ?? [],
          })
        }
      } catch (e) {
        if (alive) setError(String(e))
      } finally {
        if (alive) setLoading(false)
      }
    })()
    return () => {
      alive = false
    }
  }, [])

  // Hide "saved" badge after 2s
  useEffect(() => {
    if (savedAt == null) return
    const t = setTimeout(() => setSavedAt(null), 2000)
    return () => clearTimeout(t)
  }, [savedAt])

  const saveProfile = async (nextProfile: UserProfile): Promise<UserProfile> => {
    const saved = await jarvisSettingsApi.updateProfile(nextProfile)
    const normalized = {
      ...EMPTY_PROFILE,
      ...saved,
      location: { ...EMPTY_PROFILE.location, ...(saved.location ?? {}) },
      sleep_schedule: { ...EMPTY_PROFILE.sleep_schedule, ...(saved.sleep_schedule ?? {}) },
      diet_restrictions: saved.diet_restrictions ?? [],
      interests: saved.interests ?? [],
    }
    setProfile(normalized)
    setSavedAt(Date.now())
    notifyProfileChanged()
    return normalized
  }

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    try {
      await saveProfile(profile)
    } catch (e) {
      setError(String(e))
    } finally {
      setSaving(false)
    }
  }

  const useBrowserLocation = () => {
    if (!navigator.geolocation) {
      setError('浏览器不支持定位')
      return
    }
    setGeoBusy(true)
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const lat = Number(pos.coords.latitude.toFixed(6))
        const lng = Number(pos.coords.longitude.toFixed(6))
        let suggestedLocation: LocationSuggestion = {
          lat,
          lng,
          label: 'Current Location',
          timezone: browserTimezone,
          timezone_source: 'browser',
        }
        try {
          const data = await jarvisSettingsApi.resolveBrowserLocation({
            lat,
            lng,
            browser_timezone: browserTimezone,
            current_label: profile.location.label,
          })
          const { weather, label_error, ...location } = data
          suggestedLocation = { ...suggestedLocation, ...location }
          setWeatherPreview(weather ?? null)
          setLocationHint(label_error ? `城市名解析失败：${label_error}` : null)
        } catch {
          // Keep the browser-derived fallback above.
          setLocationHint('城市名解析失败：网络或地理编码服务不可用')
        }
        const { weather: _weather, label_error: _labelError, ...locationFields } = suggestedLocation
        const nextProfile = {
          ...profile,
          location: {
            ...profile.location,
            ...locationFields,
          },
        }
        try {
          await saveProfile(nextProfile)
        } catch (e) {
          setProfile(nextProfile)
          setError(String(e))
        } finally {
          setGeoBusy(false)
        }
      },
      (err) => {
        setError(`定位失败: ${err.message}`)
        setGeoBusy(false)
      },
      { enableHighAccuracy: false, timeout: 10000 },
    )
  }

  const resolveCityLocation = async () => {
    const cityName = profile.location.label.trim()
    if (!cityName) return
    setCityResolving(true)
    setError(null)
    try {
      const data = await jarvisSettingsApi.resolveCityLocation({ city_name: cityName, browser_timezone: browserTimezone })
      const { weather, ...location } = data
      setWeatherPreview(weather ?? null)
      await saveProfile({
        ...profile,
        location: { ...profile.location, ...location },
      })
    } catch (e) {
      setError(`城市位置解析失败: ${String(e)}`)
    } finally {
      setCityResolving(false)
    }
  }

  const addTag = (field: 'diet_restrictions' | 'interests', value: string) => {
    const trimmed = value.trim()
    if (!trimmed) return
    setProfile((p) => {
      if (p[field].includes(trimmed)) return p
      return { ...p, [field]: [...p[field], trimmed] }
    })
  }

  const removeTag = (field: 'diet_restrictions' | 'interests', value: string) => {
    setProfile((p) => ({ ...p, [field]: p[field].filter((v) => v !== value) }))
  }

  const onTagKey = (
    field: 'diet_restrictions' | 'interests',
    input: string,
    setInput: (s: string) => void,
  ) => (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      addTag(field, input)
      setInput('')
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-muted text-sm p-8">
        <Loader2 size={16} className="animate-spin" /> 加载个人资料...
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">个人资料</h1>
          <p className="text-sm text-muted mt-1">这些信息会作为画像前缀传给各位 agent,让他们更了解你。</p>
        </div>
        <div className="flex items-center gap-3">
          {savedAt && (
            <span className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-green-500/15 text-green-400 text-xs font-medium">
              <Check size={12} /> 已保存
            </span>
          )}
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-1.5 rounded-lg bg-primary-500 text-white text-xs font-medium hover:bg-primary-600 transition-colors disabled:opacity-50 flex items-center gap-1.5"
          >
            {saving && <Loader2 size={12} className="animate-spin" />}
            保存
          </button>
        </div>
      </div>

      {error && (
        <div className="px-3 py-2 rounded-md bg-red-500/10 border border-red-500/30 text-red-400 text-xs">
          {error}
        </div>
      )}

      {/* Identity */}
      <section className="surface-card p-5 space-y-4 border border-surface-tertiary">
        <h2 className="text-sm font-medium text-foreground">基本信息</h2>
        <div className="grid grid-cols-2 gap-4">
          <label className="block">
            <span className="text-xs font-medium text-muted">称呼 (name)</span>
            <input
              type="text"
              value={profile.name}
              onChange={(e) => setProfile({ ...profile, name: e.target.value })}
              placeholder="e.g. Motoki"
              className="mt-1.5 w-full px-3 py-2 rounded-lg bg-surface-secondary text-sm text-foreground border border-white/5 focus:border-primary-500/50 outline-none transition-all"
            />
          </label>
          <label className="block">
            <span className="text-xs font-medium text-muted">代词 (pronouns)</span>
            <input
              type="text"
              value={profile.pronouns}
              onChange={(e) => setProfile({ ...profile, pronouns: e.target.value })}
              placeholder="e.g. he/him, she/her, they/them"
              className="mt-1.5 w-full px-3 py-2 rounded-lg bg-surface-secondary text-sm text-foreground border border-white/5 focus:border-primary-500/50 outline-none transition-all"
            />
          </label>
        </div>
        <label className="block">
          <span className="text-xs font-medium text-muted">职业 (occupation)</span>
          <input
            type="text"
            value={profile.occupation}
            onChange={(e) => setProfile({ ...profile, occupation: e.target.value })}
            placeholder="e.g. Software Engineer"
            className="mt-1.5 w-full px-3 py-2 rounded-lg bg-surface-secondary text-sm text-foreground border border-white/5 focus:border-primary-500/50 outline-none transition-all"
          />
        </label>
      </section>

      {/* Location */}
      <section className="surface-card p-5 space-y-4 border border-surface-tertiary">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium text-foreground">位置</h2>
          <button
            onClick={useBrowserLocation}
            disabled={geoBusy}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-primary-500/20 text-primary-400 text-xs font-medium hover:bg-primary-500/30 transition-colors disabled:opacity-50"
          >
            {geoBusy ? <Loader2 size={12} className="animate-spin" /> : <MapPin size={12} />}
            使用浏览器定位
          </button>
        </div>
        <label className="block">
          <span className="text-xs font-medium text-muted">位置标签 (label)</span>
          <input
            type="text"
            value={profile.location.label}
            onChange={(e) =>
              setProfile({ ...profile, location: { ...profile.location, label: e.target.value } })
            }
            onBlur={resolveCityLocation}
            placeholder="Nanjing / Shanghai / New York"
            className="mt-1.5 w-full px-3 py-2 rounded-lg bg-surface-secondary text-sm text-foreground border border-white/5 focus:border-primary-500/50 outline-none transition-all"
          />
          <div className="mt-2 flex items-center justify-between gap-3">
            <p className="text-[10px] text-muted">输入城市名后点击解析，系统会保存该城市默认经纬度。</p>
            <button
              type="button"
              disabled={cityResolving}
              className="text-[10px] text-primary-400 hover:underline disabled:opacity-50"
              onClick={resolveCityLocation}
            >
              {cityResolving ? 'Resolving...' : '解析并保存'}
            </button>
          </div>
        </label>
        <label className="block">
          <div className="flex items-center justify-between gap-3">
            <span className="text-xs font-medium text-muted">Timezone (IANA)</span>
            <button
              type="button"
              className="text-[10px] text-primary-400 hover:underline"
              onClick={() =>
                setProfile({ ...profile, location: { ...profile.location, timezone: browserTimezone, timezone_source: 'manual' } })
              }
            >
              Use browser timezone
            </button>
          </div>
          <input
            type="text"
            value={profile.location.timezone}
            onChange={(e) =>
              setProfile({ ...profile, location: { ...profile.location, timezone: e.target.value, timezone_source: 'manual' } })
            }
            placeholder="Asia/Shanghai"
            className="mt-1.5 w-full px-3 py-2 rounded-lg bg-surface-secondary text-sm text-foreground border border-white/5 focus:border-primary-500/50 outline-none transition-all"
          />
          <p className="mt-1 text-[10px] text-muted">Browser detected: {browserTimezone}</p>
        </label>
        <div className="rounded-xl border border-surface-tertiary bg-surface-secondary/60 p-3 text-xs text-muted">
          <div className="font-medium text-foreground mb-1">当前位置预览</div>
          <div>城市：{profile.location.label || '未设置'}</div>
          <div>时区：{profile.location.timezone || browserTimezone}</div>
          {locationHint ? <div className="text-amber-500">{locationHint}</div> : null}
          {weatherPreview ? (
            weatherPreview.error ? (
              <div title={weatherPreview.error}>天气：获取失败</div>
            ) : (
              <div>
                天气：{weatherPreview.temperature_c !== undefined ? `${weatherPreview.temperature_c.toFixed(0)}°C` : '未知'}
                {weatherPreview.wind_kmh !== undefined ? ` · 风 ${weatherPreview.wind_kmh.toFixed(0)}km/h` : ''}
              </div>
            )
          ) : (
            <div>天气：定位或解析城市后显示</div>
          )}
        </div>
        <div className="grid grid-cols-2 gap-4">
          <label className="block">
            <span className="text-xs font-medium text-muted">Latitude</span>
            <input
              type="number"
              step="0.0001"
              value={profile.location.lat}
              onChange={(e) =>
                setProfile({
                  ...profile,
                  location: { ...profile.location, lat: parseFloat(e.target.value) || 0 },
                })
              }
              className="mt-1.5 w-full px-3 py-2 rounded-lg bg-surface-secondary text-sm text-foreground border border-white/5 focus:border-primary-500/50 outline-none transition-all"
            />
          </label>
          <label className="block">
            <span className="text-xs font-medium text-muted">Longitude</span>
            <input
              type="number"
              step="0.0001"
              value={profile.location.lng}
              onChange={(e) =>
                setProfile({
                  ...profile,
                  location: { ...profile.location, lng: parseFloat(e.target.value) || 0 },
                })
              }
              className="mt-1.5 w-full px-3 py-2 rounded-lg bg-surface-secondary text-sm text-foreground border border-white/5 focus:border-primary-500/50 outline-none transition-all"
            />
          </label>
        </div>
      </section>

      {/* Sleep */}
      <section className="surface-card p-5 space-y-4 border border-surface-tertiary">
        <h2 className="text-sm font-medium text-foreground">作息</h2>
        <div className="grid grid-cols-2 gap-4">
          <label className="block">
            <span className="text-xs font-medium text-muted">就寝时间 (bedtime)</span>
            <input
              type="time"
              value={profile.sleep_schedule.bedtime}
              onChange={(e) =>
                setProfile({
                  ...profile,
                  sleep_schedule: { ...profile.sleep_schedule, bedtime: e.target.value },
                })
              }
              className="mt-1.5 w-full px-3 py-2 rounded-lg bg-surface-secondary text-sm text-foreground border border-white/5 focus:border-primary-500/50 outline-none transition-all"
            />
          </label>
          <label className="block">
            <span className="text-xs font-medium text-muted">起床时间 (wake)</span>
            <input
              type="time"
              value={profile.sleep_schedule.wake}
              onChange={(e) =>
                setProfile({
                  ...profile,
                  sleep_schedule: { ...profile.sleep_schedule, wake: e.target.value },
                })
              }
              className="mt-1.5 w-full px-3 py-2 rounded-lg bg-surface-secondary text-sm text-foreground border border-white/5 focus:border-primary-500/50 outline-none transition-all"
            />
          </label>
        </div>
      </section>

      {/* Diet */}
      <section className="surface-card p-5 space-y-3 border border-surface-tertiary">
        <h2 className="text-sm font-medium text-foreground">饮食偏好 (diet_restrictions)</h2>
        <div className="flex flex-wrap gap-2">
          {profile.diet_restrictions.map((tag) => (
            <span
              key={tag}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-primary-500/15 text-primary-400 text-xs font-medium"
            >
              {tag}
              <button
                onClick={() => removeTag('diet_restrictions', tag)}
                className="hover:text-red-400 transition-colors"
                aria-label={`remove ${tag}`}
              >
                <X size={10} />
              </button>
            </span>
          ))}
        </div>
        <input
          type="text"
          value={dietInput}
          onChange={(e) => setDietInput(e.target.value)}
          onKeyDown={onTagKey('diet_restrictions', dietInput, setDietInput)}
          placeholder="输入后按回车添加 (e.g. vegetarian, no-gluten)"
          className="w-full px-3 py-2 rounded-lg bg-surface-secondary text-sm text-foreground border border-white/5 focus:border-primary-500/50 outline-none transition-all"
        />
      </section>

      {/* Interests */}
      <section className="surface-card p-5 space-y-3 border border-surface-tertiary">
        <h2 className="text-sm font-medium text-foreground">兴趣爱好 (interests)</h2>
        <div className="flex flex-wrap gap-2">
          {profile.interests.map((tag) => (
            <span
              key={tag}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-primary-500/15 text-primary-400 text-xs font-medium"
            >
              {tag}
              <button
                onClick={() => removeTag('interests', tag)}
                className="hover:text-red-400 transition-colors"
                aria-label={`remove ${tag}`}
              >
                <X size={10} />
              </button>
            </span>
          ))}
        </div>
        <input
          type="text"
          value={interestInput}
          onChange={(e) => setInterestInput(e.target.value)}
          onKeyDown={onTagKey('interests', interestInput, setInterestInput)}
          placeholder="输入后按回车添加 (e.g. hiking, photography)"
          className="w-full px-3 py-2 rounded-lg bg-surface-secondary text-sm text-foreground border border-white/5 focus:border-primary-500/50 outline-none transition-all"
        />
      </section>
    </div>
  )
}

export default SettingsProfile
