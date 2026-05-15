'use client'

import { useEffect, useState } from 'react'

interface QualitySwingSetup {
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
  rs_spy: number
  perf_1w: number
  avg_volume_10d: number
}

export default function QualitySwingScanner() {
  const [setups, setSetups] = useState<QualitySwingSetup[]>([])
  const [loading, setLoading] = useState(true)
  const [minScore, setMinScore] = useState(60)
  const [maxDistanceEma9, setMaxDistanceEma9] = useState(5)
  const [maxDistanceEma21, setMaxDistanceEma21] = useState(8)
  const [maxDistanceAth, setMaxDistanceAth] = useState(-15)

  useEffect(() => {
    async function fetchSetups() {
      setLoading(true)
      try {
        const response = await fetch(
          `/api/v1/quality-swing-scanner/?min_score=${minScore}&max_distance_ema9=${maxDistanceEma9}&max_distance_ema21=${maxDistanceEma21}&max_distance_ath=${maxDistanceAth}`
        )
        const data = await response.json()
        setSetups(data)
      } catch (error) {
        console.error('Error fetching quality swing setups:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchSetups()
  }, [minScore, maxDistanceEma9, maxDistanceEma21, maxDistanceAth])

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

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <div className="p-4 border-b border-gray-200">
        <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Quality Swing Setups Scanner</h3>
        <p className="text-xs text-gray-500 mt-1">Weekly uptrend intact, near ATH, RS strong, volume contraction</p>

        {/* Filters */}
        <div className="mt-3 grid grid-cols-2 lg:grid-cols-4 gap-2">
          <div>
            <label className="text-xs text-gray-600">Min Score: {minScore}</label>
            <input
              type="range"
              min="0"
              max="100"
              value={minScore}
              onChange={(e) => setMinScore(Number(e.target.value))}
              className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
            />
          </div>
          <div>
            <label className="text-xs text-gray-600">EMA9 ±{maxDistanceEma9}%</label>
            <input
              type="range"
              min="0"
              max="20"
              value={maxDistanceEma9}
              onChange={(e) => setMaxDistanceEma9(Number(e.target.value))}
              className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
            />
          </div>
          <div>
            <label className="text-xs text-gray-600">EMA21 ±{maxDistanceEma21}%</label>
            <input
              type="range"
              min="0"
              max="25"
              value={maxDistanceEma21}
              onChange={(e) => setMaxDistanceEma21(Number(e.target.value))}
              className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
            />
          </div>
          <div>
            <label className="text-xs text-gray-600">ATH ≥{maxDistanceAth}%</label>
            <input
              type="range"
              min="-50"
              max="0"
              value={maxDistanceAth}
              onChange={(e) => setMaxDistanceAth(Number(e.target.value))}
              className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
            />
          </div>
        </div>
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
              <th className="px-3 py-2 text-right font-medium text-gray-600">Weekly</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              [...Array(10)].map((_, i) => (
                <tr key={i}>
                  <td colSpan={9} className="px-3 py-4 text-center">
                    <div className="animate-pulse">Loading...</div>
                  </td>
                </tr>
              ))
            ) : setups.length === 0 ? (
              <tr>
                <td colSpan={9} className="px-3 py-8 text-center text-gray-500">
                  No quality swing setups found with current criteria. Try adjusting the filters.
                </td>
              </tr>
            ) : (
              setups.map((setup) => (
                <tr key={setup.symbol} className="hover:bg-gray-50">
                  <td className="px-3 py-2">
                    <div className="font-semibold text-gray-900">{setup.symbol}</div>
                    <div className="text-xs text-gray-500 truncate max-w-[120px]">{setup.name}</div>
                  </td>
                  <td className="px-3 py-2">
                    <span className="text-xs text-gray-600">{setup.sector}</span>
                  </td>
                  <td className="px-3 py-2 text-right">
                    <span className={`font-semibold ${getPullbackScoreColor(setup.pullback_quality_score)}`}>
                      {setup.pullback_quality_score.toFixed(1)}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right">
                    <span className={`px-2 py-1 rounded text-xs font-medium border ${getSetupQualityColor(setup.setup_quality)}`}>
                      {setup.setup_quality}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right text-gray-700">
                    {setup.dist_ema9 > 0 ? '+' : ''}{formatNumber(setup.dist_ema9)}%
                  </td>
                  <td className="px-3 py-2 text-right text-gray-700">
                    {setup.dist_ema21 > 0 ? '+' : ''}{formatNumber(setup.dist_ema21)}%
                  </td>
                  <td className="px-3 py-2 text-right text-gray-700">
                    {formatNumber(setup.dist_ath)}%
                  </td>
                  <td className="px-3 py-2 text-right text-gray-700">
                    {formatNumber(setup.rs_spy)}
                  </td>
                  <td className="px-3 py-2 text-right text-gray-700">
                    {(setup.weekly_trend_quality * 100).toFixed(0)}%
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
