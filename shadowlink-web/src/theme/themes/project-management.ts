import type { AmbientTheme } from '@/types'

/** Project management theme — structured, professional, productivity-oriented */
export const projectManagementTheme: AmbientTheme = {
  id: 'project-management',
  name: '活力健康',
  icon: 'Dumbbell',
  description: 'Nora 与 Leo 搭档的健康模式,活力橙红,推动你动起来',
  colors: {
    primary: '#F97316',
    primaryLight: '#FB923C',
    primaryDark: '#EA580C',
    background: '#111318',
    surface: '#1a1c24',
    surfaceSecondary: '#242730',
    surfaceTertiary: '#2e3240',
    text: '#f1f5f9',
    textMuted: '#94a3b8',
    accent: '#FED7AA',
    gradient: ['#F97316', '#FB923C'] as [string, string],
  },
  typography: {
    fontFamily: 'Inter',
    codeFont: 'JetBrains Mono',
  },
  ambient: {
    type: 'none',
    backgroundEffect: 'gradient_shift',
    transitionDuration: 400,
  },
  layout: {
    sidebarWidth: 300,
    panelRatio: [6, 4] as [number, number],
  },
}
