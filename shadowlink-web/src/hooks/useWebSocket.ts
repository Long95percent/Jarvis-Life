/**
 * useWebSocket — React hook for WebSocket lifecycle management.
 */

import { useEffect, useCallback, useRef, useState } from 'react'
import { getWebSocket } from '@/services'

export function useWebSocket() {
  const [connected, setConnected] = useState(false)
  const unsubsRef = useRef<Array<() => void>>([])

  useEffect(() => {
    const ws = getWebSocket()
    ws.connect()

    unsubsRef.current.push(
      ws.on('_connected', () => setConnected(true)),
      ws.on('_disconnected', () => setConnected(false)),
    )

    return () => {
      unsubsRef.current.forEach((unsub) => unsub())
      unsubsRef.current = []
    }
  }, [])

  const send = useCallback((type: string, payload: unknown) => {
    getWebSocket().send(type, payload)
  }, [])

  const subscribe = useCallback((event: string, handler: (data: unknown) => void) => {
    return getWebSocket().on(event, handler)
  }, [])

  return { connected, send, subscribe }
}
