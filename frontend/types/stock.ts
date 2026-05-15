export interface Stock {
  symbol: string;
  name: string;
  sector: string | null;
  industry: string | null;
  market_cap: number | null;
  float_shares: number | null;
  is_adr: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface StockPrice {
  id: number;
  symbol: string;
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  vwap: number | null;
}

export interface StockMetrics {
  id: number;
  symbol: string;
  date: string;
  ema20: number | null;
  ema50: number | null;
  ema200: number | null;
  rsi: number | null;
  relative_strength_spy: number | null;
  relative_strength_qqq: number | null;
  distance_to_ema20: number | null;
  distance_to_ema50: number | null;
  distance_to_high_52w: number | null;
  avg_volume_20d: number | null;
  relative_volume: number | null;
  // Additional indicators
  sma50: number | null;
  sma150: number | null;
  sma200: number | null;
  perf_1y: number | null;
  perf_1w: number | null;
  low_52w: number | null;
  adr_percent: number | null;
  avg_volume_10d: number | null;
  current_price: number | null;
}
