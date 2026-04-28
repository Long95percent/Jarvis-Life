/**
 * ShadowLink Electron — Main process
 *
 * Features:
 * - Main window loads React app (dev server or production build)
 * - Global hotkey (Alt+Space) toggles a quick-assist popup
 * - System tray icon with context menu
 * - IPC bridge for clipboard, screenshot, and system info
 * - Auto-start services on launch (optional)
 */

import {
  app,
  BrowserWindow,
  clipboard,
  globalShortcut,
  ipcMain,
  Menu,
  nativeImage,
  screen,
  shell,
  Tray,
} from 'electron'
import * as path from 'path'
import { exec } from 'child_process'

const isDev = !app.isPackaged
const FRONTEND_DEV_URL = 'http://localhost:3000'
const FRONTEND_PROD_PATH = path.join(__dirname, '../../shadowlink-web/dist/index.html')
const PRELOAD_PATH = path.join(__dirname, '../preload/index.js')

let mainWindow: BrowserWindow | null = null
let quickAssistWindow: BrowserWindow | null = null
let tray: Tray | null = null

function sendBehaviorLifecycle(type: string): void {
  mainWindow?.webContents.send('jarvis-behavior-lifecycle', {
    type,
    occurredAt: Math.floor(Date.now() / 1000),
  })
}

// ── Main Window ──

function createMainWindow(): BrowserWindow {
  const win = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 900,
    minHeight: 600,
    title: 'ShadowLink AI',
    icon: getIconPath(),
    webPreferences: {
      preload: PRELOAD_PATH,
      contextIsolation: true,
      nodeIntegration: false,
      spellcheck: false,
    },
    show: false,
    backgroundColor: '#0f0f14',
  })

  if (isDev) {
    win.loadURL(FRONTEND_DEV_URL)
    win.webContents.openDevTools({ mode: 'detach' })
  } else {
    win.loadFile(FRONTEND_PROD_PATH)
  }

  win.once('ready-to-show', () => {
    win.show()
    win.focus()
    sendBehaviorLifecycle('app_opened')
  })

  win.on('focus', () => sendBehaviorLifecycle('app_activated'))
  win.on('restore', () => sendBehaviorLifecycle('app_restored'))
  win.on('minimize', () => sendBehaviorLifecycle('app_minimized'))
  win.on('hide', () => sendBehaviorLifecycle('app_minimized'))

  win.on('close', (e) => {
    sendBehaviorLifecycle('app_closed')
    // Minimize to tray instead of quitting
    if (tray) {
      e.preventDefault()
      win.hide()
    }
  })

  return win
}

// ── Quick Assist Popup (Alt+Space) ──

function createQuickAssistWindow(): BrowserWindow {
  const { width: screenW, height: screenH } = screen.getPrimaryDisplay().workAreaSize

  const win = new BrowserWindow({
    width: 600,
    height: 500,
    x: Math.round((screenW - 600) / 2),
    y: Math.round(screenH * 0.2),
    frame: false,
    transparent: true,
    resizable: true,
    skipTaskbar: true,
    alwaysOnTop: true,
    webPreferences: {
      preload: PRELOAD_PATH,
      contextIsolation: true,
      nodeIntegration: false,
    },
    show: false,
    backgroundColor: '#00000000',
  })

  // Load the quick-assist route
  const url = isDev ? `${FRONTEND_DEV_URL}/#/quick-assist` : FRONTEND_PROD_PATH
  if (isDev) {
    win.loadURL(url)
  } else {
    win.loadFile(url)
  }

  win.on('blur', () => {
    win.hide()
  })

  return win
}

function toggleQuickAssist(): void {
  if (!quickAssistWindow) {
    quickAssistWindow = createQuickAssistWindow()
  }

  if (quickAssistWindow.isVisible()) {
    quickAssistWindow.hide()
  } else {
    // Update clipboard content before showing
    const clipText = clipboard.readText()
    quickAssistWindow.webContents.send('clipboard-content', clipText)
    quickAssistWindow.show()
    quickAssistWindow.focus()
  }
}

// ── System Tray ──

function createTray(): void {
  const icon = getIconPath()
  const trayIcon = nativeImage.createFromPath(icon).resize({ width: 16, height: 16 })
  tray = new Tray(trayIcon)
  tray.setToolTip('ShadowLink AI')

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Show ShadowLink',
      click: () => {
        mainWindow?.show()
        mainWindow?.focus()
      },
    },
    {
      label: 'Quick Assist (Alt+Space)',
      click: () => toggleQuickAssist(),
    },
    { type: 'separator' },
    {
      label: 'Open in Browser',
      click: () => shell.openExternal('http://localhost:3000'),
    },
    {
      label: 'API Docs',
      click: () => shell.openExternal('http://localhost:8000/docs'),
    },
    { type: 'separator' },
    {
      label: 'Quit',
      click: () => {
        tray?.destroy()
        tray = null
        app.quit()
      },
    },
  ])

  tray.setContextMenu(contextMenu)

  tray.on('double-click', () => {
    mainWindow?.show()
    mainWindow?.focus()
  })
}

// ── Global Shortcuts ──

function registerGlobalShortcuts(): void {
  // Alt+Space: Toggle quick assist
  globalShortcut.register('Alt+Space', () => {
    toggleQuickAssist()
  })

  // Ctrl+Shift+S: Take screenshot and send to AI
  globalShortcut.register('CommandOrControl+Shift+S', async () => {
    try {
      const sources = await (await import('electron')).desktopCapturer.getSources({
        types: ['screen'],
        thumbnailSize: { width: 1920, height: 1080 },
      })
      if (sources.length > 0) {
        const screenshot = sources[0].thumbnail.toPNG()
        mainWindow?.webContents.send('screenshot-captured', screenshot.toString('base64'))
        mainWindow?.show()
        mainWindow?.focus()
      }
    } catch {
      // Screenshot not available
    }
  })
}

// ── IPC Handlers ──

function registerIPC(): void {
  // Get clipboard text
  ipcMain.handle('get-clipboard', () => {
    return clipboard.readText()
  })

  // Set clipboard text
  ipcMain.handle('set-clipboard', (_event, text: string) => {
    clipboard.writeText(text)
    return true
  })

  // Get selected text (via clipboard trick)
  ipcMain.handle('get-selected-text', () => {
    // Save current clipboard
    const saved = clipboard.readText()
    // Simulate Ctrl+C to copy selection
    // This is OS-dependent and may not always work
    return saved // For now, return clipboard content
  })

  // Get system info
  ipcMain.handle('get-system-info', () => {
    return {
      platform: process.platform,
      arch: process.arch,
      version: app.getVersion(),
      electron: process.versions.electron,
      node: process.versions.node,
      chrome: process.versions.chrome,
    }
  })

  // Open external URL
  ipcMain.handle('open-external', (_event, url: string) => {
    shell.openExternal(url)
    return true
  })

  // Window controls for frameless quick-assist
  ipcMain.handle('window-close', (event) => {
    BrowserWindow.fromWebContents(event.sender)?.hide()
  })

  ipcMain.handle('window-minimize', (event) => {
    BrowserWindow.fromWebContents(event.sender)?.minimize()
  })
}

// ── Utility ──

function getIconPath(): string {
  // Try to find icon in various locations
  const candidates = [
    path.join(__dirname, '../../assets/icons/app.ico'),
    path.join(__dirname, '../../../assets/icons/app.ico'),
    path.join(app.getAppPath(), 'assets/icons/app.ico'),
  ]
  for (const p of candidates) {
    try {
      require('fs').accessSync(p)
      return p
    } catch {
      // continue
    }
  }
  return '' // Electron will use default icon
}

// ── App Lifecycle ──

app.whenReady().then(() => {
  mainWindow = createMainWindow()
  createTray()
  registerGlobalShortcuts()
  registerIPC()
})

app.on('window-all-closed', () => {
  // Don't quit on macOS (tray icon still active)
  if (process.platform !== 'darwin' && !tray) {
    app.quit()
  }
})

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    mainWindow = createMainWindow()
  } else {
    mainWindow?.show()
    sendBehaviorLifecycle('app_activated')
  }
})

app.on('will-quit', () => {
  sendBehaviorLifecycle('app_closed')
  globalShortcut.unregisterAll()
  tray?.destroy()
})

// Prevent multiple instances
const gotTheLock = app.requestSingleInstanceLock()
if (!gotTheLock) {
  app.quit()
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore()
      mainWindow.show()
      mainWindow.focus()
    }
  })
}
