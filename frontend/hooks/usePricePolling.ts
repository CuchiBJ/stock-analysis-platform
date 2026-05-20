import { useEffect, useState, useCallback, useRef } from 'react';

interface PriceData {
  symbol: string;
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  vwap?: number;
}

interface MetricData {
  symbol: string;
  timestamp: string;
  // Add other metric fields as needed
}

interface UsePricePollingOptions {
  symbols: string[];
  pollInterval?: number; // in milliseconds, default 30000 (30 seconds)
  enabled?: boolean;
}

export function usePricePolling(options: UsePricePollingOptions) {
  const {
    symbols,
    pollInterval = 30000,
    enabled = true,
  } = options;

  const [prices, setPrices] = useState<Map<string, PriceData>>(new Map());
  const [metrics, setMetrics] = useState<Map<string, MetricData>>(new Map());
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  // Use refs to avoid infinite loop
  const symbolsRef = useRef(symbols);
  const enabledRef = useRef(enabled);

  // Update refs when values change
  useEffect(() => {
    symbolsRef.current = symbols;
  }, [symbols]);

  useEffect(() => {
    enabledRef.current = enabled;
  }, [enabled]);

  const fetchPrices = useCallback(async () => {
    if (!enabledRef.current || symbolsRef.current.length === 0) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

      // Fetch prices for all symbols
      const pricePromises = symbolsRef.current.map(async (symbol) => {
        try {
          const response = await fetch(`${apiUrl}/api/v1/stocks/${symbol}/prices?days=1`);
          if (!response.ok) {
            throw new Error(`Failed to fetch prices for ${symbol}`);
          }
          const data = await response.json();
          // Get the latest price (first item if array)
          const latestPrice = Array.isArray(data) && data.length > 0 ? data[0] : null;
          return { symbol, price: latestPrice };
        } catch (err) {
          console.error(`Error fetching prices for ${symbol}:`, err);
          return { symbol, price: null };
        }
      });

      const results = await Promise.all(pricePromises);

      // Update prices state
      setPrices(prev => {
        const newPrices = new Map(prev);
        results.forEach(({ symbol, price }) => {
          if (price) {
            newPrices.set(symbol, price);
          }
        });
        return newPrices;
      });

      setLastUpdate(new Date().toISOString());
    } catch (err) {
      setError(err as Error);
      console.error('Error fetching prices:', err);
    } finally {
      setIsLoading(false);
    }
  }, []); // No dependencies - uses refs instead

  useEffect(() => {
    if (!enabledRef.current || symbolsRef.current.length === 0) {
      return;
    }

    // Initial fetch
    fetchPrices();

    // Set up polling interval
    const interval = setInterval(() => {
      fetchPrices();
    }, pollInterval);

    return () => {
      clearInterval(interval);
    };
  }, [pollInterval]); // Only pollInterval in dependencies - use refs for enabled/symbols

  return {
    prices,
    metrics,
    lastUpdate,
    isLoading,
    error,
  };
}
