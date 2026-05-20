'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { WS_URL } from '@/lib/utils'

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
  const wsRef = useRef<WebSocket | null>(null)
  const clientId = useRef(`client_${Date.now()}_${Math.random().toString(36).slice(2)}`)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mountedRef = useRef(true)

  const connect = useCallback(() => {
    if (!enabled || !mountedRef.current) return

    const url = `${WS_URL}/api/v1/ws?client_id=${clientId.current}`
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
      reconnectTimer.current = setTimeout(connect, reconnectDelay)
    }
  }, [channel, enabled, reconnectDelay])

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
  }, [connect])

  return { data, isConnected, lastEvent }
}
