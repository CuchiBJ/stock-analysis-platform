import type { SectorPerformance } from '@/types/sector'
import Card from '@/components/base/Card'
import Metric from '@/components/base/Metric'
import LoadingSkeleton from '@/components/base/LoadingSkeleton'

interface SectorPerformanceProps {
  sector: SectorPerformance | null
  loading: boolean
}

export default function SectorPerformanceComponent({ sector, loading }: SectorPerformanceProps) {
  if (loading) {
    return (
      <Card>
        <h3 className="text-sm font-bold mb-3">Sector Performance</h3>
        <div className="grid grid-cols-3 gap-2">
          <LoadingSkeleton variant="metric" />
          <LoadingSkeleton variant="metric" />
          <LoadingSkeleton variant="metric" />
        </div>
      </Card>
    )
  }

  if (!sector) {
    return (
      <Card>
        <h3 className="text-sm font-bold mb-3">Sector Performance</h3>
        <p className="text-muted-foreground text-xs">Select a sector to view performance</p>
      </Card>
    )
  }

  return (
    <Card>
      <h3 className="text-sm font-bold mb-3">{sector.name} Performance</h3>
      <div className="grid grid-cols-3 gap-3">
        <Metric
          label="Daily"
          value={`${sector.performance_daily > 0 ? '+' : ''}${sector.performance_daily.toFixed(2)}%`}
          change={sector.performance_daily}
          trend={sector.performance_daily > 0 ? 'up' : sector.performance_daily < 0 ? 'down' : 'neutral'}
          size="sm"
        />
        <Metric
          label="Weekly"
          value={`${sector.performance_weekly > 0 ? '+' : ''}${sector.performance_weekly.toFixed(2)}%`}
          change={sector.performance_weekly}
          trend={sector.performance_weekly > 0 ? 'up' : sector.performance_weekly < 0 ? 'down' : 'neutral'}
          size="sm"
        />
        <Metric
          label="Monthly"
          value={`${sector.performance_monthly > 0 ? '+' : ''}${sector.performance_monthly.toFixed(2)}%`}
          change={sector.performance_monthly}
          trend={sector.performance_monthly > 0 ? 'up' : sector.performance_monthly < 0 ? 'down' : 'neutral'}
          size="sm"
        />
      </div>
      <div className="mt-3 pt-3 border-t border-border/50">
        <div className="flex justify-between text-xs">
          <span className="text-muted-foreground">vs SPY:</span>
          <span className={sector.performance_vs_spy > 0 ? 'text-green-500' : 'text-red-500'}>
            {sector.performance_vs_spy > 0 ? '+' : ''}{sector.performance_vs_spy.toFixed(2)}%
          </span>
        </div>
        <div className="flex justify-between text-xs mt-1">
          <span className="text-muted-foreground">Trend:</span>
          <span className="font-medium capitalize">{sector.trend}</span>
        </div>
        <div className="flex justify-between text-xs mt-1">
          <span className="text-muted-foreground">Strength:</span>
          <span className="font-medium capitalize">{sector.strength}</span>
        </div>
      </div>
    </Card>
  )
}
