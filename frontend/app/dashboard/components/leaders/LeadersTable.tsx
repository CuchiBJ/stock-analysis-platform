'use client'

import { useState } from 'react'
import { LeadersTableProps } from './types'
import StockRow from './StockRow'
import Card from '@/components/base/Card'
import LoadingSkeleton from '@/components/base/LoadingSkeleton'
import { useLeaders } from '@/lib/hooks/useLeaders'
import { TrendingUp, Activity, Flame, Zap, ArrowUp, ArrowDown } from 'lucide-react'

export default function LeadersTable({ loading, limit = 50 }: LeadersTableProps) {
  const [sortBy, setSortBy] = useState<'score' | 'gain' | 'rvol' | 'rs_rank' | 'persistence'>('score')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc')
  const { data, isLoading } = useLeaders(limit, sortBy)

  const handleSort = (field: typeof sortBy) => {
    if (sortBy === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(field)
      setSortDirection('desc')
    }
  }

  if (isLoading || loading) {
    return (
      <Card className="p-4">
        <div className="space-y-2">
          {[...Array(8)].map((_, i) => (
            <LoadingSkeleton key={i} variant="card" />
          ))}
        </div>
      </Card>
    )
  }

  if (!data || data.length === 0) {
    return (
      <Card className="p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Leaders</h3>
        </div>
        <p className="text-muted-foreground text-sm">No leaders data available</p>
      </Card>
    )
  }

  const sortedData = [...data].sort((a, b) => {
    const aVal = a[sortBy as keyof typeof a] as number
    const bVal = b[sortBy as keyof typeof b] as number
    const direction = sortDirection === 'asc' ? 1 : -1
    return (aVal > bVal ? 1 : -1) * direction
  })

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Leaders</h3>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">{data.length} stocks</span>
          <div className="flex gap-1">
            {['score', 'gain', 'rvol', 'rs_rank'].map((field) => (
              <button
                key={field}
                onClick={() => handleSort(field as any)}
                className={`px-2 py-1 text-[10px] uppercase tracking-wide rounded border transition-all ${sortBy === field
                    ? 'bg-primary/10 border-primary text-primary font-medium'
                    : 'bg-transparent border-border text-muted-foreground hover:bg-muted'
                  }`}
              >
                {field.replace('_', ' ')}
                {sortBy === field && (sortDirection === 'asc' ? ' ↑' : ' ↓')}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Terminal-style Header */}
      <div className="grid grid-cols-12 gap-2 px-2 py-2 text-[10px] font-semibold text-muted-foreground border-b border-border bg-muted/30 sticky top-0">
        <div className="col-span-1 cursor-pointer hover:text-foreground" onClick={() => handleSort('gain')}>Ticker</div>
        <div className="col-span-2">Sector</div>
        <div className="col-span-1 text-right cursor-pointer hover:text-foreground" onClick={() => handleSort('gain')}>% Day</div>
        <div className="col-span-1 text-right cursor-pointer hover:text-foreground" onClick={() => handleSort('rvol')}>RVOL</div>
        <div className="col-span-1 text-right cursor-pointer hover:text-foreground" onClick={() => handleSort('rs_rank')}>RS</div>
        <div className="col-span-1 text-right cursor-pointer hover:text-foreground" onClick={() => handleSort('score')}>Score</div>
        <div className="col-span-2 text-right">Volume</div>
        <div className="col-span-1 text-right">Dist ATH</div>
        <div className="col-span-1 text-right">Float</div>
        <div className="col-span-2 text-center">Badges</div>
      </div>

      {/* Body with hover effects */}
      <div className="max-h-[500px] overflow-y-auto">
        {sortedData.map((stock, index) => (
          <StockRow key={stock.symbol} stock={stock} index={index} />
        ))}
      </div>
    </Card>
  )
}
