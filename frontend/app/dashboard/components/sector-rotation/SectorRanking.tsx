import { SectorRankingProps } from './types'
import Card from '@/components/base/Card'
import LoadingSkeleton from '@/components/base/LoadingSkeleton'
import TrendIndicator from '@/components/base/TrendIndicator'

export default function SectorRanking({ sectors, loading }: SectorRankingProps) {
  if (loading) {
    return (
      <Card>
        <h3 className="text-sm font-bold mb-3">Sector Ranking</h3>
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => (
            <LoadingSkeleton key={i} variant="metric" />
          ))}
        </div>
      </Card>
    )
  }

  if (!sectors || sectors.length === 0) {
    return (
      <Card>
        <h3 className="text-sm font-bold mb-3">Sector Ranking</h3>
        <p className="text-muted-foreground text-xs">No sector data</p>
      </Card>
    )
  }

  const sortedSectors = [...sectors].sort((a, b) => b.performance_daily - a.performance_daily)

  return (
    <Card>
      <h3 className="text-sm font-bold mb-3">Sector Ranking</h3>
      <div className="space-y-2">
        {sortedSectors.slice(0, 10).map((sector, index) => (
          <div
            key={sector.name}
            className="flex items-center justify-between text-xs py-2 border-b border-border/50 last:border-0"
          >
            <div className="flex items-center gap-3">
              <span className="w-6 text-center font-bold text-muted-foreground">#{index + 1}</span>
              <span className="font-medium w-24 truncate">{sector.name}</span>
            </div>
            <div className="flex items-center gap-4">
              <span className={`font-mono ${sector.performance_daily > 0 ? 'text-green-500' : 'text-red-500'}`}>
                {sector.performance_daily > 0 ? '+' : ''}{sector.performance_daily.toFixed(2)}%
              </span>
              <TrendIndicator 
                trend={sector.strength === 'strong' ? 'bullish' : sector.strength === 'weak' ? 'bearish' : 'neutral'} 
                size="sm" 
              />
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}
