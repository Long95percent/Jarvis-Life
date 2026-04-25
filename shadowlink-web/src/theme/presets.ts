/** Theme preset registry — maps mode IDs to ambient themes */

import type { AmbientTheme } from '@/types'
import {
  generalTheme,
  codeDevTheme,
  paperReadingTheme,
  creativeWritingTheme,
  dataAnalysisTheme,
  projectManagementTheme,
} from './themes'

/** All built-in theme presets keyed by mode ID */
const presetRegistry = new Map<string, AmbientTheme>([
  ['general', generalTheme],
  ['code-dev', codeDevTheme],
  ['paper-reading', paperReadingTheme],
  ['creative-writing', creativeWritingTheme],
  ['data-analysis', dataAnalysisTheme],
  ['project-management', projectManagementTheme],
])

export function getPresetTheme(modeId: string): AmbientTheme {
  return presetRegistry.get(modeId) ?? generalTheme
}

export function getAllPresets(): AmbientTheme[] {
  return Array.from(presetRegistry.values())
}

export function getPresetIds(): string[] {
  return Array.from(presetRegistry.keys())
}

export function registerPreset(modeId: string, theme: AmbientTheme): void {
  presetRegistry.set(modeId, theme)
}

export { presetRegistry }
