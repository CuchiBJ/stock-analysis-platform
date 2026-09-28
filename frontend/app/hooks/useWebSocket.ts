import { useEffect, useId, useRef, useState, useCallback } from 'react';

interface PriceUpdate {
  symbol: string;
  timestamp: string;
  data: {
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
    vwap: number;
  };
  metadata: {
    source: string;
    normalized_at: string;
  };
}

interface UseWebSocketOptions {
  url?: string;
  channels?: string[];
  onMessage?: (message: unknown) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
  reconnectInterval?: number;
}

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const {
    url,
    channels = ['price_update'],
    onMessage,
    onConnect,
    onDisconnect,
    onError,
    reconnectInterval = 5000,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [reconnectAttempt, setReconnectAttempt] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const clientId = useId();

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    try {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const endpoint = url ?? `${protocol}//${window.location.host}/api/v1/ws`;
      const separator = endpoint.includes('?') ? '&' : '?';
      const wsUrl = `${endpoint}${separator}client_id=${encodeURIComponent(clientId)}`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        setError(null);
        console.log('WebSocket connected');

        // Subscribe to channels
        channels.forEach(channel => {
          ws.send(JSON.stringify({
            action: 'subscribe',
            channel,
          }));
        });

        onConnect?.();
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          onMessage?.(message);
        } catch (err) {
          console.error('Error parsing WebSocket message:', err);
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        wsRef.current = null;
        console.log('WebSocket disconnected');
        onDisconnect?.();

        // Attempt reconnection
        reconnectTimeoutRef.current = setTimeout(() => {
          setReconnectAttempt(attempt => attempt + 1);
        }, reconnectInterval);
      };

      ws.onerror = (event) => {
        setError(new Error('WebSocket error'));
        onError?.(event);
      };
    } catch (err) {
      setError(err as Error);
      onError?.(err as Event);
    }
  }, [url, channels, onMessage, onConnect, onDisconnect, onError, reconnectInterval, clientId]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }

    if (wsRef.current) {
      wsRef.current.onclose = null;
      wsRef.current.close();
      wsRef.current = null;
    }

    setIsConnected(false);
  }, []);

  const subscribe = useCallback((channel: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        action: 'subscribe',
        channel,
      }));
    }
  }, []);

  const unsubscribe = useCallback((channel: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        action: 'unsubscribe',
        channel,
      }));
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => connect());

    return () => {
      disconnect();
    };
  }, [connect, disconnect, reconnectAttempt]);

  return {
    isConnected,
    error,
    subscribe,
    unsubscribe,
  };
}

export function useRealtimePrices(symbols: string[] = []) {
  void symbols;
  const [prices, setPrices] = useState<Map<string, PriceUpdate>>(new Map());
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);

  const handlePriceUpdate = useCallback((message: unknown) => {
    const envelope = message as { channel?: unknown; data?: PriceUpdate };
    if (envelope.channel === 'price_update' && envelope.data) {
      setPrices(prev => {
        const newPrices = new Map(prev);
        newPrices.set(envelope.data!.symbol, envelope.data!);
        return newPrices;
      });
      setLastUpdate(new Date().toISOString());
    }
  }, []);

  const { isConnected, error } = useWebSocket({
    channels: ['price_update', 'realtime_status'],
    onMessage: handlePriceUpdate,
  });

  return {
    prices,
    lastUpdate,
    isConnected,
    error,
  };
}
