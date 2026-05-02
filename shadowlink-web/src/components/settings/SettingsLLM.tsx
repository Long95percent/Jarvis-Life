/**
 * SettingsLLM — LLM provider management (extracted from SettingsPage).
 *
 * Talks directly to the Python AI service (/v1/settings/*) via useSettingsStore.
 * Provider configs are persisted server-side in data/llm_providers.json.
 */

import { useEffect, useState } from 'react'
import {
  Check,
  ChevronDown,
  ChevronUp,
  Plus,
  Server,
  MapPin,
  Trash2,
  Zap,
} from 'lucide-react'
import { useSettingsStore } from '@/stores'
import type { LLMConfig } from '@/types/agent'

export function SettingsLLM() {
  const language = useSettingsStore((s) => s.language)
  const setLanguage = useSettingsStore((s) => s.setLanguage)

  const activeLlmId = useSettingsStore((s) => s.activeLlmId)
  const backgroundLlmId = useSettingsStore((s) => s.backgroundLlmId)
  const llmConfigs = useSettingsStore((s) => s.llmConfigs)
  const loadingLLM = useSettingsStore((s) => s.loadingLLM)
  const lastError = useSettingsStore((s) => s.lastError)
  const loadLLMConfigs = useSettingsStore((s) => s.loadLLMConfigs)
  const addLLMConfig = useSettingsStore((s) => s.addLLMConfig)
  const updateLLMConfig = useSettingsStore((s) => s.updateLLMConfig)
  const removeLLMConfig = useSettingsStore((s) => s.removeLLMConfig)
  const setActiveLlmId = useSettingsStore((s) => s.setActiveLlmId)
  const setBackgroundLlmId = useSettingsStore((s) => s.setBackgroundLlmId)
  const externalApiKeys = useSettingsStore((s) => s.externalApiKeys)
  const loadExternalApiKeys = useSettingsStore((s) => s.loadExternalApiKeys)
  const saveExternalApiKey = useSettingsStore((s) => s.saveExternalApiKey)
  const deleteExternalApiKey = useSettingsStore((s) => s.deleteExternalApiKey)
  const amapKey = externalApiKeys.find((item) => item.id === 'amap')

  // Load providers from backend on mount
  useEffect(() => {
    loadLLMConfigs()
    loadExternalApiKeys()
  }, [loadLLMConfigs, loadExternalApiKeys])

  // Currently editing config
  const [editingId, setEditingId] = useState<string | null>(null)

  // Local state for the config being edited
  const [form, setForm] = useState<LLMConfig | null>(null)
  const [amapApiKey, setAmapApiKey] = useState('')
  const [apiKeyMessage, setApiKeyMessage] = useState<string | null>(null)

  // When a config is selected to edit
  const startEdit = (id: string) => {
    const target = llmConfigs.find(c => c.id === id)
    if (target) {
      setForm({ ...target })
      setEditingId(id)
    }
  }

  // Add new blank config — properly await backend so we use the
  // server-assigned id (backend ignores the tempid we send).
  const handleAddNew = async () => {
    const draft: LLMConfig = {
      id: '',  // backend will assign
      name: 'New Provider',
      baseUrl: 'https://api.openai.com/v1',
      model: 'gpt-4o',
      apiKey: '',
      temperature: 0.7,
      maxTokens: 4096,
    }
    try {
      const realId = await addLLMConfig(draft)
      // Enter edit mode on the backend-created config (it was auto-activated too).
      setForm({ ...draft, id: realId })
      setEditingId(realId)
    } catch {
      // addLLMConfig already sets lastError; no-op here
    }
  }

  // Update local form state
  const patch = (key: keyof LLMConfig, value: string | number) => {
    if (!form) return
    setForm({ ...form, [key]: value })
  }

  // Save changes to store
  const handleSave = () => {
    if (form && editingId) {
      updateLLMConfig(editingId, form)
      setEditingId(null)
      setForm(null)
    }
  }

  const handleCancel = () => {
    setEditingId(null)
    setForm(null)
  }

  // Delete config
  const handleDelete = (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (confirm('Are you sure you want to completely delete this API Key and config?')) {
      removeLLMConfig(id)
      if (editingId === id) {
        setEditingId(null)
        setForm(null)
      }
    }
  }

  const handleSaveAmapKey = async () => {
    const value = amapApiKey.trim()
    if (!value) {
      setApiKeyMessage('请输入高德地图 API Key')
      return
    }
    await saveExternalApiKey('amap', value)
    setAmapApiKey('')
    setApiKeyMessage('高德地图 API Key 已保存，本地时间/定位模块会立即优先使用它。')
  }

  const handleDeleteAmapKey = async () => {
    if (!confirm('确定删除已保存的高德地图 API Key？删除后后端本地存储也会清除。')) return
    await deleteExternalApiKey('amap')
    setAmapApiKey('')
    setApiKeyMessage('高德地图 API Key 已删除。')
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-xl font-semibold text-foreground">AI 模型</h1>
        <p className="text-sm text-muted mt-1">Configure AI providers, models, and preferences</p>
      </div>

      {lastError && (
        <div className="px-3 py-2 rounded-md bg-red-500/10 border border-red-500/30 text-red-400 text-xs">
          {lastError}
        </div>
      )}

      {loadingLLM && llmConfigs.length === 0 && (
        <div className="px-3 py-2 text-xs text-muted">加载 LLM 配置中...</div>
      )}

      {/* LLM Providers List */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-medium text-foreground">LLM Providers</h2>
            <p className="text-xs text-muted mt-0.5">
              Add multiple API keys and select the active AI model provider.
            </p>
          </div>
          <button
            onClick={handleAddNew}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary-500/20 text-primary-400 text-xs font-medium hover:bg-primary-500/30 transition-colors"
          >
            <Plus size={14} />
            Add Custom Provider
          </button>
        </div>

        <div className="space-y-2">
          {llmConfigs.map((config) => {
            const isActive = config.id === activeLlmId
            const isEditing = config.id === editingId

            return (
              <div
                key={config.id}
                className={`surface-card border transition-all ${
                  isActive
                    ? 'border-primary-500/40 ring-1 ring-primary-500/20'
                    : 'border-white/5 hover:border-white/10 cursor-pointer'
                }`}
                onClick={() => !isEditing && setActiveLlmId(config.id)}
              >
                {/* Header Row */}
                <div className="flex items-center justify-between px-4 py-3">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold ${
                      isActive ? 'bg-primary-500/20 text-primary-400' : 'bg-surface-secondary text-muted'
                    }`}>
                      {isActive ? <Zap size={14} /> : <Server size={14} />}
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-foreground truncate">
                          {config.name || 'Unnamed Provider'}
                        </span>
                        {isActive && (
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-primary-500/20 text-primary-400">
                            ACTIVE
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-muted truncate">
                        {config.model} &middot; {config.baseUrl}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5">
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        isEditing ? handleCancel() : startEdit(config.id)
                      }}
                      className="p-1.5 rounded-md text-muted hover:text-foreground hover:bg-white/5 transition-colors"
                    >
                      {isEditing ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </button>
                    {llmConfigs.length > 1 && (
                      <button
                        onClick={(e) => handleDelete(config.id, e)}
                        className="p-1.5 rounded-md text-muted hover:text-red-400 hover:bg-red-500/10 transition-colors"
                      >
                        <Trash2 size={14} />
                      </button>
                    )}
                  </div>
                </div>

                {/* Editor Panel */}
                {isEditing && form && (
                  <div className="border-t border-white/5 px-4 py-4 space-y-4" onClick={e => e.stopPropagation()}>
                    <div className="grid grid-cols-2 gap-4">
                      <label className="block">
                        <span className="text-xs font-medium text-muted">Config Name</span>
                        <input
                          type="text"
                          value={form.name}
                          onChange={(e) => patch('name', e.target.value)}
                          placeholder="e.g. My DeepSeek"
                          className="mt-1.5 w-full px-3 py-2 rounded-lg bg-surface-secondary text-sm text-foreground border border-white/5 focus:border-primary-500/50 outline-none transition-all"
                        />
                      </label>
                      <label className="block">
                        <span className="text-xs font-medium text-muted">Model Name</span>
                        <input
                          type="text"
                          value={form.model}
                          onChange={(e) => patch('model', e.target.value)}
                          placeholder="gpt-4o"
                          className="mt-1.5 w-full px-3 py-2 rounded-lg bg-surface-secondary text-sm text-foreground border border-white/5 focus:border-primary-500/50 outline-none transition-all"
                        />
                      </label>
                    </div>

                    <label className="block">
                      <span className="text-xs font-medium text-muted">Base URL</span>
                      <input
                        type="text"
                        value={form.baseUrl}
                        onChange={(e) => patch('baseUrl', e.target.value)}
                        placeholder="https://api.openai.com/v1"
                        className="mt-1.5 w-full px-3 py-2 rounded-lg bg-surface-secondary text-sm text-foreground border border-white/5 focus:border-primary-500/50 outline-none transition-all"
                      />
                    </label>

                    <label className="block">
                      <span className="text-xs font-medium text-muted">API Key</span>
                      <input
                        type="password"
                        value={form.apiKey}
                        onChange={(e) => patch('apiKey', e.target.value)}
                        placeholder="sk-... (Leave empty for local models)"
                        className="mt-1.5 w-full px-3 py-2 rounded-lg bg-surface-secondary text-sm text-foreground border border-white/5 focus:border-primary-500/50 outline-none transition-all"
                      />
                    </label>

                    <div className="grid grid-cols-2 gap-4">
                      <label className="block">
                        <span className="text-xs font-medium text-muted">Temperature: {form.temperature}</span>
                        <input
                          type="range"
                          min={0}
                          max={2}
                          step={0.1}
                          value={form.temperature}
                          onChange={(e) => patch('temperature', parseFloat(e.target.value) || 0)}
                          className="mt-2 w-full accent-primary-500"
                        />
                      </label>
                      <label className="block">
                        <span className="text-xs font-medium text-muted">Max Tokens: {form.maxTokens}</span>
                        <input
                          type="range"
                          min={256}
                          max={8192}
                          step={256}
                          value={form.maxTokens}
                          onChange={(e) => patch('maxTokens', parseInt(e.target.value) || 4096)}
                          className="mt-2 w-full accent-primary-500"
                        />
                      </label>
                    </div>

                    <div className="pt-3 border-t border-white/5 mt-4 flex justify-between items-center">
                      <p className="text-xs text-muted flex items-center gap-1.5">
                        <Check size={12} className="text-green-400" />
                        Click Save to apply changes permanently.
                      </p>
                      <button
                        onClick={handleSave}
                        className="px-4 py-1.5 rounded-lg bg-primary-500 text-white text-xs font-medium hover:bg-primary-600 transition-colors"
                      >
                        Save Config
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </section>

      <section className="surface-card p-5 space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-medium text-foreground flex items-center gap-2">
              <MapPin size={15} className="text-primary-400" />
              外部服务 API Key
            </h2>
            <p className="text-xs text-muted mt-0.5">
              管理本地时间、定位和天气模块使用的第三方服务 Key。
            </p>
          </div>
          <span className={`px-2 py-1 rounded text-[11px] ${amapKey?.has_key ? 'bg-green-500/15 text-green-400' : 'bg-amber-500/15 text-amber-400'}`}>
            {amapKey?.has_key ? `已配置 ${amapKey.api_key_masked}` : '未配置'}
          </span>
        </div>

        <label className="block">
          <span className="text-xs font-medium text-muted">高德地图 API Key</span>
          <input
            type="password"
            value={amapApiKey}
            onChange={(e) => setAmapApiKey(e.target.value)}
            placeholder={amapKey?.has_key ? '输入新 Key 可覆盖当前配置' : '请输入高德 Web 服务 Key'}
            className="mt-1.5 w-full px-3 py-2 rounded-lg bg-surface-secondary text-sm text-foreground border border-white/5 focus:border-primary-500/50 outline-none transition-all"
          />
        </label>

        {apiKeyMessage ? <div className="text-xs text-muted">{apiKeyMessage}</div> : null}

        <div className="flex items-center justify-between gap-3 pt-2 border-t border-white/5">
          <p className="text-xs text-muted">
            保存后会写入后端本地存储；删除会同步清除后端保存的 Key。
          </p>
          <div className="flex items-center gap-2">
            {amapKey?.has_key ? (
              <button
                onClick={handleDeleteAmapKey}
                className="px-3 py-1.5 rounded-lg text-xs text-red-400 bg-red-500/10 hover:bg-red-500/20 transition-colors"
              >
                删除
              </button>
            ) : null}
            <button
              onClick={handleSaveAmapKey}
              className="px-4 py-1.5 rounded-lg bg-primary-500 text-white text-xs font-medium hover:bg-primary-600 transition-colors"
            >
              保存 Key
            </button>
          </div>
        </div>
      </section>

      <section className="surface-card p-5 space-y-4">
        <div>
          <h2 className="text-sm font-medium text-foreground">后台旁路模型</h2>
          <p className="text-xs text-muted mt-0.5">
            长期记忆提取和偏好学习使用这里选择的小模型，私聊、圆桌和多 Agent 回复仍使用 ACTIVE 主模型。
          </p>
        </div>
        <label className="block">
          <span className="text-xs text-muted">Sidecar Provider</span>
          <select
            value={backgroundLlmId || activeLlmId}
            onChange={(e) => setBackgroundLlmId(e.target.value)}
            className="mt-1.5 w-full px-3 py-2 rounded-lg bg-surface-secondary text-sm text-foreground border border-white/5 focus:border-primary-500/50 outline-none"
          >
            {llmConfigs.map((config) => (
              <option key={config.id} value={config.id}>
                {config.name} · {config.model}
              </option>
            ))}
          </select>
        </label>
        <div className="text-xs text-muted">
          当前后台模型：
          <span className="ml-1 text-foreground">
            {(llmConfigs.find((item) => item.id === (backgroundLlmId || activeLlmId))?.model) || '未配置'}
          </span>
        </div>
      </section>

      {/* Preferences */}
      <section className="surface-card p-5 space-y-4">
        <h2 className="text-sm font-medium text-foreground">Preferences</h2>
        <label className="block">
          <span className="text-xs text-muted">Language</span>
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="mt-1 w-full px-3 py-2 rounded-lg bg-surface-secondary text-sm text-foreground border border-white/5 focus:border-primary-500/50 outline-none"
          >
            <option value="zh-CN">中文</option>
            <option value="en">English</option>
          </select>
        </label>
      </section>

      {/* Version info */}
      <div className="text-center text-xs text-muted pb-4">
        ShadowLink AI Platform v3.0
      </div>
    </div>
  )
}

export default SettingsLLM
