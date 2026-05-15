export interface Watchlist {
  id: string
  name: string
  symbols: string[]
  created_at: string
  updated_at: string
}

export interface WatchlistCreate {
  name: string
  symbols: string[]
}

export type SmartWatchlistType =
  | 'persistent_leaders'
  | 'strongest_pullbacks'
  | 'ema20_defenders'
  | 'scanner_repeaters'
  | 'tight_consolidations'
  | 'strongest_rs'
  | 'unusual_strength'

export interface SmartWatchlist {
  id: string
  name: string
  type: SmartWatchlistType
  stocks: string[]  // symbols
  appearance_count: number  // days appeared consecutively
  last_updated: string
}
