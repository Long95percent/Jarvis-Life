/**
 * ModeSwitcher — dropdown/grid for switching ambient work modes.
 */

import { useState, MouseEvent } from 'react'
import { useAmbientStore } from '@/stores'
import { Settings, Play } from 'lucide-react'
import { ModeSettingsModal } from './ModeSettingsModal'

export function ModeSwitcher() {
  const [open, setOpen] = useState(false)
  const [settingsModeId, setSettingsModeId] = useState<string | null>(null)
  
  const activeModeId = useAmbientStore((s) => s.activeModeId)
  const switchMode = useAmbientStore((s) => s.switchMode)
  const modes = useAmbientStore((s) => s.modes)
  const active = modes.find((m) => m.modeId === activeModeId) ?? modes[0]

  const handleGo = async (e: MouseEvent, modeId: string) => {
    e.stopPropagation()
    const targetMode = modes.find(m => m.modeId === modeId)
    if (!targetMode || !targetMode.resources || targetMode.resources.length === 0) {
      alert('This mode has no resources configured. Click the gear icon to add some.')
      return
    }

    try {
      const res = await fetch('/api/ai/system/open', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ resources: targetMode.resources }),
      })
      const result = await res.json()
      if (!result.success) {
        alert(`Failed to open resources: ${result.message}`)
      }
    } catch (err) {
      alert(`Error connecting to server: ${err}`)
    }
  }

  const handleSettings = (e: MouseEvent, modeId: string) => {
    e.stopPropagation()
    setSettingsModeId(modeId)
    setOpen(false)
  }

  return (
    <>
      <div className="relative">
        <button
          onClick={() => setOpen(!open)}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-surface-secondary hover:bg-surface-tertiary transition-colors text-sm"
        >
          <span className="w-6 h-6 rounded-md ambient-gradient flex items-center justify-center text-white text-[10px] font-bold shrink-0">
            {active?.icon?.charAt(0) || 'M'}
          </span>
          <span className="flex-1 text-left text-foreground truncate">{active?.name || 'Mode'}</span>
          <svg
            width="14" height="14" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" strokeWidth="2"
            className={`text-muted transition-transform ${open ? 'rotate-180' : ''}`}
          >
            <path d="m6 9 6 6 6-6" />
          </svg>
        </button>

        {open && (
          <>
            {/* Backdrop */}
            <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />

            {/* Dropdown */}
            <div className="absolute left-0 right-0 top-full mt-1 z-50 bg-surface border border-surface-tertiary rounded-xl shadow-xl overflow-hidden animate-fade-in">
              {modes.map((mode) => (
                <div
                  key={mode.modeId}
                  onClick={() => {
                    switchMode(mode.modeId)
                    setOpen(false)
                  }}
                  className={`group relative w-full flex items-center gap-3 px-3 py-2.5 text-left hover:bg-surface-secondary transition-colors cursor-pointer
                    ${mode.modeId === activeModeId ? 'bg-surface-secondary' : ''}`}
                >
                  <span className="w-7 h-7 rounded-md ambient-gradient flex items-center justify-center text-white text-xs font-bold shrink-0">
                    {mode.icon.charAt(0)}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm text-foreground truncate">{mode.name}</div>
                    <div className="text-[11px] text-muted truncate pr-16">{mode.description}</div>
                  </div>
                  
                  {/* Hover Actions */}
                  <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={(e) => handleGo(e, mode.modeId)}
                      className="flex items-center gap-1 px-2 py-1 rounded bg-green-500/20 text-green-400 hover:bg-green-500/30 text-xs font-bold transition-colors"
                      title="Open Mode Resources (GO)"
                    >
                      <Play size={12} fill="currentColor" /> GO
                    </button>
                    <button
                      onClick={(e) => handleSettings(e, mode.modeId)}
                      className="p-1.5 rounded text-muted hover:text-foreground hover:bg-surface-tertiary transition-colors"
                      title="Edit Mode Resources"
                    >
                      <Settings size={14} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      {settingsModeId && (
        <ModeSettingsModal 
          modeId={settingsModeId} 
          onClose={() => setSettingsModeId(null)} 
        />
      )}
    </>
  )
}
