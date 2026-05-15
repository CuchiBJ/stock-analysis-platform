'use client'

import { useEffect, useState } from 'react'

interface WeeklyFirstData {
  symbol: string
  name: string
  sector: string
  price: number
  weekly_tightness: number
  weekly_trend_quality: number
  weeks_in_base: number
  weekly_volatility_contraction: number
  perf_1w: number
  perf_4w: number
  perf_13w: number
  dist_high_52w: number
  setup_quality: string
}

export default function WeeklyFirstVisuals() {
  const [stocks, setStocks] = useState<WeeklyFirstData[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedStock, setSelectedStock] = useState<string | null>(null)

  useEffect(() => {
    async function fetchWeeklyData() {
      try {
        const response = await fetch('/api/v1/pullbacks/quality/?min_score=50&limit=30')
        const data = await response.json()
        setStocks(data)
      } catch (error) {
        console.error('Error fetching weekly first data:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchWeeklyData()
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
    if (quality >= 0.7) return 'bg-green-500'
    if (quality >= 0.5) return 'bg-blue-500'
    if (quality >= 0.3) return 'bg-yellow-500'
    return 'bg-red-500'
  }

  const formatNumber = (num: number, decimals: number = 2) => {
    return num.toFixed(decimals)
  }

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow p-4">
        <div className="animate-pulse space-y-3">
          <div className="h-4 bg-gray-200 rounded w-1/4"></div>
          <div className="grid grid-cols-4 gap-2">
            {[...Array(8)].map((_, i) => (
              <div key={i} className="h-24 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <div className="p-4 border-b border-gray-200">
        <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Weekly-First Visuals</h3>
        <p className="text-xs text-gray-500 mt-1">Mini charts priorizando estructura semanal no intradía</p>
      </div>

      <div className="p-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {stocks.slice(0, 8).map((stock) => (
            <div
              key={stock.symbol}
              className="border border-gray-200 rounded-lg p-3 hover:border-blue-300 cursor-pointer transition-colors"
              onClick={() => setSelectedStock(stock.symbol)}
            >
              {/* Header */}
              <div className="flex justify-between items-start mb-2">
                <div>
                  <div className="font-semibold text-gray-900 text-sm">{stock.symbol}</div>
                  <div className="text-xs text-gray-500">{stock.sector}</div>
                </div>
                <span className={`px-2 py-1 rounded text-[10px] font-medium border ${getSetupQualityColor(stock.setup_quality)}`}>
                  {stock.setup_quality}
                </span>
              </div>

              {/* Weekly Trend Indicator */}
              <div className="mb-2">
                <div className="flex items-center justify-between text-xs text-gray-600 mb-1">
                  <span>Weekly Trend</span>
                  <span>{(stock.weekly_trend_quality * 100).toFixed(0)}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className={`h-2 rounded-full transition-all ${getWeeklyTrendColor(stock.weekly_trend_quality)}`}
                    style={{ width: `${stock.weekly_trend_quality * 100}%` }}
                  ></div>
                </div>
              </div>

              {/* Weekly Structure Metrics */}
              <div className="space-y-1 text-xs">
                <div className="flex justify-between">
                  <span className="text-gray-500">Weekly Tight:</span>
                  <span className="text-gray-700">{(stock.weekly_tightness * 100).toFixed(0)}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Weeks in Base:</span>
                  <span className="text-gray-700">{stock.weeks_in_base}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Vol Contraction:</span>
                  <span className="text-gray-700">{stock.weekly_volatility_contraction !== null && stock.weekly_volatility_contraction !== undefined ? (stock.weekly_volatility_contraction > 0 ? '+' : '') + formatNumber(stock.weekly_volatility_contraction * 100) + '%' : 'N/A'}</span>
                </div>
              </div>

              {/* Performance */}
              <div className="mt-2 pt-2 border-t border-gray-100 grid grid-cols-3 gap-1 text-xs">
                <div className="text-center">
                  <div className="text-gray-500">1W</div>
                  <div className={`font-semibold ${stock.perf_1w >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {stock.perf_1w.toFixed(1)}%
                  </div>
                </div>
                <div className="text-center">
                  <div className="text-gray-500">4W</div>
                  <div className={`font-semibold ${stock.perf_4w >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {stock.perf_4w?.toFixed(1) || 'N/A'}%
                  </div>
                </div>
                <div className="text-center">
                  <div className="text-gray-500">13W</div>
                  <div className={`font-semibold ${stock.perf_13w >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {stock.perf_13w?.toFixed(1) || 'N/A'}%
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {stocks.length === 0 && (
          <div className="text-center py-8 text-gray-500">
            No weekly structure data available
          </div>
        )}
      </div>
    </div>
  )
}
