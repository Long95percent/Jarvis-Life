import type { AmbientTheme } from '@/types'

/** Data analysis theme — crisp, analytical, chart-friendly color palette */
export const dataAnalysisTheme: AmbientTheme = {
  id: 'data-analysis',
  name: '恢复静养',
  icon: 'Leaf',
  description: 'Mira 主导的压力疏解模式,柔和绿色,放慢节奏',
  colors: {
    primary: '#10B981',
    primaryLight: '#34D399',
    primaryDark: '#059669',
    background: '#0c1222',
    surface: '#131c2e',
    surfaceSecondary: '#1c2740',
    surfaceTertiary: '#243352',
    text: '#e0f2fe',
    textMuted: '#7dd3fc',
    accent: '#A7F3D0',
    gradient: ['#10B981', '#6EE7B7'] as [string, string],
  },
  typography: {
    fontFamily: 'Inter',
    codeFont: 'JetBrains Mono',
  },
  ambient: {
    type: 'particles',
    backgroundEffect: 'static',
    transitionDuration: 500,
  },
  layout: {
    sidebarWidth: 300,
    panelRatio: [5, 5] as [number, number],
  },
}
