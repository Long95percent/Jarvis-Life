/**
 * useAmbient — convenience hook for ambient theme operations.
 */

import { useCallback } from 'react'
import { useAmbientStore } from '@/stores'
import { getPresetTheme, getAllPresets } from '@/theme'
import type { AmbientTheme } from '@/types'

export function useAmbient() {
  const activeModeId = useAmbientStore((s) => s.activeModeId)
  const switchMode = useAmbientStore((s) => s.switchMode)
  const isTransitioning = useAmbientStore((s) => s.isTransitioning)

  const currentTheme: AmbientTheme = getPresetTheme(activeModeId)
  const presets = getAllPresets()

  const switchTo = useCallback(
    (modeId: string) => {
      if (modeId !== activeModeId) {
        switchMode(modeId)
      }
    },
    [activeModeId, switchMode],
  )

  return {
    activeModeId,
    currentTheme,
    presets,
    isTransitioning,
    switchTo,
  }
}
