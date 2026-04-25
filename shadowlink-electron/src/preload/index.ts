/**
 * ShadowLink Electron — Preload script
 *
 * Exposes safe APIs to the renderer process via contextBridge.
 * All IPC calls go through main process handlers.
 */

import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('shadowlink', {
  // ── System Info ──
  platform: process.platform,
  isElectron: true,

  // ── Clipboard ──
  getClipboard: (): Promise<string> => ipcRenderer.invoke('get-clipboard'),
  setClipboard: (text: string): Promise<boolean> => ipcRenderer.invoke('set-clipboard', text),
  getSelectedText: (): Promise<string> => ipcRenderer.invoke('get-selected-text'),

  // ── System ──
  getSystemInfo: (): Promise<Record<string, string>> => ipcRenderer.invoke('get-system-info'),
  openExternal: (url: string): Promise<boolean> => ipcRenderer.invoke('open-external', url),

  // ── Window Controls (for frameless quick-assist) ──
  closeWindow: (): Promise<void> => ipcRenderer.invoke('window-close'),
  minimizeWindow: (): Promise<void> => ipcRenderer.invoke('window-minimize'),

  // ── Event listeners ──
  onClipboardContent: (callback: (text: string) => void) => {
    ipcRenderer.on('clipboard-content', (_event, text: string) => callback(text))
  },
  onScreenshotCaptured: (callback: (base64: string) => void) => {
    ipcRenderer.on('screenshot-captured', (_event, base64: string) => callback(base64))
  },

  // ── Cleanup ──
  removeAllListeners: (channel: string) => {
    ipcRenderer.removeAllListeners(channel)
  },
})

// Type declaration for renderer
declare global {
  interface Window {
    shadowlink: {
      platform: string
      isElectron: boolean
      getClipboard: () => Promise<string>
      setClipboard: (text: string) => Promise<boolean>
      getSelectedText: () => Promise<string>
      getSystemInfo: () => Promise<Record<string, string>>
      openExternal: (url: string) => Promise<boolean>
      closeWindow: () => Promise<void>
      minimizeWindow: () => Promise<void>
      onClipboardContent: (callback: (text: string) => void) => void
      onScreenshotCaptured: (callback: (base64: string) => void) => void
      removeAllListeners: (channel: string) => void
    }
  }
}
