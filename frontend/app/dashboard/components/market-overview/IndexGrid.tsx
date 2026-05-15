import { IndexData } from '@/types/market'
import IndexCard from './IndexCard'
import LoadingSkeleton from '@/components/base/LoadingSkeleton'

interface IndexGridProps {
  indices: IndexData[]
  loading: boolean
}

export default function IndexGrid({ indices, loading }: IndexGridProps) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[...Array(4)].map((_, i) => (
          <LoadingSkeleton key={i} variant="metric" />
        ))}
      </div>
    )
  }

  if (!indices || indices.length === 0) {
    return (
      <div className="bg-card border border-border rounded-lg p-6 text-center">
        <p className="text-muted-foreground text-sm">No index data available</p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {indices.map((index) => (
        <IndexCard
          key={index.symbol}
          symbol={index.symbol}
          name={index.name}
          current_price={index.current_price}
          daily_change_pct={index.daily_change_pct}
          gap_pct={index.gap_pct}
          relative_volume={index.relative_volume}
          distance_ema20={index.distance_ema20}
          trend_short={index.trend_short || 'neutral'}
          strength={index.strength || 'neutral'}
        />
      ))}
    </div>
  )
}
