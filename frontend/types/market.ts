// Market Overview Types
export interface IndexData {
  symbol: string  // SPY, QQQ, IWM, DIA
  name: string
  current_price: number
  daily_change_pct: number
  gap_pct: number | null
  relative_volume: number | null
  distance_ema20: number | null
  trend_short: 'bullish' | 'neutral' | 'bearish'
  strength: 'bullish' | 'neutral' | 'bearish'
  updated_at: string
}

// Market Breadth Types
export interface BreadthData {
  advance_decline: {
    advancers: number
    decliners: number
    ratio: number
  }
  new_highs_lows: {
    new_highs: number
    new_lows: number
  }
  above_ema: {
    above_ema20: number  // percentage
    above_ema50: number  // percentage
  }
  color_breakdown: {
    green_stocks: number
    red_stocks: number
    neutral_stocks: number
  }
  sector_breadth: SectorBreadth[]
}

export interface SectorBreadth {
  sector: string
  advancers: number
  decliners: number
  strength: 'strong' | 'moderate' | 'weak'
}

// Theme/Flow Types
export interface Theme {
  id: string
  name: string  // "AI Infrastructure", "Semiconductors", "Uranium"
  status: 'dominant' | 'accelerating' | 'decelerating' | 'emerging'
  strength: number  // 0-100
  related_sectors: string[]
  top_stocks: string[]  // symbols
  flow_direction: 'in' | 'out' | 'neutral'
  momentum: number
  correlation: number
}

// Calendar Types
export interface Event {
  id: string
  date: string
  type: 'earnings' | 'cpi' | 'fomc' | 'speech' | 'unemployment' | 'options_expiry'
  title: string
  importance: 'high' | 'medium' | 'low'
  affected_symbols?: string[]
  description?: string
}
