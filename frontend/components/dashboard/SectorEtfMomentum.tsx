'use client'

import { useCallback, useEffect, useState } from 'react'
import { ChevronDown, ChevronUp, Flame, TrendingDown, TrendingUp } from 'lucide-react'
import { API_URL } from '@/lib/utils'
import { useWebSocket } from '@/hooks/useWebSocket'
import type { MarketGroupMomentum as MomentumData, MarketGroupMomentumSignal, SectorMomentumStatus } from '@/types/sector'

const STATUS_LABEL: Record<SectorMomentumStatus, string> = {
  warming: 'Calentándose',
  hot: 'Caliente',
  cooling: 'Enfriándose',
}

const STATUS_STYLE: Record<SectorMomentumStatus, string> = {
  warming: 'border-amber-500/40 bg-amber-500/10 text-amber-400',
  hot: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-400',
  cooling: 'border-red-500/35 bg-red-500/10 text-red-400',
}

function signed(value: number): string {
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}`
}

function StatusBadge({ status }: { status: SectorMomentumStatus }) {
  const Icon = status === 'hot' ? Flame : status === 'warming' ? TrendingUp : TrendingDown
  return (
    <span className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] font-medium ${STATUS_STYLE[status]}`}>
      <Icon className="h-3 w-3" />
      {STATUS_LABEL[status]}
    </span>
  )
}

export default function SectorLeadershipMomentum() {
  const [data, setData] = useState<MomentumData | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [sectionExpanded, setSectionExpanded] = useState(false)
  const [detailsExpanded, setDetailsExpanded] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const { data: metricsEvent } = useWebSocket<{ event: string }>({ channel: 'metrics' })

  const load = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/api/v1/sectors/leadership-momentum`)
      if (!response.ok) throw new Error('failed')
      const next: MomentumData = await response.json()
      setData(next)
      setSelected(current => current ?? next.groups[0]?.name ?? null)
      setError(false)
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    const id = setInterval(load, 60000)
    return () => clearInterval(id)
  }, [load])

  useEffect(() => {
    if (metricsEvent?.event === 'updated') load()
  }, [metricsEvent, load])

  if (loading) {
    return (
      <div className="flex min-h-12 items-center justify-between rounded-lg border border-border/50 bg-muted/20 px-3 py-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Momentum de Sector Leadership</span>
        <span className="text-[10px] text-muted-foreground">Cargando…</span>
      </div>
    )
  }
  if (error || !data) return null
  if (data.groups.length === 0) {
    return (
      <div className="rounded-lg border border-border/50 bg-[hsl(var(--block-sector))] px-4 py-3 text-xs text-muted-foreground">
        Momentum de Sector Leadership no disponible: faltan métricas históricas suficientes.
      </div>
    )
  }

  const selectedGroup: MarketGroupMomentumSignal =
    data.groups.find(group => group.name === selected) ?? data.groups[0]

  return (
    <section className="rounded-lg border border-border/50 bg-[hsl(var(--block-sector))] p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <div className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            <Flame className="h-3.5 w-3.5 text-emerald-400" />
            Momentum de Sector Leadership
          </div>
          <span className="ml-2 text-[10px] text-muted-foreground">
            {data.groups.length} grupos · vs {data.benchmark} · 4 semanas + 5 días
          </span>
        </div>
        <button
          type="button"
          aria-expanded={sectionExpanded}
          aria-controls="sector-momentum-content"
          onClick={() => setSectionExpanded(expanded => !expanded)}
          className="inline-flex min-h-7 shrink-0 items-center gap-1 rounded border border-border/60 px-2.5 py-1 text-[11px] font-medium text-foreground/80 transition-colors hover:border-foreground/30 hover:bg-white/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          {sectionExpanded ? 'Ocultar análisis' : 'Mostrar análisis'}
          {sectionExpanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
        </button>
      </div>

      <div id="sector-momentum-content" hidden={!sectionExpanded}>
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-b border-border/50 py-3">
        <span className="inline-flex shrink-0 items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          <Flame className="h-3.5 w-3.5 text-emerald-400" />
          Caliente ahora
        </span>
        <div className="flex flex-wrap gap-1.5">
          {data.hot_now.length > 0 ? data.hot_now.map(sector => (
            <button
              key={sector.name}
              type="button"
              aria-pressed={selected === sector.name}
              onClick={() => setSelected(sector.name)}
              className={`inline-flex items-center gap-1.5 rounded border px-2 py-1 text-[11px] transition-colors hover:border-foreground/30 ${
                selected === sector.name ? 'border-foreground/30 bg-white/5' : 'border-border/60'
              }`}
            >
              <span className="font-semibold">{sector.name}</span>
              <span className="font-mono text-emerald-400">Δ {signed(sector.acceleration_5d)}</span>
            </button>
          )) : <span className="text-[11px] text-muted-foreground">Sin sectores acelerando.</span>}
        </div>
        <div className="ml-auto flex flex-wrap items-center justify-end gap-x-3 gap-y-1">
          <button
            type="button"
            aria-expanded={detailsExpanded}
            aria-controls="sector-momentum-detail"
            aria-label={`${detailsExpanded ? 'Ocultar' : 'Ver'} detalle de ${selectedGroup.name}`}
            onClick={() => setDetailsExpanded(expanded => !expanded)}
            className="inline-flex min-h-7 items-center gap-1 rounded border border-border/60 px-2 py-1 text-[11px] font-medium text-foreground/80 transition-colors hover:border-foreground/30 hover:bg-white/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            {detailsExpanded ? 'Ocultar detalle' : 'Ver detalle'} · {selectedGroup.name}
            {detailsExpanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          </button>
          <span className="text-[10px] text-muted-foreground">
            vs {data.benchmark} · {data.as_of ?? 'sin fecha'}
          </span>
        </div>
      </div>

      <div className="pt-3">
        <div
          id="sector-momentum-detail"
          hidden={!detailsExpanded}
          className="mb-3 rounded border border-border/60 bg-background/30 p-3"
        >
          <div className="mb-2 flex items-start justify-between gap-2">
            <div>
              <div className="text-sm font-semibold">{selectedGroup.name}</div>
              <div className="text-[11px] text-muted-foreground">
                #{selectedGroup.weekly_rank} · {selectedGroup.stock_count} acciones · liderazgo en dos horizontes
              </div>
            </div>
            <StatusBadge status={selectedGroup.status} />
          </div>
          <p className="text-xs leading-5 text-foreground/80">
            {selectedGroup.relative_strength_4w > 0 ? 'Fuerte' : 'Débil'} en cuatro semanas
            {' '}(#{selectedGroup.weekly_rank}, {signed(selectedGroup.relative_strength_4w)} pp vs SPY)
            {' '}y {selectedGroup.acceleration_5d > 0 ? 'acelerando' : 'perdiendo velocidad'} en cinco días
            {' '}({signed(selectedGroup.acceleration_5d)} pp).
          </p>
          <div className="mt-2 text-[10px] leading-4 text-muted-foreground">
            El ranking semanal mide liderazgo estructural; la aceleración compara el RS de las últimas 5 ruedas con las 5 anteriores.
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[620px] text-xs">
            <thead className="text-[10px] uppercase tracking-wide text-muted-foreground">
              <tr className="border-b border-border/60">
                <th className="px-2 py-1.5 text-left font-medium">Rank</th>
                <th className="px-2 py-1.5 text-left font-medium">Grupo</th>
                <th className="px-2 py-1.5 text-right font-medium">RS 4s</th>
                <th className="px-2 py-1.5 text-right font-medium">RS 5d</th>
                <th className="px-2 py-1.5 text-right font-medium">Acel. 5d</th>
                <th className="px-2 py-1.5 text-right font-medium">Estado</th>
              </tr>
            </thead>
            <tbody>
              {data.groups.map(sector => (
                <tr
                  key={sector.name}
                  onClick={() => setSelected(sector.name)}
                  className={`cursor-pointer border-b border-border/30 transition-colors hover:bg-white/5 ${selected === sector.name ? 'bg-white/5' : ''}`}
                >
                  <td className="px-2 py-2 font-mono text-muted-foreground">{sector.weekly_rank}</td>
                  <td className="px-2 py-2">
                    <span className="font-semibold">{sector.name}</span>
                    <span className="ml-2 text-[10px] text-muted-foreground">{sector.stock_count}</span>
                  </td>
                  <td className={`px-2 py-2 text-right font-mono ${sector.relative_strength_4w >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {signed(sector.relative_strength_4w)}
                  </td>
                  <td className={`px-2 py-2 text-right font-mono ${sector.relative_strength_5d >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {signed(sector.relative_strength_5d)}
                  </td>
                  <td className={`px-2 py-2 text-right font-mono ${sector.acceleration_5d >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {signed(sector.acceleration_5d)}
                  </td>
                  <td className="px-2 py-2 text-right"><StatusBadge status={sector.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      </div>
    </section>
  )
}
