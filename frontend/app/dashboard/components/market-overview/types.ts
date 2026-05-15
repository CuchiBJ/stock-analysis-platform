export interface IndexCardProps {
  symbol: string
  name: string
  current_price: number
  daily_change_pct: number
  gap_pct: number | null
  relative_volume: number | null
  distance_ema20: number | null
  trend_short: 'bullish' | 'neutral' | 'bearish'
  strength: 'bullish' | 'neutral' | 'bearish'
}
