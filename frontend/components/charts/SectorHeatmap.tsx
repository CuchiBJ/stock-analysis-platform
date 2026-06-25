'use client'

import { useEffect, useState } from 'react'
import Card from '@/components/base/Card'
import LoadingSkeleton from '@/components/base/LoadingSkeleton'
import { TrendingUp, TrendingDown, Activity, Flame, ArrowDown } from 'lucide-react'
import { API_URL } from '@/lib/utils'
import SectorConstituentsDrawer from '@/components/dashboard/SectorConstituentsDrawer'

type ViewMode = 'daily' | 'weekly' | 'monthly' | 'rs_spy' | 'momentum' | 'rvol'

// Mirror of MARKET_GROUP_TO_FAMILY in market_group_mapping.py — update both when taxonomy changes.
const MARKET_GROUP_TO_FAMILY: Record<string, string> = {
  'Electronic Technology': 'tech',
  'Technology Services': 'tech',
  'Health Technology': 'healthcare',
  'Health Services': 'healthcare',
  'Finance': 'financial',
  'Banks': 'financial',
  'Insurance': 'financial',
  'Defense': 'industrial',
  'Industrials': 'industrial',
  'Commercial Services': 'industrial',
  'Transportation': 'industrial',
  'Retail': 'consumer',
  'Consumer Cyclical': 'consumer',
  'Auto': 'consumer',
  'Consumer Staples': 'consumer',
  'Consumer Products': 'consumer',
  'Energy': 'energy',
  'Renewables': 'energy',
  'Mining & Metals': 'materials',
  'Chemicals': 'materials',
  'Building': 'materials',
  'Real Estate': 'yield',
  'Utilities': 'yield',
  'Media & Telecom': 'yield',
}

const FAMILY_BORDER_COLOR: Record<string, string> = {
  tech: 'border-l-cyan-500',
  healthcare: 'border-l-pink-500',
  financial: 'border-l-blue-500',
  industrial: 'border-l-amber-500',
  consumer: 'border-l-orange-500',
  energy: 'border-l-red-500',
  materials: 'border-l-stone-500',
  yield: 'border-l-purple-500',
}

function familyBorder(name: string): string {
  const family = MARKET_GROUP_TO_FAMILY[name]
  return family ? (FAMILY_BORDER_COLOR[family] ?? 'border-l-white/10') : 'border-l-white/10'
}

export default function SectorHeatmap() {
  const [data, setData] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>('weekly')
  const [selectedGroup, setSelectedGroup] = useState<string | null>(null)

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true)
        setError(null)
        const response = await fetch(`${API_URL}/api/v1/sectors/performance?timeframe=daily`)
        if (!response.ok) throw new Error('Failed to load sector data')
        const data = await response.json()
        setData(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load sector data')
        console.error('Error loading sector data:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
    const interval = setInterval(fetchData, 60000)
    return () => clearInterval(interval)
  }, [])

  const getValueByMode = (sector: any) => {
    switch (viewMode) {
      case 'daily': return sector.performance_weekly || 0
      case 'weekly': return sector.performance_weekly || 0
      case 'monthly': return sector.performance_monthly || 0
      case 'rs_spy': return sector.performance_vs_spy || 0
      case 'momentum': return sector.performance_weekly || 0
      case 'rvol': return sector.volume_trend === 'increasing' ? 2 : sector.volume_trend === 'decreasing' ? -1 : 0
      default: return sector.performance_weekly || 0
    }
  }

  const getColor = (value: number) => {
    if (value > 3) return { bg: 'bg-green-600', text: 'text-white' }
    if (value > 2) return { bg: 'bg-green-500', text: 'text-white' }
    if (value > 1) return { bg: 'bg-green-400', text: 'text-black' }
    if (value > 0) return { bg: 'bg-green-300', text: 'text-black' }
    if (value > -1) return { bg: 'bg-red-300', text: 'text-black' }
    if (value > -2) return { bg: 'bg-red-400', text: 'text-black' }
    if (value > -3) return { bg: 'bg-red-500', text: 'text-white' }
    return { bg: 'bg-red-600', text: 'text-white' }
  }

  const getTrendIcon = (trend: string) => {
    if (trend === 'accelerating') return <TrendingUp className="w-3 h-3" />
    if (trend === 'decelerating') return <TrendingDown className="w-3 h-3" />
    return <Activity className="w-3 h-3" />
  }

  const getStrengthColor = (strength: string) => {
    if (strength === 'strong') return 'text-green-400'
    if (strength === 'moderate') return 'text-yellow-400'
    return 'text-red-400'
  }

  const getStrengthIcon = (strength: string) => {
    if (strength === 'strong') return <Flame className="w-3 h-3" />
    if (strength === 'weak') return <ArrowDown className="w-3 h-3" />
    return <Activity className="w-3 h-3" />
  }

  const viewModeLabels: Record<ViewMode, string> = {
    daily: 'Weekly %',
    weekly: 'Weekly %',
    monthly: 'Monthly %',
    rs_spy: 'RS vs SPY',
    momentum: 'Momentum',
    rvol: 'RVOL'
  }

  if (loading) {
    return (
      <Card className="p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Sector Rotation</h3>
        </div>
        <div className="grid grid-cols-5 gap-2">
          {[...Array(25)].map((_, i) => (
            <LoadingSkeleton key={i} variant="card" />
          ))}
        </div>
      </Card>
    )
  }

  if (error) {
    return (
      <Card className="p-4">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-4">Sector Rotation</h3>
        <p className="text-red-500 text-sm">Error: {error}</p>
      </Card>
    )
  }

  if (!data || data.length === 0) {
    return (
      <Card className="p-4">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-4">Sector Rotation</h3>
        <p className="text-muted-foreground text-sm">No sector data available</p>
      </Card>
    )
  }

  const sortedData = [...data].sort((a, b) => getValueByMode(b) - getValueByMode(a))

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Sector Rotation</h3>
          <div className="flex gap-1">
            {(['weekly', 'monthly', 'rs_spy', 'momentum', 'rvol'] as ViewMode[]).map((mode) => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={`px-2 py-1 text-[10px] uppercase tracking-wide rounded border transition-all ${viewMode === mode
                  ? 'bg-primary/10 border-primary text-primary font-medium'
                  : 'bg-transparent border-border text-muted-foreground hover:bg-muted'
                  }`}
              >
                {viewModeLabels[mode]}
              </button>
            ))}
          </div>
        </div>
        <span className="text-xs text-muted-foreground">{data.length} groups</span>
      </div>

      <div className="grid grid-cols-5 gap-2">
        {sortedData.map((sector) => {
          const value = getValueByMode(sector)
          const colors = getColor(value)
          return (
            <div
              key={sector.name}
              onClick={() => setSelectedGroup(sector.name)}
              className={`${colors.bg} border-l-2 ${familyBorder(sector.name)} p-3 rounded cursor-pointer hover:opacity-80 transition-opacity relative group`}
              title={`${sector.name}: ${viewModeLabels[viewMode]} = ${value.toFixed(2)}% | Trend: ${sector.trend} | Strength: ${sector.strength} — clic para ver acciones`}
            >
              <div className="flex items-start justify-between mb-1">
                <div className={`font-bold text-xs truncate flex-1 ${colors.text}`}>{sector.name}</div>
                <span className={`${colors.text}/70 ml-1`}>{getTrendIcon(sector.trend)}</span>
              </div>
              <div className={`text-sm font-semibold ${colors.text}`}>
                {value > 0 ? '+' : ''}{value.toFixed(2)}%
              </div>
              <div className="flex items-center justify-between mt-1">
                <span className={`${colors.text}/80 text-[10px]`}>{sector.stock_count} stocks</span>
                <div className={`flex items-center gap-0.5 ${getStrengthColor(sector.strength)}`}>
                  <span className="text-[9px] font-medium">{sector.strength}</span>
                  {getStrengthIcon(sector.strength)}
                </div>
              </div>
            </div>
          )
        })}
      </div>

      <SectorConstituentsDrawer group={selectedGroup} onClose={() => setSelectedGroup(null)} />
    </Card>
  )
}
