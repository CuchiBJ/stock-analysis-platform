'use client'

import Link from 'next/link'
import { useCallback, useEffect, useState } from 'react'
import { Activity } from 'lucide-react'

import Card from '@/components/base/Card'
import LoadingSkeleton from '@/components/base/LoadingSkeleton'
import GroupStrengthBadge from '@/components/shared/GroupStrengthBadge'
import { apiFetch } from '@/lib/api-client'
import { useWebSocket } from '@/hooks/useWebSocket'

type Badge = 'leader' | 'neutral' | 'weak'

interface FormationSetup {
  symbol: string
  current_price: number | null
  change_pct: number | null
  formation_state: string
  formation_score: number
  formation_narrative: string
  primary_risk: string
  next_trigger: string
  distance_to_trigger_atr: number | null
  structure_evidence: string
  contraction_evidence: string
  rs_direction: string
  group_strength: { group: string | null; badge: Badge }
}

interface FormationEnvelope {
  setups: FormationSetup[]
  total_eligible: number
}

function formatState(value: string) {
  return value.replaceAll('_', ' ')
}

function FormationCard({ setup }: { setup: FormationSetup }) {
  const distance = setup.distance_to_trigger_atr == null
    ? 'sin dato'
    : `${setup.distance_to_trigger_atr >= 0 ? '+' : ''}${setup.distance_to_trigger_atr.toFixed(2)} ATR`
  const price = setup.current_price == null
    ? null
    : `$${setup.current_price.toFixed(2)}${setup.change_pct == null ? '' : ` · ${setup.change_pct >= 0 ? '+' : ''}${setup.change_pct.toFixed(1)}%`}`

  return (
    <Link
      href={`/stock/${setup.symbol}`}
      className="flex min-h-52 flex-col gap-2 rounded-lg border border-white/10 border-l-2 border-l-cyan-500/70 bg-white/5 p-3 transition-colors hover:bg-white/8"
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="text-sm font-bold tracking-wide text-white">{setup.symbol}</div>
          {price && <div className="text-[10px] font-mono text-white/50">{price}</div>}
        </div>
        <div className="text-right text-base font-bold tabular-nums text-cyan-300">
          {Math.round(setup.formation_score)}<span className="text-[9px] font-normal text-white/30">/100</span>
        </div>
      </div>
      <div className="text-[9px] uppercase tracking-widest text-white/40">{formatState(setup.formation_state)}</div>
      <p className="text-xs leading-snug text-white/75">{setup.formation_narrative}</p>
      <div className="text-[10px] text-white/65"><span className="text-white/35">Próximo trigger · </span>{setup.next_trigger} {distance}</div>
      <div className="text-[10px] text-white/60">{setup.structure_evidence}</div>
      <div className="text-[10px] text-white/60">{setup.contraction_evidence}</div>
      <div className="text-[10px] text-white/60"><span className="text-white/35">RS · </span>{formatState(setup.rs_direction)}</div>
      <div className="mt-auto border-t border-white/8 pt-2 text-[10px] leading-snug text-amber-300/85">Riesgo: {setup.primary_risk}</div>
      <GroupStrengthBadge group={setup.group_strength.group} badge={setup.group_strength.badge} />
    </Link>
  )
}

export default function SetupsForming() {
  const [data, setData] = useState<FormationEnvelope | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { data: metricsEvent } = useWebSocket<{ event: string }>({ channel: 'metrics' })

  const load = useCallback(async () => {
    try {
      setError(null)
      const response = await apiFetch('/api/v1/transitions/forming?limit=6')
      if (!response.ok) throw new Error(response.status === 401 ? 'La sesión expiró.' : 'No se pudieron cargar los setups en formación.')
      setData(await response.json() as FormationEnvelope)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudieron cargar los setups en formación.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    queueMicrotask(() => void load())
    const interval = window.setInterval(load, 60_000)
    return () => window.clearInterval(interval)
  }, [load])

  useEffect(() => {
    if (metricsEvent?.event === 'updated') queueMicrotask(() => void load())
  }, [metricsEvent, load])

  return (
    <Card blockType="forming" className="p-4">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Setups Forming</h2>
            <Activity className="h-4 w-4 text-cyan-400" />
          </div>
          <p className="mt-1 text-xs text-white/40">Preparación previa: estructuras sanas que todavía no activaron el Setup Feed.</p>
        </div>
        {data && <span className="text-xs text-white/35">{data.setups.length} de {data.total_eligible}</span>}
      </div>

      {loading ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          {Array.from({ length: 6 }, (_, index) => <LoadingSkeleton key={index} variant="card" />)}
        </div>
      ) : error ? (
        <div className="flex items-center justify-between gap-3 text-sm text-red-400">
          <span>{error}</span>
          <button className="rounded border border-white/15 px-2 py-1 text-xs text-white/70" onClick={() => void load()}>Reintentar</button>
        </div>
      ) : !data?.setups.length ? (
        <p className="text-sm text-white/45">No hay estructuras suficientemente preparadas en este snapshot. Los umbrales no se relajaron para llenar la sección.</p>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          {data.setups.slice(0, 6).map((setup) => <FormationCard key={setup.symbol} setup={setup} />)}
        </div>
      )}
    </Card>
  )
}
