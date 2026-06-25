'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { API_URL } from '@/lib/utils'
import Card from '@/components/base/Card'
import LoadingSkeleton from '@/components/base/LoadingSkeleton'
import { ExternalLink } from 'lucide-react'
import GroupStrengthBadge from '@/components/shared/GroupStrengthBadge'
import TakeFromQueueButton from '@/components/queue/TakeFromQueueButton'

interface GroupStrength {
  group: string | null
  badge: 'leader' | 'neutral' | 'weak'
}

interface BaseRow {
  symbol: string
  vcp_quality: number
  band_contraction: number
  volume_dryup: number
  max_gap_atr: number
  recent_range_atr: number
  is_contracting: boolean
  weeks_in_base: number
  current_distance_to_ema21_atr: number | null
  vcp_score: number | null
  tradingview_url: string
  market_group?: string | null
  group_strength?: GroupStrength | null
}

interface ContextSnapshot {
  participation: string
  leadership: string
}

interface QueueResponse {
  suppressed: boolean
  suppression_reason: string | null
  context_snapshot: ContextSnapshot
  results: BaseRow[]
}

interface Props {
  refreshKey: number
}

function qualityTier(q: number): { label: string; cls: string } {
  if (q >= 0.5) return { label: 'VCP limpio', cls: 'text-green-400' }
  if (q >= 0.3) return { label: 'en desarrollo', cls: 'text-yellow-400' }
  return { label: 'flojo', cls: 'text-orange-400' }
}

// component scores 0–1: higher = better (more contraction / more dry-up)
function compColor(v: number) {
  if (v >= 0.5) return 'text-green-400'
  if (v >= 0.25) return 'text-yellow-400'
  return 'text-muted-foreground'
}

export default function BuildingBasesQueue({ refreshKey }: Props) {
  const [response, setResponse] = useState<QueueResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetch(`${API_URL}/api/v1/queue/building-bases`)
      .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then(data => {
        if (cancelled) return
        setResponse(data)
        setError(null)
      })
      .catch(e => { if (!cancelled) setError(e.message) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [refreshKey])

  if (loading) return <div className="space-y-2">{[...Array(4)].map((_, i) => <LoadingSkeleton key={i} variant="card" />)}</div>
  if (error) return <p className="text-sm text-destructive">Error: {error}</p>
  if (!response) return null

  const { results: rows } = response

  if (rows.length === 0) {
    return (
      <div className="space-y-2">
        <Card className="p-6">
          <p className="text-sm text-muted-foreground">
            No hay líderes Minervini con 6+ semanas en base ahora mismo.
          </p>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground px-1">
        Líderes Minervini (6+ semanas en base) ordenados por <strong className="text-foreground">calidad de VCP</strong>:
        combina contracción de banda (rango cerrándose) + secado de volumen, penalizando gaps de evento
        (un salto de noticia no es un VCP). En este universo de alto ADR no existen bases apretadas en
        absoluto — son las <strong className="text-foreground">8 de mayor calidad disponibles</strong>. Score bajo
        en toda la lista = no hay VCPs limpios ahora mismo.
      </p>
      {rows.map(r => {
        const tier = qualityTier(r.vcp_quality)
        return (
        <Card key={r.symbol} className="p-3 hover:bg-muted/30 cursor-pointer transition-colors">
          <div className="flex items-center justify-between gap-4">
            <Link href={`/stock/${r.symbol}`} className="flex items-center gap-3 min-w-0 flex-1">
              <div className="font-bold text-foreground w-16">{r.symbol}</div>
              {r.group_strength && (
                <GroupStrengthBadge group={r.group_strength.group} badge={r.group_strength.badge} />
              )}
              <div className="text-xs text-muted-foreground">{r.weeks_in_base}w base</div>
              <span className={`text-[10px] px-2 py-0.5 rounded border border-white/10 ${tier.cls}`}>{tier.label}</span>
              {r.max_gap_atr >= 1.5 && (
                <span className="text-[10px] text-orange-400" title={`Gap de evento de ${r.max_gap_atr} ATR en la ventana — penaliza la calidad`}>
                  ⚠ gap {r.max_gap_atr}ATR
                </span>
              )}
            </Link>

            <div className="flex items-center gap-4 text-xs">
              <div title="Calidad de VCP 0–1: banda + volumen − gap de evento">
                <span className="text-muted-foreground">VCP: </span>
                <span className={`font-mono font-semibold ${tier.cls}`}>{r.vcp_quality.toFixed(2)}</span>
              </div>
              <div title="Contracción de banda: 1 − rango_reciente/rango_previo (0=plano, 1=cerrando fuerte)">
                <span className="text-muted-foreground">banda: </span>
                <span className={`font-mono ${compColor(r.band_contraction)}`}>{r.band_contraction.toFixed(2)}</span>
              </div>
              <div title="Secado de volumen: 1 − vol_reciente/vol_previo (0=volumen subiendo, 1=secándose)">
                <span className="text-muted-foreground">vol seca: </span>
                <span className={`font-mono ${compColor(r.volume_dryup)}`}>{r.volume_dryup.toFixed(2)}</span>
              </div>
              {r.current_distance_to_ema21_atr != null && (
                <div>
                  <span className="text-muted-foreground">EMA21: </span>
                  <span className="font-mono text-foreground">
                    {r.current_distance_to_ema21_atr >= 0 ? '+' : ''}{r.current_distance_to_ema21_atr.toFixed(2)} ATR
                  </span>
                </div>
              )}
              <a
                href={r.tradingview_url}
                target="_blank"
                rel="noopener noreferrer"
                onClick={e => e.stopPropagation()}
                className="flex items-center gap-1 text-primary hover:text-primary/80"
              >
                TV <ExternalLink className="w-3 h-3" />
              </a>
              <TakeFromQueueButton symbol={r.symbol} setup="building_base" />
            </div>
          </div>
        </Card>
        )
      })}
    </div>
  )
}
