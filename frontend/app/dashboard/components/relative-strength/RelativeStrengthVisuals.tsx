'use client'

import { useEffect, useState } from 'react'

interface RSStock {
  symbol: string
  name: string
  sector: string
  price: number
  perf_1w: number
  perf_4w: number
  perf_13w: number
  perf_1y: number
  weekly_trend_quality: number
  pullback_quality_score: number
  distance_to_high_52w: number
}

export default function RelativeStrengthVisuals() {
  const [stocks, setStocks] = useState<RSStock[]>([])
  const [loading, setLoading] = useState(true)
  const [timeframe, setTimeframe] = useState<'1w' | '4w' | '13w' | '1y'>('1y')

  useEffect(() => {
    async function fetchRSData() {
      setLoading(true)
      try {
        const response = await fetch('/api/v1/pullbacks/quality/?min_score=50&limit=50')
        const data = await response.json()
        setStocks(data)
      } catch (error) {
        console.error('Error fetching relative strength data:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchRSData()
  }, [])

  const getPerformanceColor = (value: number) => {
    if (value > 0) return 'text-green-600'
    if (value < 0) return 'text-red-600'
    return 'text-gray-600'
  }

  const getPerformanceBgColor = (value: number) => {
    if (value > 10) return 'bg-green-50 border-green-200'
    if (value > 0) return 'bg-green-50/50 border-green-200/50'
    if (value > -10) return 'bg-red-50/50 border-red-200/50'
    return 'bg-red-50 border-red-200'
  }

  const getPerformanceMetric = (stock: RSStock) => {
    switch (timeframe) {
      case '1w': return stock.perf_1w
      case '4w': return stock.perf_4w || 0
      case '13w': return stock.perf_13w || 0
      case '1y': return stock.perf_1y || 0
      default: return 0
    }
  }

  const sortedStocks = [...stocks].sort((a, b) => getPerformanceMetric(b) - getPerformanceMetric(a))

  const formatNumber = (num: number) => {
    if (num === null || num === undefined) return 'N/A'
    return num.toFixed(1)
  }

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow p-4">
        <div className="animate-pulse space-y-3">
          <div className="h-4 bg-gray-200 rounded w-1/4"></div>
          <div className="space-y-2">
            {[...Array(10)].map((_, i) => (
              <div key={i} className="h-12 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <div className="p-4 border-b border-gray-200">
        <div className="flex justify-between items-center">
          <div>
            <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Relative Strength</h3>
            <p className="text-xs text-gray-500 mt-1">Performance vs market benchmarks (using available metrics)</p>
          </div>
          <div className="flex gap-2">
            {(['1w', '4w', '13w', '1y'] as const).map((tf) => (
              <button
                key={tf}
                onClick={() => setTimeframe(tf)}
                className={`px-3 py-1 text-xs font-medium rounded border ${
                  timeframe === tf
                    ? 'bg-blue-500 text-white border-blue-500'
                    : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'
                }`}
              >
                {tf.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
      </div>
      
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-3 py-2 text-left font-medium text-gray-600">Ticker</th>
              <th className="px-3 py-2 text-left font-medium text-gray-600">Sector</th>
              <th className="px-3 py-2 text-right font-medium text-gray-600">1W</th>
              <th className="px-3 py-2 text-right font-medium text-gray-600">4W</th>
              <th className="px-3 py-2 text-right font-medium text-gray-600">13W</th>
              <th className="px-3 py-2 text-right font-medium text-gray-600">1Y</th>
              <th className="px-3 py-2 text-right font-medium text-gray-600">Weekly Trend</th>
              <th className="px-3 py-2 text-right font-medium text-gray-600">Dist ATH</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {sortedStocks.map((stock, index) => (
              <tr 
                key={stock.symbol} 
                className={`hover:bg-gray-50 ${getPerformanceBgColor(getPerformanceMetric(stock))}`}
              >
                <td className="px-3 py-2">
                  <div className="font-semibold text-gray-900">{stock.symbol}</div>
                  <div className="text-xs text-gray-500 truncate max-w-[120px]">{stock.name}</div>
                </td>
                <td className="px-3 py-2">
                  <span className="text-xs text-gray-600">{stock.sector}</span>
                </td>
                <td className={`px-3 py-2 text-right font-medium ${getPerformanceColor(stock.perf_1w)}`}>
                  {formatNumber(stock.perf_1w)}%
                </td>
                <td className={`px-3 py-2 text-right font-medium ${getPerformanceColor(stock.perf_4w || 0)}`}>
                  {formatNumber(stock.perf_4w || 0)}%
                </td>
                <td className={`px-3 py-2 text-right font-medium ${getPerformanceColor(stock.perf_13w || 0)}`}>
                  {formatNumber(stock.perf_13w || 0)}%
                </td>
                <td className={`px-3 py-2 text-right font-medium ${getPerformanceColor(stock.perf_1y || 0)}`}>
                  {formatNumber(stock.perf_1y || 0)}%
                </td>
                <td className="px-3 py-2 text-right text-gray-700">
                  {(stock.weekly_trend_quality * 100).toFixed(0)}%
                </td>
                <td className="px-3 py-2 text-right text-gray-700">
                  {formatNumber(stock.distance_to_high_52w)}%
                </td>
              </tr>
            ))}
            {stocks.length === 0 && (
              <tr>
                <td colSpan={8} className="px-3 py-8 text-center text-gray-500">
                  No relative strength data available
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
