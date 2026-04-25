/**
 * AmbientProvider — initializes the ambient engine on mount and syncs mode changes.
 * Wrap the entire app with this component.
 */

import { useEffect, type ReactNode } from 'react'
import { useAmbientStore, getBuiltinModes } from '@/stores'
import { getAmbientEngine } from '@/theme'
import { AmbientBackground } from './AmbientBackground'

interface AmbientProviderProps {
  children: ReactNode
}

export function AmbientProvider({ children }: AmbientProviderProps) {
  const activeModeId = useAmbientStore((s) => s.activeModeId)
  const setModes = useAmbientStore((s) => s.setModes)

  // Initialize engine and apply default theme on mount
  useEffect(() => {
    setModes(getBuiltinModes())
    const engine = getAmbientEngine()
    engine.applyTheme(activeModeId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <>
      <AmbientBackground />
      <div className="relative z-10 h-screen w-screen">
        {children}
      </div>
    </>
  )
}
