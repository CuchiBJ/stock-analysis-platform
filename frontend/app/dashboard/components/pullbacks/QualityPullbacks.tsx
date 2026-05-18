'use client'

import { useQuery } from '@tanstack/react-query'

interface QualityPullback {
  symbol: string
  name: string
  sector: string
  price: number
  pullback_quality_score: number
  setup_quality: string
  dist_ema9: number
  dist_ema21: number
  dist_ath: number
  weekly_tightness: number
  weekly_trend_quality: number
  volume_contraction: number
  weeks_in_base: number
  rs_spy: number | null
  perf_1w: number
  avg_volume_10d: number
}

export default function QualityPullbacks() {
  const { data: stocks = [], isLoading, error } = useQuery({
    queryKey: ['quality-pullbacks'],
    queryFn: async () => {
      const response = await fetch('http://localhost:8000/api/v1/pullbacks/quality/?limit=25')
      if (!response.ok) {
        throw new Error('Failed to fetch quality pullbacks')
      }
      return response.json() as Promise<QualityPullback[]>
    },
    refetchInterval: 60000, // Auto-refresh every 60 seconds
  })

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

  if (isLoading) {
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
        <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Quality Pullbacks</h3>
        <p className="text-xs text-gray-500 mt-1">Líderes en pullback sano cerca de EMA9/21 con RS fuerte</p>
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
              <th className="px-3 py-2 text-right font-medium text-gray-600">ATH</th>
              <th className="px-3 py-2 text-right font-medium text-gray-600">RS</th>
              <th className="px-3 py-2 text-right font-medium text-gray-600">Vol</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {stocks.map((pullback) => (
              <tr
                key={pullback.symbol}
                className="hover:bg-gray-50 transition-colors duration-200 cursor-pointer group"
              >
                <td className="px-3 py-2">
                  <div className="font-semibold text-gray-900 group-hover:text-blue-600 transition-colors duration-200">{pullback.symbol}</div>
                  <div className="text-xs text-gray-500 truncate max-w-[120px]">{pullback.name}</div>
                </td>
                <td className="px-3 py-2">
                  <span className="text-xs text-gray-600">{pullback.sector}</span>
                </td>
                <td className="px-3 py-2 text-right">
                  <span className={`font-semibold ${getPullbackScoreColor(pullback.pullback_quality_score)}`}>
                    {pullback.pullback_quality_score.toFixed(1)}
                  </span>
                </td>
                <td className="px-3 py-2 text-right">
                  <span className={`px-2 py-1 rounded text-xs font-medium border ${getSetupQualityColor(pullback.setup_quality)}`}>
                    {pullback.setup_quality}
                  </span>
                </td>
                <td className="px-3 py-2 text-right text-gray-700">
                  {pullback.dist_ema9 > 0 ? '+' : ''}{formatNumber(pullback.dist_ema9)}%
                </td>
                <td className="px-3 py-2 text-right text-gray-700">
                  {pullback.dist_ema21 > 0 ? '+' : ''}{formatNumber(pullback.dist_ema21)}%
                </td>
                <td className="px-3 py-2 text-right text-gray-700">
                  {formatNumber(pullback.dist_ath)}%
                </td>
                <td className="px-3 py-2 text-right text-gray-700">
                  {formatNumber(pullback.rs_spy)}
                </td>
                <td className="px-3 py-2 text-right text-gray-700">
                  {(pullback.avg_volume_10d / 1000).toFixed(0)}K
                </td>
              </tr>
            ))}
            {stocks.length === 0 && (
              <tr>
                <td colSpan={9} className="px-3 py-8 text-center text-gray-500">
                  No quality pullbacks found with current criteria
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
