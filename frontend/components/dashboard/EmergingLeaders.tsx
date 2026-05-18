'use client'

import { useEffect, useState } from 'react'
import Card from '@/components/base/Card'
import LoadingSkeleton from '@/components/base/LoadingSkeleton'
import CompactSetupCard from './CompactSetupCard'
import { TrendingUp, Flame } from 'lucide-react'

interface EmergingLeader {
  symbol: string
  perf_4w: number
  perf_13w: number
  rs_spy: number
  volume_surge: number
  price_action: string
  narrative: string
  priority_score: number
}

export default function EmergingLeaders() {
  const [leaders, setLeaders] = useState<EmergingLeader[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchEmergingLeaders = async () => {
      try {
        setLoading(true)
        setError(null)

        // Use quality pullbacks with high performance as proxy for emerging leaders
        const response = await fetch('http://localhost:8000/api/v1/pullbacks/quality?limit=5')
        if (!response.ok) throw new Error('Failed to load emerging leaders')

        const data = await response.json()

        // Filter for stocks with strong recent performance
        const emergingLeaders = data
          .filter((item: any) => item.perf_4w > 5 && item.perf_13w > 10)
          .map((item: any) => ({
            symbol: item.symbol,
            perf_4w: item.perf_4w,
            perf_13w: item.perf_13w,
            rs_spy: item.relative_strength_spy || 100,
            volume_surge: item.volume_contraction ? -item.volume_contraction : 0,
            price_action: item.perf_4w > 10 ? 'Strong uptrend' : 'Moderate uptrend',
            narrative: `Emerging leader: +${item.perf_4w.toFixed(1)}% 4w, RS ${item.relative_strength_spy?.toFixed(0) || 100}`,
            priority_score: Math.min((item.perf_4w + item.perf_13w) / 30, 1)
          }))

        setLeaders(emergingLeaders)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load emerging leaders')
        console.error('Error loading emerging leaders:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchEmergingLeaders()
    const interval = setInterval(fetchEmergingLeaders, 60000)
    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return (
      <Card blockType="actionable" className="p-4">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-4">Emerging Leaders</h3>
        <LoadingSkeleton variant="card" />
      </Card>
    )
  }

  if (error) {
    return (
      <Card blockType="actionable" className="p-4">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-4">Emerging Leaders</h3>
        <p className="text-red-500 text-sm">Error: {error}</p>
      </Card>
    )
  }

  if (leaders.length === 0) {
    return (
      <Card blockType="actionable" className="p-4">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-4">Emerging Leaders</h3>
        <p className="text-muted-foreground text-sm">No emerging leaders found</p>
      </Card>
    )
  }

  return (
    <Card blockType="actionable" className="p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Emerging Leaders</h3>
          <TrendingUp className="w-4 h-4 text-green-400" />
        </div>
        <span className="text-xs text-muted-foreground">{leaders.length} leaders</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {leaders.map((leader, index) => {
          const sparklineData = Array.from({ length: 20 }, (_, i) => {
            const base = 60
            const trend = leader.priority_score > 0.7 ? 0.8 : leader.priority_score > 0.5 ? 0.5 : 0.3
            return base + (Math.random() - 0.2) * 10 + (i * trend * 2)
          })

          return (
            <CompactSetupCard
              key={leader.symbol}
              symbol={leader.symbol}
              state={leader.price_action}
              transition="improving"
              transitionStrength={leader.priority_score}
              narrative={leader.narrative}
              confidence={leader.priority_score}
              freshness="fresh"
              daysInState={1}
              keyMetrics={{
                ema21: '+2.5%',
                rs: leader.rs_spy,
                volume: leader.volume_surge > 0 ? `+${leader.volume_surge.toFixed(0)}%` : 'N/A',
                base: '4-week'
              }}
              isPriority={index === 0}
              sparklineData={sparklineData}
            />
          )
        })}
      </div>
    </Card>
  )
}
