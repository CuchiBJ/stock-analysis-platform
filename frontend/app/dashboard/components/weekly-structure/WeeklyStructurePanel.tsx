'use client'

import { useEffect, useState } from 'react'
import Card from '@/components/base/Card'

interface WeeklyStructure {
  symbol: string
  name: string
  sector: string
  price: number
  weekly_tightness: number
  weekly_volatility_contraction: number
  weekly_trend_quality: number
  weeks_in_base: number
  setup_quality: string
  pullback_quality_score: number
}

export default function WeeklyStructurePanel() {
  const [stocks, setStocks] = useState<WeeklyStructure[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function fetchWeeklyStructure() {
      try {
        // Reuse the quality pullbacks endpoint as it has weekly structure metrics
        const response = await fetch('http://localhost:8000/api/v1/pullbacks/quality/?min_score=50&limit=30')
        const data = await response.json()
        setStocks(data)
      } catch (error) {
        console.error('Error fetching weekly structure:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchWeeklyStructure()
  }, [])

  const getSetupQualityColor = (quality: string) => {
    switch (quality) {
      case 'excellent': return 'bg-green-100 text-green-800 border-green-300'
      case 'good': return 'bg-blue-100 text-blue-800 border-blue-300'
      case 'fair': return 'bg-yellow-100 text-yellow-800 border-yellow-300'
      case 'developing': return 'bg-orange-100 text-orange-800 border-orange-300'
      case 'poor': return 'bg-red-100 text-red-800 border-red-300'
      default: return 'bg-gray-100 text-gray-800 border-gray-300'
    }
  }

  const getWeeklyTrendColor = (quality: number) => {
    if (quality >= 0.7) return 'text-green-600'
    if (quality >= 0.5) return 'text-blue-600'
    if (quality >= 0.3) return 'text-yellow-600'
    return 'text-red-600'
  }

  const formatNumber = (num: number, decimals: number = 2) => {
    return num.toFixed(decimals)
  }

  if (loading) {
    return (
      <Card blockType="structure">
        <div className="animate-pulse space-y-3">
          <div className="h-4 bg-gray-200 rounded w-1/4"></div>
          <div className="space-y-2">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-12 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      </Card>
    )
  }

  return (
    <Card blockType="structure">
      <div className="p-4 border-b border-border">
        <h3 className="text-sm font-semibold text-foreground uppercase tracking-wide">Weekly Structure Panel</h3>
        <p className="text-xs text-foreground/70 mt-1">Semanas consolidando, tight weekly closes, volatility contraction</p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-muted">
            <tr>
              <th className="px-3 py-2 text-left font-medium text-foreground">Ticker</th>
              <th className="px-3 py-2 text-left font-medium text-foreground">Sector</th>
              <th className="px-3 py-2 text-right font-medium text-foreground">Setup</th>
              <th className="px-3 py-2 text-right font-medium text-foreground">Weekly Tight</th>
              <th className="px-3 py-2 text-right font-medium text-foreground">Vol Contraction</th>
              <th className="px-3 py-2 text-right font-medium text-foreground">Weekly Trend</th>
              <th className="px-3 py-2 text-right font-medium text-foreground">Weeks in Base</th>
              <th className="px-3 py-2 text-right font-medium text-foreground">Score</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {stocks.map((stock) => (
              <tr key={stock.symbol} className="hover:bg-muted/50">
                <td className="px-3 py-2">
                  <div className="font-semibold text-foreground">{stock.symbol}</div>
                  <div className="text-xs text-foreground/70 truncate max-w-[120px]">{stock.name}</div>
                </td>
                <td className="px-3 py-2">
                  <span className="text-xs text-foreground/80">{stock.sector}</span>
                </td>
                <td className="px-3 py-2 text-right">
                  <span className={`px-2 py-1 rounded text-xs font-medium border ${getSetupQualityColor(stock.setup_quality)}`}>
                    {stock.setup_quality}
                  </span>
                </td>
                <td className="px-3 py-2 text-right text-foreground">
                  {(stock.weekly_tightness * 100).toFixed(0)}%
                </td>
                <td className="px-3 py-2 text-right text-foreground">
                  {stock.weekly_volatility_contraction > 0 ? '+' : ''}{formatNumber(stock.weekly_volatility_contraction * 100)}%
                </td>
                <td className="px-3 py-2 text-right">
                  <span className={`font-semibold ${getWeeklyTrendColor(stock.weekly_trend_quality)}`}>
                    {(stock.weekly_trend_quality * 100).toFixed(0)}%
                  </span>
                </td>
                <td className="px-3 py-2 text-right text-foreground">
                  {stock.weeks_in_base}
                </td>
                <td className="px-3 py-2 text-right text-foreground">
                  {stock.pullback_quality_score.toFixed(1)}
                </td>
              </tr>
            ))}
            {stocks.length === 0 && (
              <tr>
                <td colSpan={8} className="px-3 py-8 text-center text-foreground/70">
                  No stocks with strong weekly structure found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </Card>
  )
}
