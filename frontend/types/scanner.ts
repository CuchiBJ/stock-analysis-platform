export interface ScannerFilter {
  min_relative_volume?: number;
  max_distance_to_ema20?: number;
  min_distance_to_ema50?: number;
  sector?: string;
  industry?: string;
  min_market_cap?: number;
  max_market_cap?: number;
  is_adr?: boolean;
  min_price?: number;
  max_price?: number;
  breakout?: boolean;
}

export interface ScanResult {
  symbol: string;
  name: string;
  sector: string | null;
  price: number;
  relative_volume: number;
  distance_to_ema20: number;
  rsi: number;
}

export interface QuickScannerFilter {
  min_rvol?: number
  min_relative_volume?: number
  market_cap_range?: [number, number]
  price_range?: [number, number]
  sector?: string
  min_distance_high?: number
  min_distance_high_52w?: number
  max_distance_high_52w?: number
  min_distance_ema20?: number
  min_rs?: number
  min_volume?: number
  max_adr?: number
  gap_pct_range?: [number, number]
  consolidation_days?: number
  upcoming_earnings_days?: number
  has_earnings?: boolean
  max_bollinger_width?: number
  ema20_above_ema50?: boolean
  ema50_above_ema200?: boolean
}

export interface QuickFilter {
  id: string
  name: string
  description?: string
  filters: QuickScannerFilter
}
