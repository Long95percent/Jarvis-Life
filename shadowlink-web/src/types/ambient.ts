/** Ambient theme system — full-stack context switching per work mode */

export type AnimationType = 'none' | 'particles' | 'matrix_rain' | 'aurora' | 'fireflies'
export type BackgroundEffect = 'static' | 'gradient_shift' | 'mesh_gradient'

export interface AmbientColors {
  primary: string
  primaryLight: string
  primaryDark: string
  background: string
  surface: string
  surfaceSecondary: string
  surfaceTertiary: string
  text: string
  textMuted: string
  accent: string
  gradient: [string, string]
}

export interface AmbientTypography {
  fontFamily: string
  codeFont: string
}

export interface AmbientAnimation {
  type: AnimationType
  backgroundEffect: BackgroundEffect
  transitionDuration: number
}

export interface AmbientLayout {
  sidebarWidth: number
  panelRatio: [number, number] // [agent panel, dialog panel]
}

export interface AmbientTheme {
  id: string
  name: string
  icon: string
  description: string
  colors: AmbientColors
  typography: AmbientTypography
  ambient: AmbientAnimation
  layout: AmbientLayout
}

export interface WorkModeResource {
  id: string
  type: 'folder' | 'file' | 'url' | 'app' | 'script'
  value: string
  name: string
}

export interface WorkMode {
  modeId: string
  name: string
  description: string
  icon: string
  themeConfig: AmbientTheme
  agentConfig: Record<string, unknown>
  toolsConfig: Record<string, unknown>
  systemPrompt: string
  strategy?: string
  enabledTools?: string[]
  resources: WorkModeResource[]
  isBuiltin: boolean
  sortOrder: number
}
