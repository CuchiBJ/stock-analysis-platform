'use client'

import { useEffect, useState } from 'react'
import Card from '@/components/base/Card'
import LoadingSkeleton from '@/components/base/LoadingSkeleton'
import CompactSetupCard from './CompactSetupCard'
import { Star, Shield, Zap } from 'lucide-react'

interface WatchlistItem {
  symbol: string
  name: string
  type: 'quality-pullback' | 'ema20-defender' | 'emerging-leader'
  pullback_quality?: number
  distance_to_ema21?: number
  rs_spy?: number
  perf_4w?: number
  perf_13w?: number
  volume_contraction?: number
  narrative: string
  priority_score: number
}

export default function SmartWatchlists() {
  const [items, setItems] = useState<WatchlistItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'quality-pullback' | 'ema20-defender' | 'emerging-leader'>('quality-pullback')

  useEffect(() => {
    const fetchWatchlists = async () => {
      try {
        setLoading(true)
        setError(null)

        // Fetch from multiple endpoints
        const [qualityRes, leadersRes] = await Promise.all([
          fetch('http://localhost:8000/api/v1/pullbacks/quality?limit=5'),
          fetch('http://localhost:8000/api/v1/leaders?limit=5')
        ])

        if (!qualityRes.ok || !leadersRes.ok) throw new Error('Failed to load watchlists')

        const qualityData = await qualityRes.json()
        const leadersData = await leadersRes.json()

        // Transform to unified format
        const transformedItems: WatchlistItem[] = [
          ...qualityData.map((item: any) => ({
            symbol: item.symbol,
            name: item.symbol,
            type: 'quality-pullback' as const,
            pullback_quality: item.pullback_quality,
            distance_to_ema21: item.distance_to_ema21,
            rs_spy: item.relative_strength_spy,
            perf_4w: item.perf_4w,
            perf_13w: item.perf_13w,
            volume_contraction: item.volume_contraction,
            narrative: `Quality pullback at EMA21 with RS ${item.relative_strength_spy?.toFixed(0) || 100}`,
            priority_score: item.pullback_quality / 100
          })),
          ...leadersData.slice(0, 5).map((item: any) => ({
            symbol: item.symbol,
            name: item.symbol,
            type: 'ema20-defender' as const,
            distance_to_ema21: item.distance_to_ema21,
            rs_spy: item.relative_strength_spy,
            perf_4w: item.perf_4w,
            perf_13w: item.perf_13w,
            narrative: `Defending EMA21 with strong trend`,
            priority_score: 0.7
          }))
        ]

        setItems(transformedItems)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load watchlists')
        console.error('Error loading watchlists:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchWatchlists()
    const interval = setInterval(fetchWatchlists, 60000)
    return () => clearInterval(interval)
  }, [])

  const filteredItems = items.filter(item => item.type === activeTab).slice(0, 5)

  const getTabIcon = (type: string) => {
    switch (type) {
      case 'quality-pullback': return <Star className="w-4 h-4" />
      case 'ema20-defender': return <Shield className="w-4 h-4" />
      case 'emerging-leader': return <Zap className="w-4 h-4" />
      default: return null
    }
  }

  const getTabLabel = (type: string) => {
    switch (type) {
      case 'quality-pullback': return 'Quality Pullbacks'
      case 'ema20-defender': return 'EMA21 Defenders'
      case 'emerging-leader': return 'Emerging Leaders'
      default: return type
    }
  }

  if (loading) {
    return (
      <Card blockType="market-context" className="p-4">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-4">Smart Watchlists</h3>
        <LoadingSkeleton variant="card" />
      </Card>
    )
  }

  if (error) {
    return (
      <Card blockType="market-context" className="p-4">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-4">Smart Watchlists</h3>
        <p className="text-red-500 text-sm">Error: {error}</p>
      </Card>
    )
  }

  const tabs: ('quality-pullback' | 'ema20-defender' | 'emerging-leader')[] = ['quality-pullback', 'ema20-defender', 'emerging-leader']

  return (
    <Card blockType="market-context" className="p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Smart Watchlists</h3>
        <span className="text-xs text-muted-foreground">{filteredItems.length} items</span>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-4">
        {tabs.map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`flex items-center gap-1 px-3 py-1.5 rounded text-xs font-medium transition-all ${activeTab === tab
              ? 'bg-primary text-primary-foreground'
              : 'bg-muted text-muted-foreground hover:bg-muted/80'
              }`}
          >
            {getTabIcon(tab)}
            {getTabLabel(tab)}
          </button>
        ))}
      </div>

      {/* Content */}
      {filteredItems.length === 0 ? (
        <p className="text-muted-foreground text-sm">No items in this watchlist</p>
      ) : (
        <div className="space-y-2">
          {filteredItems.map((item, index) => {
            const sparklineData = Array.from({ length: 20 }, (_, i) => {
              const base = item.pullback_quality || 60
              const trend = item.priority_score > 0.7 ? 0.5 : item.priority_score > 0.5 ? 0.2 : -0.1
              return base + (Math.random() - 0.3) * 10 + (i * trend)
            })

            return (
              <CompactSetupCard
                key={item.symbol}
                symbol={item.symbol}
                state={getTabLabel(item.type)}
                transition="stable"
                transitionStrength={item.priority_score}
                narrative={item.narrative}
                confidence={item.priority_score}
                freshness="fresh"
                daysInState={1}
                keyMetrics={{
                  ema21: item.distance_to_ema21 !== undefined
                    ? (item.distance_to_ema21 >= 0 ? `+${item.distance_to_ema21.toFixed(1)}%` : `${item.distance_to_ema21.toFixed(1)}%`)
                    : 'N/A',
                  rs: item.rs_spy || 100,
                  volume: item.volume_contraction ? `-${item.volume_contraction.toFixed(0)}%` : 'N/A',
                  base: '8-week'
                }}
                isPriority={index === 0}
                sparklineData={sparklineData}
              />
            )
          })}
        </div>
      )}
    </Card>
  )
}
