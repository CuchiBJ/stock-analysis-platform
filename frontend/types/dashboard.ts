export type MarketFilter = 'all' | 'large_cap' | 'mid_cap' | 'small_cap'
export type TimeframeFilter = '1d' | '1w' | '1m'
export type TableView = 'compact' | 'detailed'

export interface DashboardPreferences {
  marketFilter: MarketFilter
  sectorFilter: string | null
  timeframeFilter: TimeframeFilter
  tableView: TableView
  showCharts: boolean
  showBadges: boolean
  sidebarCollapsed: boolean
}

export interface QuickFilter {
  id: string
  name: string
  filters: {
    min_rvol?: number
    market_cap_range?: [number, number]
    price_range?: [number, number]
    sector?: string
    min_distance_high?: number
    min_rs?: number
    min_volume?: number
    max_adr?: number
    gap_pct_range?: [number, number]
    consolidation_days?: number
    upcoming_earnings_days?: number
  }
}
