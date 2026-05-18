'use client'

import Card from '@/components/base/Card'
import { TrendingUp, TrendingDown, Activity, Flame, ArrowDown, Clock } from 'lucide-react'
import Sparkline from '@/components/charts/Sparkline'

interface CompactSetupCardProps {
  symbol: string
  state: string
  transition: string
  transitionStrength: number
  narrative: string
  confidence: number
  freshness: string
  daysInState: number
  keyMetrics: {
    ema21: string
    rs: number
    volume: string
    base: string
  }
  sector?: string
  isPriority?: boolean
  sparklineData?: number[]  // Historical price data for sparkline
}

export default function CompactSetupCard({
  symbol,
  state,
  transition,
  transitionStrength,
  narrative,
  confidence,
  freshness,
  daysInState,
  keyMetrics,
  sector,
  isPriority = false,
  sparklineData
}: CompactSetupCardProps) {
  const getTransitionVisuals = (transition: string, strength: number) => {
    const intensity = Math.floor(strength * 100)

    if (transition === 'improving' || transition === 'tightening' || transition === 'reclaiming') {
      return {
        bg: `bg-green-${500 + Math.min(intensity, 200)}`,
        glow: `shadow-green-${500 + Math.min(intensity, 200)}/${50 + intensity}%`,
        pulse: true
      }
    } else if (transition === 'stable' || transition === 'stabilizing') {
      return {
        bg: 'bg-blue-600',
        glow: 'shadow-blue-600/20',
        pulse: false
      }
    } else if (transition === 'weakening') {
      return {
        bg: `bg-orange-${500 + Math.min(intensity, 200)}`,
        glow: `shadow-orange-${500 + Math.min(intensity, 200)}/${30 + intensity}%`,
        pulse: false
      }
    } else if (transition === 'failing') {
      return {
        bg: `bg-red-${500 + Math.min(intensity, 200)}`,
        glow: `shadow-red-${500 + Math.min(intensity, 200)}/${50 + intensity}%`,
        pulse: true
      }
    }

    return { bg: 'bg-slate-700', glow: '', pulse: false }
  }

  const getFreshnessColor = (freshness: string) => {
    switch (freshness) {
      case 'fresh': return 'text-green-400 bg-green-400/10'
      case 'aging': return 'text-yellow-400 bg-yellow-400/10'
      case 'late-stage': return 'text-orange-400 bg-orange-400/10'
      case 'stale': return 'text-red-400 bg-red-400/10'
      case 'extended': return 'text-red-500 bg-red-500/20'
      default: return 'text-slate-400 bg-slate-400/10'
    }
  }

  const getTransitionIcon = (transition: string) => {
    if (transition === 'improving' || transition === 'tightening' || transition === 'reclaiming') {
      return <TrendingUp className="w-3 h-3" />
    } else if (transition === 'weakening' || transition === 'failing') {
      return <TrendingDown className="w-3 h-3" />
    } else {
      return <Activity className="w-3 h-3" />
    }
  }

  const visuals = getTransitionVisuals(transition, transitionStrength)
  const freshnessClass = getFreshnessColor(freshness)

  const cardSize = isPriority ? 'w-full max-w-md' : 'w-full max-w-xs'
  const padding = isPriority ? 'p-4' : 'p-3'

  const sparklineColor = transition === 'improving' || transition === 'tightening' || transition === 'reclaiming'
    ? 'rgba(34, 197, 94, 0.8)'
    : transition === 'weakening' || transition === 'failing'
      ? 'rgba(239, 68, 68, 0.8)'
      : 'rgba(59, 130, 246, 0.8)'

  return (
    <Card className={`${cardSize} ${padding} ${visuals.bg} ${visuals.glow} ${visuals.pulse ? 'animate-pulse' : ''} rounded cursor-pointer hover:opacity-80 transition-all relative group`}>
      {/* Header */}
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="font-bold text-sm text-white">{symbol}</span>
          <span className={`text-[10px] px-1.5 py-0.5 rounded ${freshnessClass} uppercase`}>
            {freshness}
          </span>
        </div>
        <div className="flex items-center gap-1 text-white/80">
          {getTransitionIcon(transition)}
          <span className="text-[10px] uppercase">{transition}</span>
        </div>
      </div>

      {/* Sparkline */}
      {sparklineData && sparklineData.length > 1 && (
        <div className="mb-2">
          <Sparkline
            data={sparklineData}
            color={sparklineColor}
            width={isPriority ? 300 : 200}
            height={30}
          />
        </div>
      )}

      {/* State */}
      <div className="mb-2">
        <span className="text-xs text-white/70 uppercase tracking-wide">{state}</span>
      </div>

      {/* Narrative */}
      <div className="mb-2">
        <p className="text-xs text-white/90 leading-relaxed">{narrative}</p>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-2 gap-1 mb-2">
        <div className="text-[10px] text-white/60">
          <span className="text-white/80">EMA21:</span> {keyMetrics.ema21}
        </div>
        <div className="text-[10px] text-white/60">
          <span className="text-white/80">RS:</span> {keyMetrics.rs}
        </div>
        <div className="text-[10px] text-white/60">
          <span className="text-white/80">Vol:</span> {keyMetrics.volume}
        </div>
        <div className="text-[10px] text-white/60">
          <span className="text-white/80">Base:</span> {keyMetrics.base}
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1">
          <Clock className="w-3 h-3 text-white/50" />
          <span className="text-[10px] text-white/50">{daysInState}d in state</span>
        </div>
        {isPriority && (
          <div className="flex items-center gap-1">
            <Flame className="w-3 h-3 text-orange-400" />
            <span className="text-[10px] text-orange-400 font-medium">
              Priority {Math.round(confidence * 100)}
            </span>
          </div>
        )}
        {sector && (
          <span className="text-[10px] text-white/50">{sector}</span>
        )}
      </div>

      {/* Confidence indicator (only for priority cards) */}
      {isPriority && (
        <div className="absolute top-2 right-2">
          <div className="w-2 h-2 rounded-full bg-orange-400 animate-pulse" />
        </div>
      )}
    </Card>
  )
}
