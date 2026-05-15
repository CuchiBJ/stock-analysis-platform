'use client'

import { useEffect, useState } from 'react'

interface LeaderUnderPressure {
  symbol: string
  name: string
  sector: string
  price: number
  weekly_trend_quality: number
  dist_ath: number
  perf_1w: number
  setup_quality: string
  relative_volume: number
  avg_volume_10d: number
  pullback_quality_score: number
  dist_ema9: number
  dist_ema21: number
  rs_spy: number | null
}

export default function LeadersUnderPressure() {
  const [stocks, setStocks] = useState<LeaderUnderPressure[]>([])
  const [loading, setLoading] = useState(true)
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date())

  const fetchData = async () => {
    try {
      const response = await fetch('/api/v1/pullbacks/leaders-under-pressure/?limit=20')
      const data = await response.json()
      setStocks(data)
      setLastUpdated(new Date())
    } catch (error) {
      console.error('Error fetching leaders under pressure:', error)
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

  const getPullbackScoreColor = (score: number) => {
    if (score >= 70) return 'text-green-600'
    if (score >= 60) return 'text-blue-600'
    if (score >= 50) return 'text-yellow-600'
    return 'text-red-600'
  }

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
        <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Leaders Under Pressure</h3>
        <p className="text-xs text-gray-500 mt-1">Estructuralmente fuertes corrigiendo ordenadamente cerca de zonas de entrada</p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-3 py-2 text-left font-medium text-gray-600">Ticker</th>
              <th className="px-3 py-2 text-left font-medium text-gray-600">Sector</th>
              <th className="px-3 py-2 text-right font-medium text-gray-600">Score</th>
              <th className="px-3 py-2 text-right font-medium text-gray-600">Setup</th>
              <th className="px-3 py-2 text-right font-medium text-gray-600">EMA9</th>
              <th className="px-3 py-2 text-right font-medium text-gray-600">EMA21</th>
              <th className="px-3 py-2 text-right font-medium text-gray-600">Weekly</th>
              <th className="px-3 py-2 text-right font-medium text-gray-600">Perf 1W</th>
              <th className="px-3 py-2 text-right font-medium text-gray-600">RS</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {stocks.map((leader) => (
              <tr key={leader.symbol} className="hover:bg-gray-50">
                <td className="px-3 py-2">
                  <div className="font-semibold text-gray-900">{leader.symbol}</div>
                  <div className="text-xs text-gray-500 truncate max-w-[120px]">{leader.name}</div>
                </td>
                <td className="px-3 py-2">
                  <span className="text-xs text-gray-600">{leader.sector}</span>
                </td>
                <td className="px-3 py-2 text-right">
                  <span className={`font-semibold ${getPullbackScoreColor(leader.pullback_quality_score)}`}>
                    {leader.pullback_quality_score.toFixed(1)}
                  </span>
                </td>
                <td className="px-3 py-2 text-right">
                  <span className={`px-2 py-1 rounded text-xs font-medium border ${getSetupQualityColor(leader.setup_quality)}`}>
                    {leader.setup_quality}
                  </span>
                </td>
                <td className="px-3 py-2 text-right text-gray-700">
                  {leader.dist_ema9 > 0 ? '+' : ''}{formatNumber(leader.dist_ema9)}%
                </td>
                <td className="px-3 py-2 text-right text-gray-700">
                  {leader.dist_ema21 > 0 ? '+' : ''}{formatNumber(leader.dist_ema21)}%
                </td>
                <td className="px-3 py-2 text-right text-gray-700">
                  {(leader.weekly_trend_quality * 100).toFixed(0)}%
                </td>
                <td className="px-3 py-2 text-right text-red-600">
                  {leader.perf_1w.toFixed(1)}%
                </td>
                <td className="px-3 py-2 text-right text-gray-700">
                  {formatNumber(leader.rs_spy)}
                </td>
              </tr>
            ))}
            {stocks.length === 0 && (
              <tr>
                <td colSpan={9} className="px-3 py-8 text-center text-gray-500">
                  No leaders under pressure found with current criteria
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
