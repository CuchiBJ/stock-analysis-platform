'use client'

import { useEffect, useState } from 'react'

interface EarlyReclaim {
  symbol: string
  name: string
  sector: string
  price: number
  dist_ema9: number
  dist_ema21: number
  perf_1w: number
  relative_volume: number
  weekly_trend_quality: number
  avg_volume_10d: number
  rs_spy: number | null
}

export default function EarlyReclaims() {
  const [stocks, setStocks] = useState<EarlyReclaim[]>([])
  const [loading, setLoading] = useState(true)
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date())

  const fetchData = async () => {
    try {
      const response = await fetch('/api/v1/pullbacks/early-reclaims/?limit=20')
      const data = await response.json()
      setStocks(data)
      setLastUpdated(new Date())
    } catch (error) {
      console.error('Error fetching early reclaims:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    // Auto-refresh every 60 seconds
    const interval = setInterval(fetchData, 60000)
    return () => clearInterval(interval)
  }, [])

  const formatNumber = (num: number | null, decimals: number = 2) => {
    if (num === null) return 'N/A'
    return num.toFixed(decimals)
  }

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow p-4">
        <div className="animate-pulse space-y-3">
          <div className="h-4 bg-gray-200 rounded w-1/4"></div>
          <div className="space-y-2">
            {[...Array(5)].map((_, i) => (
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
        <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Early Reclaims</h3>
        <p className="text-xs text-gray-500 mt-1">Pérdida breve EMA9/21 con recuperación rápida y volumen comprador</p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-3 py-2 text-left font-medium text-gray-600">Ticker</th>
              <th className="px-3 py-2 text-left font-medium text-gray-600">Sector</th>
              <th className="px-3 py-2 text-right font-medium text-gray-600">EMA9</th>
              <th className="px-3 py-2 text-right font-medium text-gray-600">EMA21</th>
              <th className="px-3 py-2 text-right font-medium text-gray-600">Perf 1W</th>
              <th className="px-3 py-2 text-right font-medium text-gray-600">RVOL</th>
              <th className="px-3 py-2 text-right font-medium text-gray-600">Weekly</th>
              <th className="px-3 py-2 text-right font-medium text-gray-600">RS</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {stocks.map((reclaim) => (
              <tr key={reclaim.symbol} className="hover:bg-gray-50">
                <td className="px-3 py-2">
                  <div className="font-semibold text-gray-900">{reclaim.symbol}</div>
                  <div className="text-xs text-gray-500 truncate max-w-[120px]">{reclaim.name}</div>
                </td>
                <td className="px-3 py-2">
                  <span className="text-xs text-gray-600">{reclaim.sector}</span>
                </td>
                <td className="px-3 py-2 text-right text-gray-700">
                  {reclaim.dist_ema9 > 0 ? '+' : ''}{formatNumber(reclaim.dist_ema9)}%
                </td>
                <td className="px-3 py-2 text-right text-gray-700">
                  {reclaim.dist_ema21 > 0 ? '+' : ''}{formatNumber(reclaim.dist_ema21)}%
                </td>
                <td className="px-3 py-2 text-right text-green-600">
                  +{reclaim.perf_1w.toFixed(1)}%
                </td>
                <td className="px-3 py-2 text-right text-green-600">
                  {reclaim.relative_volume.toFixed(1)}x
                </td>
                <td className="px-3 py-2 text-right text-gray-700">
                  {(reclaim.weekly_trend_quality * 100).toFixed(0)}%
                </td>
                <td className="px-3 py-2 text-right text-gray-700">
                  {formatNumber(reclaim.rs_spy)}
                </td>
              </tr>
            ))}
            {stocks.length === 0 && (
              <tr>
                <td colSpan={8} className="px-3 py-8 text-center text-gray-500">
                  No early reclaims found with current criteria
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
