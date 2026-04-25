import type { AmbientTheme } from '@/types'

/** Code development theme — matrix-inspired, sharp contrasts, monospace-forward */
export const codeDevTheme: AmbientTheme = {
  id: 'code-dev',
  name: '全速工作',
  icon: 'Zap',
  description: 'Maxwell 带队的高专注模式,代码/分析/决策一气呵成',
  colors: {
    primary: '#10b981',
    primaryLight: '#34d399',
    primaryDark: '#059669',
    background: '#0a0e14',
    surface: '#131820',
    surfaceSecondary: '#1c222d',
    surfaceTertiary: '#262d3a',
    text: '#d4d4d8',
    textMuted: '#71717a',
    accent: '#22d3ee',
    gradient: ['#10b981', '#06b6d4'] as [string, string],
  },
  typography: {
    fontFamily: 'JetBrains Mono',
    codeFont: 'JetBrains Mono',
  },
  ambient: {
    type: 'matrix_rain',
    backgroundEffect: 'static',
    transitionDuration: 400,
  },
  layout: {
    sidebarWidth: 260,
    panelRatio: [5, 5] as [number, number],
  },
}
