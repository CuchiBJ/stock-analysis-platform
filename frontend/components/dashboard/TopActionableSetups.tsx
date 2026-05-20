'use client'

import { useEffect, useState } from 'react'
import Card from '@/components/base/Card'
import LoadingSkeleton from '@/components/base/LoadingSkeleton'
import CompactSetupCard from './CompactSetupCard'
import { Flame } from 'lucide-react'

interface ActionableSetup {
  symbol: string
  priority_score: number
  narrative: string
  pullback_quality: number
  distance_to_ema21: number
  rs_spy: number
  volume_contraction: number
}

export default function TopActionableSetups() {
  const [setups, setSetups] = useState<ActionableSetup[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchSetups = async () => {
      try {
        setLoading(true)
        setError(null)
        const response = await fetch('http://localhost:8000/api/v1/transitions/actionable?limit=5')
        if (!response.ok) throw new Error('Failed to load actionable setups')
        const data = await response.json()
        setSetups(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load actionable setups')
        console.error('Error loading actionable setups:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchSetups()
    // Refresh every 60 seconds
    const interval = setInterval(fetchSetups, 60000)
    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return (
      <Card className="p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Top Actionable Setups</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {[...Array(5)].map((_, i) => (
            <LoadingSkeleton key={i} variant="card" />
          ))}
        </div>
      </Card>
    )
  }

  if (error) {
    return (
      <Card className="p-4">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-4">Top Actionable Setups</h3>
        <p className="text-red-500 text-sm">Error: {error}</p>
      </Card>
    )
  }

  if (!setups || setups.length === 0) {
    return (
      <Card className="p-4">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-4">Top Actionable Setups</h3>
        <p className="text-muted-foreground text-sm">No actionable setups found</p>
      </Card>
    )
  }

  return (
    <Card blockType="actionable" className="p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Top Actionable Setups</h3>
          <Flame className="w-4 h-4 text-orange-400" />
        </div>
        <span className="text-xs text-muted-foreground">{setups.length} setups</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {setups.map((setup, index) => (
            <CompactSetupCard
              key={setup.symbol}
              symbol={setup.symbol}
              state="Constructive Pullback"
              transition="stable"
              transitionStrength={setup.priority_score}
              narrative={setup.narrative}
              confidence={setup.priority_score}
              freshness="fresh"
              daysInState={1}
              keyMetrics={{
                ema21: setup.distance_to_ema21 >= 0 ? `+${setup.distance_to_ema21.toFixed(1)}%` : `${setup.distance_to_ema21.toFixed(1)}%`,
                rs: setup.rs_spy || 100,
                volume: setup.volume_contraction ? `-${setup.volume_contraction.toFixed(0)}%` : 'N/A',
                base: '8-week'
              }}
              isPriority={index === 0}
            />
          ))}
      </div>
    </Card>
  )
}
