/**
 * SSE (Server-Sent Events) client for agent execution streaming.
 * Connects to the Python AI service SSE endpoint via Vite proxy.
 */

import type { StreamEvent } from '@/types'

export type SSEEventHandler = (event: StreamEvent) => void

interface SSEConnection {
  close: () => void
}

/**
 * Open an SSE connection for agent execution streaming.
 * POST body triggers the stream; events arrive on the response body.
 */
export function connectAgentSSE(
  sessionId: string,
  modeId: string,
  message: string,
  llmConfig: any,
  extraContext: any,
  handlers: {
    onEvent: SSEEventHandler
    onError?: (error: Error) => void
    onClose?: () => void
  },
): SSEConnection {
  const controller = new AbortController()

  const run = async () => {
    try {
      const res = await fetch('/api/ai/agent/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
        body: JSON.stringify({ 
          session_id: sessionId, 
          mode_id: modeId, 
          message,
          strategy: extraContext.strategy,
          tools: extraContext.enabled_tools,
          context: { llm_config: llmConfig, ...extraContext }
        }),
        signal: controller.signal,
      })

      if (!res.ok || !res.body) {
        throw new Error(`SSE connection failed: ${res.status}`)
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let currentEvent = ''
      let currentData = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (line.startsWith('event:')) {
            const raw = line.slice(6)
            currentEvent = raw.startsWith(' ') ? raw.slice(1) : raw
          } else if (line.startsWith('data:')) {
            const raw = line.slice(5)
            currentData += (currentData ? '\n' : '') + (raw.startsWith(' ') ? raw.slice(1) : raw)
          } else if (line === '' && currentData) {
            try {
              const parsed: StreamEvent = JSON.parse(currentData)
              if (!parsed.event && currentEvent) {
                parsed.event = currentEvent as StreamEvent['event']
              }
              handlers.onEvent(parsed)
            } catch {
              // skip malformed events
            }
            currentEvent = ''
            currentData = ''
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        handlers.onError?.(err as Error)
      }
    } finally {
      handlers.onClose?.()
    }
  }

  run()

  return {
    close: () => controller.abort(),
  }
}
