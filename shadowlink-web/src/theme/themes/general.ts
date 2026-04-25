import type { AmbientTheme } from '@/types'

/** Default general-purpose theme — neutral, balanced, distraction-free */
export const generalTheme: AmbientTheme = {
  id: 'general',
  name: '生活总管',
  icon: 'Crown',
  description: 'Alfred 坐镇的日常总览模式,统筹你一天所有节奏',
  colors: {
    primary: '#6366f1',
    primaryLight: '#818cf8',
    primaryDark: '#4f46e5',
    background: '#0f1117',
    surface: '#1a1b23',
    surfaceSecondary: '#252631',
    surfaceTertiary: '#2f3142',
    text: '#e2e8f0',
    textMuted: '#94a3b8',
    accent: '#a78bfa',
    gradient: ['#6366f1', '#8b5cf6'] as [string, string],
  },
  typography: {
    fontFamily: 'Inter',
    codeFont: 'JetBrains Mono',
  },
  ambient: {
    type: 'particles',
    backgroundEffect: 'gradient_shift',
    transitionDuration: 600,
  },
  layout: {
    sidebarWidth: 280,
    panelRatio: [6, 4] as [number, number],
  },
}
