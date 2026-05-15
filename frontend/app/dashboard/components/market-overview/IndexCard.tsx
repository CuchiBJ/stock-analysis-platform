import { IndexCardProps } from './types'
import Card from '@/components/base/Card'
import Metric from '@/components/base/Metric'
import TrendIndicator from '@/components/base/TrendIndicator'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

export default function IndexCard({
  symbol,
  name,
  current_price,
  daily_change_pct,
  gap_pct,
  relative_volume,
  distance_ema20,
  trend_short,
  strength
}: IndexCardProps) {
  const getTrend = (): 'up' | 'down' | 'neutral' => {
    if (daily_change_pct > 0) return 'up'
    if (daily_change_pct < 0) return 'down'
    return 'neutral'
  }

  const formatPrice = (price: number) => {
    if (price >= 1000) return `$${price.toFixed(2)}`
    if (price >= 100) return `$${price.toFixed(2)}`
    return `$${price.toFixed(3)}`
  }

  return (
    <Card variant="compact" className="hover:border-border/80">
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="text-lg font-bold text-foreground">{symbol}</div>
          <div className="text-xs text-muted-foreground">{name}</div>
        </div>
        <TrendIndicator trend={trend_short} size="sm" />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Metric
          label="Price"
          value={formatPrice(current_price)}
          change={daily_change_pct}
          trend={getTrend()}
          size="sm"
        />

        <Metric
          label="Gap %"
          value={gap_pct ? `${gap_pct.toFixed(2)}%` : 'N/A'}
          change={gap_pct ?? undefined}
          trend={gap_pct ? (gap_pct > 0 ? 'up' : gap_pct < 0 ? 'down' : 'neutral') : 'neutral'}
          size="sm"
        />

        <Metric
          label="RVOL"
          value={relative_volume ? relative_volume.toFixed(2) : 'N/A'}
          size="sm"
        />

        <Metric
          label="Dist EMA20"
          value={distance_ema20 ? `${distance_ema20.toFixed(2)}%` : 'N/A'}
          change={distance_ema20 ?? undefined}
          trend={distance_ema20 ? (distance_ema20 > 0 ? 'up' : distance_ema20 < 0 ? 'down' : 'neutral') : 'neutral'}
          size="sm"
        />
      </div>

      <div className="mt-3 pt-3 border-t border-border/50">
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">Strength:</span>
          <TrendIndicator trend={strength} size="sm" showLabel />
        </div>
      </div>
    </Card>
  )
}
