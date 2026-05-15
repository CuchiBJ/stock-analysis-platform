'use client'

import { useEffect, useState } from 'react'

interface MarketEnvironment {
  pullback_environment_healthy: boolean
  continuation_environment: boolean
  healthy_leadership: boolean
  quality_pullbacks_count: number
  leaders_under_pressure_count: number
  early_reclaims_count: number
  avg_pullback_quality_score: number
  avg_weekly_trend_quality: number
}

export default function MarketEnvironmentPanel() {
  const [environment, setEnvironment] = useState<MarketEnvironment | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function fetchMarketEnvironment() {
      try {
        // Fetch data from multiple endpoints to calculate environment
        const [qualityRes, leadersRes, reclaimsRes] = await Promise.all([
          fetch('/api/v1/pullbacks/quality/?min_score=60&limit=100'),
          fetch('/api/v1/pullbacks/leaders-under-pressure/?limit=100'),
          fetch('/api/v1/pullbacks/early-reclaims/?limit=100')
        ])

        const qualityData = await qualityRes.json()
        const leadersData = await leadersRes.json()
        const reclaimsData = await reclaimsRes.json()

        // Calculate environment metrics
        const avgPullbackScore = qualityData.length > 0 
          ? qualityData.reduce((sum: number, item: any) => sum + item.pullback_quality_score, 0) / qualityData.length
          : 0

        const avgWeeklyTrend = qualityData.length > 0
          ? qualityData.reduce((sum: number, item: any) => sum + item.weekly_trend_quality, 0) / qualityData.length
          : 0

        // Determine environment health based on counts and scores
        const pullbackEnvironmentHealthy = qualityData.length >= 20 && avgPullbackScore >= 60
        const continuationEnvironment = leadersData.length >= 15 && avgWeeklyTrend >= 0.5
        const healthyLeadership = qualityData.length >= 25 && avgWeeklyTrend >= 0.55

        setEnvironment({
          pullback_environment_healthy: pullbackEnvironmentHealthy,
          continuation_environment: continuationEnvironment,
          healthy_leadership: healthyLeadership,
          quality_pullbacks_count: qualityData.length,
          leaders_under_pressure_count: leadersData.length,
          early_reclaims_count: reclaimsData.length,
          avg_pullback_quality_score: avgPullbackScore,
          avg_weekly_trend_quality: avgWeeklyTrend
        })
      } catch (error) {
        console.error('Error fetching market environment:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchMarketEnvironment()
  }, [])

  const getStatusColor = (healthy: boolean) => {
    return healthy ? 'bg-green-100 text-green-800 border-green-300' : 'bg-red-100 text-red-800 border-red-300'
  }

  const getStatusText = (healthy: boolean) => {
    return healthy ? 'HEALTHY' : 'UNHEALTHY'
  }

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow p-4">
        <div className="animate-pulse space-y-3">
          <div className="h-4 bg-gray-200 rounded w-1/3"></div>
          <div className="space-y-2">
            <div className="h-16 bg-gray-200 rounded"></div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <div className="p-4 border-b border-gray-200">
        <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Market Environment</h3>
        <p className="text-xs text-gray-500 mt-1">Pullback environment healthy, continuation environment, healthy leadership</p>
      </div>
      
      <div className="p-4 space-y-4">
        {/* Environment Indicators */}
        <div className="grid grid-cols-3 gap-4">
          <div className="text-center">
            <div className={`px-3 py-2 rounded-lg border ${getStatusColor(environment?.pullback_environment_healthy || false)}`}>
              <div className="text-xs font-semibold">{getStatusText(environment?.pullback_environment_healthy || false)}</div>
              <div className="text-[10px] text-gray-600 mt-1">Pullback Env</div>
            </div>
          </div>
          <div className="text-center">
            <div className={`px-3 py-2 rounded-lg border ${getStatusColor(environment?.continuation_environment || false)}`}>
              <div className="text-xs font-semibold">{getStatusText(environment?.continuation_environment || false)}</div>
              <div className="text-[10px] text-gray-600 mt-1">Continuation</div>
            </div>
          </div>
          <div className="text-center">
            <div className={`px-3 py-2 rounded-lg border ${getStatusColor(environment?.healthy_leadership || false)}`}>
              <div className="text-xs font-semibold">{getStatusText(environment?.healthy_leadership || false)}</div>
              <div className="text-[10px] text-gray-600 mt-1">Leadership</div>
            </div>
          </div>
        </div>

        {/* Metrics */}
        <div className="grid grid-cols-2 gap-4 pt-4 border-t border-gray-100">
          <div>
            <div className="text-xs text-gray-500 mb-1">Quality Pullbacks</div>
            <div className="text-2xl font-bold text-gray-900">{environment?.quality_pullbacks_count || 0}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Leaders Under Pressure</div>
            <div className="text-2xl font-bold text-gray-900">{environment?.leaders_under_pressure_count || 0}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Early Reclaims</div>
            <div className="text-2xl font-bold text-gray-900">{environment?.early_reclaims_count || 0}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Avg Pullback Score</div>
            <div className="text-2xl font-bold text-gray-900">{environment?.avg_pullback_quality_score.toFixed(1) || 0}</div>
          </div>
        </div>

        {/* Weekly Trend Quality */}
        <div className="pt-4 border-t border-gray-100">
          <div className="text-xs text-gray-500 mb-1">Avg Weekly Trend Quality</div>
          <div className="flex items-center gap-2">
            <div className="flex-1 bg-gray-200 rounded-full h-2">
              <div 
                className="bg-blue-600 h-2 rounded-full transition-all" 
                style={{ width: `${(environment?.avg_weekly_trend_quality || 0) * 100}%` }}
              ></div>
            </div>
            <span className="text-sm font-semibold text-gray-900">{((environment?.avg_weekly_trend_quality || 0) * 100).toFixed(0)}%</span>
          </div>
        </div>
      </div>
    </div>
  )
}
