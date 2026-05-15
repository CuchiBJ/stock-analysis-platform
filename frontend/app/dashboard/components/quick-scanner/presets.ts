import { QuickFilter } from '@/types/scanner'

export const QUICK_PRESETS: QuickFilter[] = [
  {
    id: 'earnings',
    name: 'Earnings Plays',
    description: 'Stocks with upcoming earnings and strong setup',
    filters: {
      min_relative_volume: 1.2,
      min_distance_ema20: 0,
      max_distance_high_52w: -5,
      has_earnings: true
    }
  },
  {
    id: 'breakouts',
    name: 'Breakouts',
    description: 'Stocks breaking above resistance with volume',
    filters: {
      min_relative_volume: 2,
      min_distance_ema20: 2,
      min_distance_high_52w: -10,
      ema20_above_ema50: true
    }
  },
  {
    id: 'near_ath',
    name: 'Near ATH',
    description: 'Stocks trading near 52-week highs',
    filters: {
      min_distance_high_52w: -5,
      min_relative_volume: 1.5,
      min_distance_ema20: 0
    }
  },
  {
    id: 'squeeze',
    name: 'Squeeze Setup',
    description: 'Bollinger squeeze with low volatility',
    filters: {
      max_bollinger_width: 0.5,
      min_relative_volume: 0.8,
      min_distance_ema20: -1
    }
  },
  {
    id: 'strong_momentum',
    name: 'Strong Momentum',
    description: 'Stocks with strong upward momentum',
    filters: {
      min_relative_volume: 1.5,
      min_distance_ema20: 3,
      ema20_above_ema50: true,
      ema50_above_ema200: true
    }
  },
  {
    id: 'sector_leaders',
    name: 'Sector Leaders',
    description: 'Top performing stocks in each sector',
    filters: {
      min_relative_volume: 1.2,
      min_distance_ema20: 1,
      min_distance_high_52w: -15
    }
  }
]
