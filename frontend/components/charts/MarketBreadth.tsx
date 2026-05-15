'use client'

import { useEffect, useState } from 'react'

interface BreadthData {
  above_ema20: number
  above_ema50: number
  new_highs: number
  new_lows: number
  advancers: number
  decliners: number
}

export default function MarketBreadth() {
  const [data, setData] = useState<BreadthData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Fetch breadth data
    fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/sectors/breadth`)
      .then(res => res.json())
      .then(data => {
        setData(data)
        setLoading(false)
      })
      .catch(err => {
        console.error('Error fetching breadth data:', err)
        setLoading(false)
      })
  }, [])

  if (loading) {
    return (
      <div className="bg-card border border-border rounded-lg p-6">
        <h2 className="text-xl font-bold mb-4">Market Breadth</h2>
        <div className="text-muted-foreground">Loading...</div>
      </div>
    )
  }

  const getBarColor = (value: number, threshold: number) => {
    if (value > threshold) return 'bg-green-500'
    if (value < threshold / 2) return 'bg-red-500'
    return 'bg-yellow-500'
  }

  return (
    <div className="bg-card border border-border rounded-lg p-6">
      <h2 className="text-xl font-bold mb-4">Market Breadth</h2>

      <div className="space-y-4">
        {/* Above EMA20 */}
        <div>
          <div className="flex justify-between text-sm mb-1">
            <span className="text-muted-foreground">Above EMA20</span>
            <span className="font-bold">{data?.above_ema20 || 0}%</span>
          </div>
          <div className="h-3 bg-muted rounded-full overflow-hidden">
            <div
              className={`h-full ${getBarColor(data?.above_ema20 || 0, 50)} transition-all`}
              style={{ width: `${data?.above_ema20 || 0}%` }}
            />
          </div>
        </div>

        {/* Above EMA50 */}
        <div>
          <div className="flex justify-between text-sm mb-1">
            <span className="text-muted-foreground">Above EMA50</span>
            <span className="font-bold">{data?.above_ema50 || 0}%</span>
          </div>
          <div className="h-3 bg-muted rounded-full overflow-hidden">
            <div
              className={`h-full ${getBarColor(data?.above_ema50 || 0, 50)} transition-all`}
              style={{ width: `${data?.above_ema50 || 0}%` }}
            />
          </div>
        </div>

        {/* New Highs/Lows */}
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-muted p-3 rounded">
            <div className="text-sm text-muted-foreground">52-Week Highs</div>
            <div className="text-2xl font-bold text-green-500">{data?.new_highs || 0}</div>
          </div>
          <div className="bg-muted p-3 rounded">
            <div className="text-sm text-muted-foreground">52-Week Lows</div>
            <div className="text-2xl font-bold text-red-500">{data?.new_lows || 0}</div>
          </div>
        </div>

        {/* Advancers/Decliners */}
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-muted p-3 rounded">
            <div className="text-sm text-muted-foreground">Advancers</div>
            <div className="text-2xl font-bold text-green-500">{data?.advancers || 0}</div>
          </div>
          <div className="bg-muted p-3 rounded">
            <div className="text-sm text-muted-foreground">Decliners</div>
            <div className="text-2xl font-bold text-red-500">{data?.decliners || 0}</div>
          </div>
        </div>
      </div>
    </div>
  )
}
