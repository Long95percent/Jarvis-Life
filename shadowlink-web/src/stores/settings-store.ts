/**
 * Settings store — LLM provider management, synced with backend.
 *
 * IMPORTANT: This store talks to /v1/settings/providers/* on the Python
 * service. Previously it was a pure-local zustand+localStorage store, which
 * meant UI edits never reached the backend — the running LLM client kept
 * using whatever was in .env at startup. This version:
 *   - fetches providers from the backend on first read
 *   - proxies every CRUD action to the backend
 *   - only caches UI preferences (language, sidebar) locally
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { LLMConfig } from '@/types/agent'

// Backend schema (snake_case)
interface ServerProvider {
  id: string
  name: string
  base_url: string
  model: string
  api_key: string
  temperature?: number
  max_tokens?: number
}

interface ServerProvidersResponse {
  providers: ServerProvider[]
  active_id: string | null
  background_id?: string | null
}

function toClient(p: ServerProvider): LLMConfig {
  return {
    id: p.id,
    name: p.name,
    baseUrl: p.base_url,
    model: p.model,
    apiKey: p.api_key ?? '',
    temperature: p.temperature ?? 0.7,
    maxTokens: p.max_tokens ?? 4096,
  }
}

function toServer(c: LLMConfig): Partial<ServerProvider> {
  return {
    id: c.id,
    name: c.name,
    base_url: c.baseUrl,
    model: c.model,
    api_key: c.apiKey,
    temperature: c.temperature,
    max_tokens: c.maxTokens,
  }
}

interface SettingsState {
  activeLlmId: string
  backgroundLlmId: string
  llmConfigs: LLMConfig[]
  loadingLLM: boolean
  lastError: string | null

  language: string
  sidebarCollapsed: boolean

  // LLM actions (all async, all talk to backend)
  loadLLMConfigs: () => Promise<void>
  addLLMConfig: (config: LLMConfig) => Promise<string>  // returns backend-assigned id
  updateLLMConfig: (id: string, patch: Partial<LLMConfig>) => Promise<void>
  removeLLMConfig: (id: string) => Promise<void>
  setActiveLlmId: (id: string) => Promise<void>
  setBackgroundLlmId: (id: string) => Promise<void>

  // Local-only preferences
  setLanguage: (lang: string) => void
  toggleSidebar: () => void
}

/** Result envelope used by /v1/settings/* endpoints. */
interface ResultEnvelope<T> {
  success: boolean
  code: number
  message: string
  data: T | null
  timestamp?: number
}

/** Fetch + unwrap `{success, data}` envelope used by the Python service. */
async function fetchResult<T>(url: string, init?: RequestInit, options?: { allowEmptyData?: boolean }): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!res.ok) {
    let detail = ''
    try {
      const body = await res.text()
      detail = ` — ${body.slice(0, 200)}`
    } catch {}
    throw new Error(`HTTP ${res.status}${detail}`)
  }
  const envelope = (await res.json()) as ResultEnvelope<T>
  if (!envelope.success) {
    throw new Error(envelope.message || 'Unknown backend error')
  }
  if ((envelope.data === null || envelope.data === undefined) && !options?.allowEmptyData) {
    throw new Error('Backend returned empty data')
  }
  return envelope.data as T
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set, get) => ({
      activeLlmId: '',
      backgroundLlmId: '',
      llmConfigs: [],
      loadingLLM: false,
      lastError: null,

      language: 'zh-CN',
      sidebarCollapsed: false,

      loadLLMConfigs: async () => {
        set({ loadingLLM: true, lastError: null })
        try {
          const data = await fetchResult<ServerProvidersResponse>(
            '/v1/settings/providers',
          )
          set({
            llmConfigs: data.providers.map(toClient),
            activeLlmId: data.active_id ?? '',
            backgroundLlmId: data.background_id ?? '',
            loadingLLM: false,
          })
        } catch (err) {
          set({ loadingLLM: false, lastError: String(err) })
        }
      },

      addLLMConfig: async (config) => {
        try {
          // Backend assigns its own id (ignores frontend-generated tempid)
          const created = await fetchResult<ServerProvider>(
            '/v1/settings/providers',
            {
              method: 'POST',
              body: JSON.stringify(toServer(config)),
            },
          )
          // Reload + activate the newly-created one so the running
          // LLM client actually picks up the new credentials.
          await get().loadLLMConfigs()
          try {
            await get().setActiveLlmId(created.id)
          } catch (activateErr) {
            // Non-fatal: the config is saved; user can click ⚡ manually
            set({ lastError: `Saved but activation failed: ${activateErr}` })
          }
          return created.id
        } catch (err) {
          set({ lastError: String(err) })
          throw err
        }
      },

      updateLLMConfig: async (id, patch) => {
        const current = get().llmConfigs.find((c) => c.id === id)
        if (!current) {
          set({ lastError: `Config ${id} not found` })
          return
        }
        const merged: LLMConfig = { ...current, ...patch }
        try {
          await fetchResult(`/v1/settings/providers/${id}`, {
            method: 'PUT',
            body: JSON.stringify(toServer(merged)),
          })
          await get().loadLLMConfigs()
          // If the user just edited the ACTIVE provider, re-activate so
          // the running client picks up the new key/model/etc.
          if (get().activeLlmId === id) {
            try {
              await get().setActiveLlmId(id)
            } catch {}
          }
        } catch (err) {
          set({ lastError: String(err) })
          throw err
        }
      },

      removeLLMConfig: async (id) => {
        try {
          await fetchResult<void>(
            `/v1/settings/providers/${id}`,
            { method: 'DELETE' },
            { allowEmptyData: true },
          )
          await get().loadLLMConfigs()
        } catch (err) {
          const message = String(err)
          if (message.includes('not found')) {
            await get().loadLLMConfigs()
            set({ lastError: null })
            return
          }
          set({ lastError: String(err) })
          throw err
        }
      },

      setActiveLlmId: async (id) => {
        try {
          await fetchResult(`/v1/settings/providers/${id}/activate`, {
            method: 'POST',
          })
          await get().loadLLMConfigs()
        } catch (err) {
          set({ lastError: String(err) })
          throw err
        }
      },

      setBackgroundLlmId: async (id) => {
        try {
          await fetchResult(`/v1/settings/providers/${id}/activate-background`, {
            method: 'POST',
          })
          await get().loadLLMConfigs()
        } catch (err) {
          set({ lastError: String(err) })
          throw err
        }
      },

      setLanguage: (language) => set({ language }),
      toggleSidebar: () =>
        set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
    }),
    {
      name: 'shadowlink-settings',
      // Only persist UI preferences locally. LLM configs are authoritative on the backend.
      partialize: (s) => ({
        language: s.language,
        sidebarCollapsed: s.sidebarCollapsed,
      }),
    },
  ),
)
