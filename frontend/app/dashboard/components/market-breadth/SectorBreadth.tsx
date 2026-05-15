import { SectorBreadth as SectorBreadthType } from '@/types/market'
import TrendIndicator from '@/components/base/TrendIndicator'

interface SectorBreadthProps {
  sectors: SectorBreadthType[]
}

export default function SectorBreadth({ sectors }: SectorBreadthProps) {
  if (!sectors || sectors.length === 0) {
    return <p className="text-muted-foreground text-xs">No sector breadth data</p>
  }

  const getStrengthTrend = (strength: string): 'bullish' | 'bearish' | 'neutral' => {
    if (strength === 'strong') return 'bullish'
    if (strength === 'weak') return 'bearish'
    return 'neutral'
  }

  const getRatioColor = (ratio: number) => {
    if (ratio >= 2) return 'text-green-500'
    if (ratio >= 1) return 'text-yellow-500'
    return 'text-red-500'
  }

  return (
    <div className="space-y-2">
      {sectors.slice(0, 6).map((sector) => {
        const ratio = sector.decliners > 0 ? sector.advancers / sector.decliners : sector.advancers
        
        return (
          <div key={sector.sector} className="flex items-center justify-between text-xs">
            <span className="text-foreground font-medium w-24 truncate">{sector.sector}</span>
            <div className="flex items-center gap-2">
              <span className={`font-mono ${getRatioColor(ratio)}`}>
                {ratio.toFixed(2)}
              </span>
              <TrendIndicator trend={getStrengthTrend(sector.strength)} size="sm" />
            </div>
          </div>
        )
      })}
    </div>
  )
}
