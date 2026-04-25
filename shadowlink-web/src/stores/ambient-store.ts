/**
 * Ambient theme store — drives the entire ambient work mode system.
 * When the active mode changes, the AmbientEngine applies new CSS variables.
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { AmbientTheme, WorkMode, WorkModeResource } from '@/types'
import { getAmbientEngine, getPresetTheme, getAllPresets } from '@/theme'

interface AmbientState {
  /** Current active mode ID */
  activeModeId: string
  /** All available work modes (from server + builtins) */
  modes: WorkMode[]
  /** Whether a theme transition is in progress */
  isTransitioning: boolean

  // Actions
  switchMode: (modeId: string) => void
  setModes: (modes: WorkMode[]) => void
  updateModeResources: (modeId: string, resources: WorkModeResource[]) => void
  updateModeSystemPrompt: (modeId: string, systemPrompt: string) => void
  updateModeStrategy: (modeId: string, strategy: string) => void
  updateModeTools: (modeId: string, tools: string[]) => void
  getCurrentTheme: () => AmbientTheme
}

export const useAmbientStore = create<AmbientState>()(
  persist(
    (set, get) => ({
      activeModeId: 'general',
      modes: getBuiltinModes(),
      isTransitioning: false,

      switchMode: (modeId) => {
        const engine = getAmbientEngine({
          onTransitionEnd: () => set({ isTransitioning: false }),
        })
        set({ activeModeId: modeId, isTransitioning: true })
        engine.applyTheme(modeId)
      },

      setModes: (modes) => set({ modes }),
      
      updateModeResources: (modeId, resources) => set((state) => ({
        modes: state.modes.map((m) => 
          m.modeId === modeId ? { ...m, resources } : m
        )
      })),

      updateModeSystemPrompt: (modeId, systemPrompt) => set((state) => ({
        modes: state.modes.map((m) => 
          m.modeId === modeId ? { ...m, systemPrompt } : m
        )
      })),

      updateModeStrategy: (modeId, strategy) => set((state) => ({
        modes: state.modes.map((m) => 
          m.modeId === modeId ? { ...m, strategy } : m
        )
      })),

      updateModeTools: (modeId, tools) => set((state) => ({
        modes: state.modes.map((m) => 
          m.modeId === modeId ? { ...m, enabledTools: tools } : m
        )
      })),

      getCurrentTheme: () => {
        return getPresetTheme(get().activeModeId)
      },
    }),
    {
      name: 'shadowlink-ambient',
      partialize: (s) => ({
        modes: s.modes.map(m => ({ 
          ...m, 
          resources: m.resources || [], 
          systemPrompt: m.systemPrompt || '',
          strategy: m.strategy,
          enabledTools: m.enabledTools
        })) // Persist mode configurations
      })
    }
  )
)

/** Build default WorkMode entries from built-in presets */
export function getBuiltinModes(): WorkMode[] {
  return getAllPresets().map((theme) => ({
    modeId: theme.id,
    name: theme.name,
    description: theme.description,
    icon: theme.icon,
    themeConfig: theme,
    agentConfig: {},
    toolsConfig: {},
    systemPrompt: '',
    resources: [],
    isBuiltin: true,
    sortOrder: 0,
  }))
}
