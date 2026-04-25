/**
 * AmbientEngine — core runtime for the ambient theme system.
 *
 * Responsibilities:
 * 1. Convert an AmbientTheme into CSS custom properties
 * 2. Apply them to a target element (default: <html>)
 * 3. Orchestrate smooth transitions between themes
 * 4. Expose current theme state for React integration
 */

import type { AmbientTheme } from '@/types'
import type { CSSVariableMap, AmbientEngineConfig, ThemeTransition } from './types'
import { getPresetTheme } from './presets'

/** Convert a hex color to an rgb() triplet string for Tailwind opacity support */
function hexToRGB(hex: string): string {
  const h = hex.replace('#', '')
  const r = parseInt(h.substring(0, 2), 16)
  const g = parseInt(h.substring(2, 4), 16)
  const b = parseInt(h.substring(4, 6), 16)
  return `${r} ${g} ${b}`
}

/** Generate a 10-shade palette from a single base color using HSL manipulation */
function generatePalette(base: string): Record<string, string> {
  const h = base.replace('#', '')
  const r = parseInt(h.substring(0, 2), 16) / 255
  const g = parseInt(h.substring(2, 4), 16) / 255
  const b = parseInt(h.substring(4, 6), 16) / 255

  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  const l = (max + min) / 2
  let s = 0
  let hue = 0

  if (max !== min) {
    const d = max - min
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min)
    switch (max) {
      case r: hue = ((g - b) / d + (g < b ? 6 : 0)) / 6; break
      case g: hue = ((b - r) / d + 2) / 6; break
      case b: hue = ((r - g) / d + 4) / 6; break
    }
  }

  const shades: [string, number][] = [
    ['50', 0.95], ['100', 0.9], ['200', 0.8], ['300', 0.7], ['400', 0.6],
    ['500', 0.5], ['600', 0.4], ['700', 0.3], ['800', 0.2], ['900', 0.1],
  ]

  const result: Record<string, string> = {}
  for (const [shade, lightness] of shades) {
    const a = s * Math.min(lightness, 1 - lightness)
    const f = (n: number) => {
      const k = (n + hue * 12) % 12
      return lightness - a * Math.max(Math.min(k - 3, 9 - k, 1), -1)
    }
    const sr = Math.round(f(0) * 255)
    const sg = Math.round(f(8) * 255)
    const sb = Math.round(f(4) * 255)
    result[shade] = `${sr} ${sg} ${sb}`
  }
  return result
}

/** Build the full CSS variable map from an AmbientTheme */
function buildCSSVariables(theme: AmbientTheme): CSSVariableMap {
  const { colors, typography, ambient, layout } = theme
  const palette = generatePalette(colors.primary)

  const vars: CSSVariableMap = {
    // Primary palette (RGB triplets for Tailwind opacity)
    '--color-primary-50': palette['50'],
    '--color-primary-100': palette['100'],
    '--color-primary-200': palette['200'],
    '--color-primary-300': palette['300'],
    '--color-primary-400': palette['400'],
    '--color-primary-500': palette['500'],
    '--color-primary-600': palette['600'],
    '--color-primary-700': palette['700'],
    '--color-primary-800': palette['800'],
    '--color-primary-900': palette['900'],

    // Semantic surface colors
    '--color-bg': colors.background,
    '--color-surface': colors.surface,
    '--color-surface-secondary': colors.surfaceSecondary,
    '--color-surface-tertiary': colors.surfaceTertiary,
    '--color-text': colors.text,
    '--color-text-muted': colors.textMuted,
    '--color-accent': colors.accent,
    '--color-primary': colors.primary,
    '--color-primary-light': colors.primaryLight,
    '--color-primary-dark': colors.primaryDark,

    // Gradient
    '--gradient-from': colors.gradient[0],
    '--gradient-to': colors.gradient[1],

    // Typography
    '--font-sans': typography.fontFamily,
    '--font-mono': typography.codeFont,

    // Layout
    '--sidebar-width': `${layout.sidebarWidth}px`,
    '--panel-ratio-agent': `${layout.panelRatio[0]}`,
    '--panel-ratio-dialog': `${layout.panelRatio[1]}`,

    // Ambient animation
    '--ambient-transition': `${ambient.transitionDuration}ms`,
    '--ambient-type': ambient.type,
    '--ambient-bg-effect': ambient.backgroundEffect,
  }

  return vars
}

class AmbientEngine {
  private currentThemeId: string | null = null
  private targetElement: HTMLElement
  private enableTransitions: boolean
  private onTransitionEnd?: (themeId: string) => void
  private transition: ThemeTransition | null = null

  constructor(config: AmbientEngineConfig = {}) {
    this.targetElement = config.targetElement ?? document.documentElement
    this.enableTransitions = config.enableTransitions ?? true
    this.onTransitionEnd = config.onTransitionEnd
  }

  /** Get the current active theme ID */
  get activeThemeId(): string | null {
    return this.currentThemeId
  }

  /** Get current transition state (null if idle) */
  get currentTransition(): ThemeTransition | null {
    return this.transition
  }

  /** Apply a theme by mode ID — looks up from the preset registry */
  applyTheme(modeId: string): void {
    const theme = getPresetTheme(modeId)
    this.applyThemeObject(theme)
  }

  /** Apply an arbitrary AmbientTheme object */
  applyThemeObject(theme: AmbientTheme): void {
    const vars = buildCSSVariables(theme)
    const duration = this.enableTransitions ? theme.ambient.transitionDuration : 0

    if (this.enableTransitions && duration > 0) {
      this.transition = {
        from: this.currentThemeId,
        to: theme.id,
        startedAt: Date.now(),
        duration,
      }
      this.targetElement.style.setProperty('transition',
        `background-color ${duration}ms ease, color ${duration}ms ease`)
    }

    // Apply all CSS variables
    for (const [key, value] of Object.entries(vars)) {
      this.targetElement.style.setProperty(key, value)
    }

    // Set data attribute for conditional styling
    this.targetElement.dataset.theme = theme.id
    this.targetElement.dataset.ambientType = theme.ambient.type
    this.targetElement.dataset.bgEffect = theme.ambient.backgroundEffect

    this.currentThemeId = theme.id

    // Clear transition state after duration
    if (this.transition) {
      setTimeout(() => {
        this.transition = null
        this.targetElement.style.removeProperty('transition')
        this.onTransitionEnd?.(theme.id)
      }, duration)
    }
  }

  /** Remove all ambient CSS variables from the target */
  reset(): void {
    const style = this.targetElement.style
    const toRemove: string[] = []
    for (let i = 0; i < style.length; i++) {
      const prop = style[i]
      if (prop.startsWith('--')) {
        toRemove.push(prop)
      }
    }
    toRemove.forEach(prop => style.removeProperty(prop))
    delete this.targetElement.dataset.theme
    delete this.targetElement.dataset.ambientType
    delete this.targetElement.dataset.bgEffect
    this.currentThemeId = null
    this.transition = null
  }
}

/** Singleton instance for the app */
let engineInstance: AmbientEngine | null = null

export function getAmbientEngine(config?: AmbientEngineConfig): AmbientEngine {
  if (!engineInstance) {
    engineInstance = new AmbientEngine(config)
  }
  return engineInstance
}

export { AmbientEngine, buildCSSVariables, hexToRGB, generatePalette }
export type { CSSVariableMap, AmbientEngineConfig, ThemeTransition }
