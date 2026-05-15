import { Stock } from './stock'

export type BadgeType = 
  | 'breakout'
  | 'near_ath'
  | 'earnings'
  | 'squeeze'
  | 'ema20_reclaim'
  | 'unusual_volume'
  | 'tight_consolidation'
  | 'strong_rs'

export interface LeaderData {
  symbol: string
  name: string
  sector: string
  price: number
  gain_pct: number
  rvol: number
  rs_rank: number
  volume: number
  market_cap: number
  distance_ath: number
  float: number
  trend_quality: number  // 0-100
  score: number  // 0-100
  badges: BadgeType[]
  mini_chart: number[]  // last 30 closes
}

export interface ScoreBreakdown {
  total: number
  rs: number
  rvol: number
  momentum: number
  sector: number
  trend: number
  proximity: number
  breakout: number
}

export interface ScoredStock {
  symbol: string
  name: string
  sector: string
  score: ScoreBreakdown
  price: number
  change_pct: number
}
