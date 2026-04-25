/**
 * WebSocket service — real-time communication with the Java backend.
 * Uses native WebSocket (not socket.io) to stay lightweight.
 */

type MessageHandler = (data: unknown) => void

interface WSOptions {
  url?: string
  reconnectInterval?: number
  maxReconnectAttempts?: number
}

class WebSocketService {
  private ws: WebSocket | null = null
  private handlers = new Map<string, Set<MessageHandler>>()
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private reconnectAttempts = 0
  private url: string
  private maxReconnectAttempts: number
  private reconnectInterval: number
  private intentionallyClosed = false

  constructor(options: WSOptions = {}) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    this.url = options.url ?? `${protocol}//${window.location.host}/ws`
    this.reconnectInterval = options.reconnectInterval ?? 3000
    this.maxReconnectAttempts = options.maxReconnectAttempts ?? 10
  }

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) return

    this.intentionallyClosed = false
    this.ws = new WebSocket(this.url)

    this.ws.onopen = () => {
      this.reconnectAttempts = 0
      this.emit('_connected', null)
    }

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as { type: string; payload: unknown }
        this.emit(msg.type, msg.payload)
      } catch {
        // ignore non-JSON messages
      }
    }

    this.ws.onclose = () => {
      this.emit('_disconnected', null)
      if (!this.intentionallyClosed) {
        this.scheduleReconnect()
      }
    }

    this.ws.onerror = () => {
      this.ws?.close()
    }
  }

  disconnect(): void {
    this.intentionallyClosed = true
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    this.ws?.close()
    this.ws = null
  }

  send(type: string, payload: unknown): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type, payload }))
    }
  }

  on(event: string, handler: MessageHandler): () => void {
    if (!this.handlers.has(event)) {
      this.handlers.set(event, new Set())
    }
    this.handlers.get(event)!.add(handler)
    return () => this.handlers.get(event)?.delete(handler)
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }

  private emit(event: string, data: unknown): void {
    this.handlers.get(event)?.forEach(h => h(data))
    this.handlers.get('*')?.forEach(h => h({ type: event, payload: data }))
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) return
    this.reconnectAttempts++
    const delay = this.reconnectInterval * Math.min(this.reconnectAttempts, 5)
    this.reconnectTimer = setTimeout(() => this.connect(), delay)
  }
}

/** Singleton */
let wsInstance: WebSocketService | null = null

export function getWebSocket(options?: WSOptions): WebSocketService {
  if (!wsInstance) {
    wsInstance = new WebSocketService(options)
  }
  return wsInstance
}

export { WebSocketService }
