'use client'

import { useEffect, useId, useRef, useState, useCallback } from 'react'

interface UseWebSocketOptions {
  channel: string
  enabled?: boolean
  reconnectDelay?: number
}

interface UseWebSocketResult<T> {
  data: T | null
  isConnected: boolean
  lastEvent: number | null
}

export function useWebSocket<T = unknown>({
  channel,
  enabled = true,
  reconnectDelay = 3000,
}: UseWebSocketOptions): UseWebSocketResult<T> {
  const [data, setData] = useState<T | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [lastEvent, setLastEvent] = useState<number | null>(null)
  const [reconnectAttempt, setReconnectAttempt] = useState(0)
  const wsRef = useRef<WebSocket | null>(null)
  const clientId = useId()
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mountedRef = useRef(true)

  const connect = useCallback(() => {
    if (!enabled || !mountedRef.current) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.host}/api/v1/ws?client_id=${encodeURIComponent(clientId)}`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      if (!mountedRef.current) return
      setIsConnected(true)
      // Subscribe to the requested channel
      ws.send(JSON.stringify({ action: 'subscribe', channel }))
    }

    ws.onmessage = (event) => {
      if (!mountedRef.current) return
      try {
        const msg = JSON.parse(event.data)
        // Accept messages targeting our channel or with no channel field
        if (!msg.channel || msg.channel === channel) {
          setData(msg.data ?? msg)
          setLastEvent(Date.now())
        }
      } catch {
        // ignore malformed messages
      }
    }

    ws.onerror = () => {
      // errors trigger onclose automatically
    }

    ws.onclose = () => {
      if (!mountedRef.current) return
      setIsConnected(false)
      wsRef.current = null
      // Auto-reconnect
      reconnectTimer.current = setTimeout(() => {
        if (mountedRef.current) setReconnectAttempt(attempt => attempt + 1)
      }, reconnectDelay)
    }
  }, [channel, clientId, enabled, reconnectDelay])

  useEffect(() => {
    mountedRef.current = true
    connect()

    return () => {
      mountedRef.current = false
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      if (wsRef.current) {
        wsRef.current.onclose = null // prevent reconnect on intentional close
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [connect, reconnectAttempt])

  return { data, isConnected, lastEvent }
}
