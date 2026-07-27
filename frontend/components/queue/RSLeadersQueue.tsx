'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { API_URL } from '@/lib/utils'
import Card from '@/components/base/Card'
import LoadingSkeleton from '@/components/base/LoadingSkeleton'
import { ExternalLink, Shield } from 'lucide-react'
import GroupStrengthBadge from '@/components/shared/GroupStrengthBadge'
import TakeFromQueueButton from '@/components/queue/TakeFromQueueButton'

interface GroupStrength {
  group: string | null
  badge: 'leader' | 'neutral' | 'weak'
}

type HoldingStatus = 'at_highs' | 'above_ema21' | 'testing_ema21' | 'testing_ema50' | 'deep_pullback'
type SortMode = 'rs' | 'momentum'
type Window = 3 | 5 | 10

interface RSLeaderRow {
  symbol: string
  rs_spy: number
  rs_qqq: number | null
  perf_1w: number | null
  rel_strength_1w: number | null
  perf_4w: number | null
  perf_13w: number | null
  distance_to_high_52w_atr: number | null
  distance_to_ema21_atr: number | null
  distance_to_ema50_atr: number | null
  current_price: number | null
  holding_status: HoldingStatus
  // momentum block
  window: number
  rs_delta: number | null
  rs_delta_pct: number | null
  stock_return_n: number | null
  spy_return_n: number | null
  resilience: number | null
  held_up: boolean
  rs_momentum_score: number | null
  tradingview_url: string
  market_group?: string | null
  group_strength?: GroupStrength | null
}

interface QueueResponse {
  suppressed: boolean
  suppression_reason: string | null
  context_snapshot: { participation: string; leadership: string }
  results: RSLeaderRow[]
}

interface Props {
  refreshKey: number
}

const HOLDING: Record<HoldingStatus, { label: string; cls: string }> = {
  at_highs:      { label: 'en máximos',    cls: 'border-green-500/30 bg-green-500/10 text-green-400' },
  above_ema21:   { label: 'sobre EMA21',   cls: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300' },
  testing_ema21: { label: 'testea EMA21',  cls: 'border-yellow-400/30 bg-yellow-400/10 text-yellow-300' },
  testing_ema50: { label: 'testea EMA50',  cls: 'border-amber-400/30 bg-amber-400/10 text-amber-300' },
  deep_pullback: { label: 'pullback profundo', cls: 'border-red-500/30 bg-red-500/10 text-red-400' },
}

const signed = (v: number, suffix = '') => `${v >= 0 ? '+' : ''}${v.toFixed(1)}${suffix}`
const tone = (v: number) => (v >= 0 ? 'text-green-400' : 'text-red-400')

// d21 (distancia a EMA21 en ATR) por encima de esto = "extendida" — mismo techo
// que el rango accionable de la cola U&R (-0.5 ≤ d21 ≤ 1.5).
const EXTENSION_CEILING_ATR = 1.5
const HIDE_EXTENDED_KEY = 'rsq:hideExtended'

export default function RSLeadersQueue({ refreshKey }: Props) {
  const [response, setResponse] = useState<QueueResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [sortMode, setSortMode] = useState<SortMode>('rs')
  const [window, setWindow] = useState<Window>(5)
  const [hideExtended, setHideExtended] = useState(true)

  // Restaurar preferencia del toggle (default ON) y persistirla.
  useEffect(() => {
    const saved = localStorage.getItem(HIDE_EXTENDED_KEY)
    if (saved !== null) setHideExtended(saved === '1')
  }, [])
  useEffect(() => {
    localStorage.setItem(HIDE_EXTENDED_KEY, hideExtended ? '1' : '0')
  }, [hideExtended])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetch(`${API_URL}/api/v1/queue/rs-leaders?sort=${sortMode}&window=${window}`)
      .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then(data => {
        if (cancelled) return
        setResponse(data)
        setError(null)
      })
      .catch(e => { if (!cancelled) setError(e.message) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [refreshKey, sortMode, window])

  const isMomentum = sortMode === 'momentum'
  const spyReturnN = response?.results.find(r => r.spy_return_n != null)?.spy_return_n ?? null

  const controls = (
    <div className="flex items-center justify-between gap-3 px-1 flex-wrap">
      <div className="flex rounded-md border border-border overflow-hidden text-xs">
        <button
          onClick={() => setSortMode('rs')}
          className={`px-3 py-1.5 transition-colors ${!isMomentum ? 'bg-primary/15 text-foreground font-medium' : 'text-muted-foreground hover:text-foreground'}`}
        >
          RS 13w
        </button>
        <button
          onClick={() => setSortMode('momentum')}
          className={`px-3 py-1.5 border-l border-border transition-colors ${isMomentum ? 'bg-primary/15 text-foreground font-medium' : 'text-muted-foreground hover:text-foreground'}`}
        >
          RS Momentum
        </button>
      </div>
      <div className="flex items-center gap-3 text-xs flex-wrap">
        {isMomentum && (
          <div className="flex items-center gap-2 text-xs">
            <span className="text-muted-foreground">ventana:</span>
            <div className="flex rounded-md border border-border overflow-hidden">
              {([3, 5, 10] as Window[]).map(w => (
                <button
                  key={w}
                  onClick={() => setWindow(w)}
                  className={`px-2.5 py-1 transition-colors ${window === w ? 'bg-primary/15 text-foreground font-medium' : 'text-muted-foreground hover:text-foreground'} ${w !== 3 ? 'border-l border-border' : ''}`}
                >
                  {w}d
                </button>
              ))}
            </div>
            {spyReturnN != null && (
              <span className="text-muted-foreground/70">
                SPY {window}d: <span className={`font-mono ${tone(spyReturnN)}`}>{signed(spyReturnN, '%')}</span>
              </span>
            )}
          </div>
        )}
        <button
          onClick={() => setHideExtended(v => !v)}
          title="Oculta líderes a más de 1.5 ATR sobre la EMA21 (extendidas, no accionables)"
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md border transition-colors ${
            hideExtended
              ? 'border-primary/40 bg-primary/15 text-foreground font-medium'
              : 'border-border text-muted-foreground hover:text-foreground'
          }`}
        >
          <span className="font-mono">{hideExtended ? '✓' : ''}</span>
          ocultar extendidas
        </button>
      </div>
    </div>
  )

  const header = isMomentum ? (
    <p className="text-xs text-muted-foreground px-1">
      Hacia dónde fluye la fuerza relativa <strong className="text-foreground">ahora</strong>: ordenado por
      pendiente del RS line en las últimas {window} sesiones + resiliencia mientras el SPY cae.
      El badge <span className="inline-flex items-center gap-0.5 text-sky-300"><Shield className="w-3 h-3" />aguantó</span>{' '}
      marca los que cerraron planos o positivos mientras el SPY bajó. <span className="text-muted-foreground/60">ΔRS = cambio del RS line; resil = cuánto le sacó al SPY en la ventana.</span>
    </p>
  ) : (
    <p className="text-xs text-muted-foreground px-1">
      Líderes Minervini ordenados por fuerza relativa vs SPY (RS trailing de 13 semanas). En días de caída, los de
      RS más alto que siguen <span className="text-green-400">en máximos</span> o{' '}
      <span className="text-emerald-300">sobre EMA21</span> son candidatos a liderar el próximo rebote.
      <span className="text-muted-foreground/60"> Para ver quién gana RS estos días, pasá a RS Momentum.</span>
    </p>
  )

  if (loading) {
    return (
      <div className="space-y-2">
        {controls}
        {[...Array(4)].map((_, i) => <LoadingSkeleton key={i} variant="card" />)}
      </div>
    )
  }
  if (error) return <div className="space-y-2">{controls}<p className="text-sm text-destructive">Error: {error}</p></div>
  if (!response) return null

  const rows = response.results

  if (rows.length === 0) {
    return (
      <div className="space-y-2">
        {controls}
        <Card className="p-6">
          <p className="text-sm text-muted-foreground">
            No hay líderes Minervini en el universo ahora mismo. Esta lente rankea el pool de
            líderes por RS vs SPY — aparece cuando hay al menos un líder calificado.
          </p>
        </Card>
      </div>
    )
  }

  const visibleRows = hideExtended
    ? rows.filter(r => r.distance_to_ema21_atr == null || r.distance_to_ema21_atr <= EXTENSION_CEILING_ATR)
    : rows
  const hiddenCount = rows.length - visibleRows.length

  if (visibleRows.length === 0) {
    return (
      <div className="space-y-2">
        {controls}
        {header}
        <Card className="p-6">
          <p className="text-sm text-muted-foreground">
            Todas las líderes están extendidas (&gt;{EXTENSION_CEILING_ATR} ATR sobre la EMA21) ahora mismo.{' '}
            <button onClick={() => setHideExtended(false)} className="text-primary hover:text-primary/80">
              Apagá el filtro
            </button>{' '}
            para verlas.
          </p>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {controls}
      {header}
      {hiddenCount > 0 && (
        <p className="text-[11px] text-muted-foreground/60 px-1">
          {hiddenCount} extendida{hiddenCount === 1 ? '' : 's'} oculta{hiddenCount === 1 ? '' : 's'} (&gt;{EXTENSION_CEILING_ATR} ATR sobre EMA21).{' '}
          <button onClick={() => setHideExtended(false)} className="text-primary/80 hover:text-primary">
            Mostrar
          </button>
        </p>
      )}
      {visibleRows.map(r => (
        <Card key={r.symbol} className="p-3">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3 min-w-0 flex-1">
              <div className="font-bold text-foreground w-16">{r.symbol}</div>
              {r.group_strength && (
                <GroupStrengthBadge group={r.group_strength.group} badge={r.group_strength.badge} />
              )}
              <span className={`text-[10px] px-2 py-0.5 rounded border ${HOLDING[r.holding_status].cls}`}>
                {HOLDING[r.holding_status].label}
              </span>
              {isMomentum && r.held_up && (
                <span className="inline-flex items-center gap-0.5 text-[10px] px-2 py-0.5 rounded border border-sky-400/30 bg-sky-400/10 text-sky-300">
                  <Shield className="w-3 h-3" /> aguantó
                </span>
              )}
            </div>

            <div className="flex items-center gap-4 text-xs">
              {isMomentum ? (
                <>
                  {r.rs_momentum_score != null && (
                    <div title="rs_delta_pct + resiliencia mientras el SPY cae">
                      <span className="text-muted-foreground">mom: </span>
                      <span className={`font-mono font-semibold ${tone(r.rs_momentum_score)}`}>{signed(r.rs_momentum_score)}</span>
                    </div>
                  )}
                  {r.rs_delta_pct != null && (
                    <div title={`Pendiente del RS line en ${r.window} sesiones`}>
                      <span className="text-muted-foreground">ΔRS: </span>
                      <span className={`font-mono ${tone(r.rs_delta_pct)}`}>{signed(r.rs_delta_pct, '%')}</span>
                    </div>
                  )}
                  {r.resilience != null && (
                    <div title="Retorno del stock menos el del SPY en la ventana">
                      <span className="text-muted-foreground">resil: </span>
                      <span className={`font-mono ${tone(r.resilience)}`}>{signed(r.resilience, 'pp')}</span>
                    </div>
                  )}
                  <div title="RS trailing 13 semanas (acumulado)">
                    <span className="text-muted-foreground">RS13w: </span>
                    <span className="font-mono text-foreground/70">{r.rs_spy.toFixed(0)}</span>
                  </div>
                </>
              ) : (
                <>
                  <div title="Relative Strength vs SPY (13 semanas)">
                    <span className="text-muted-foreground">RS: </span>
                    <span className="font-mono text-foreground font-semibold">{r.rs_spy.toFixed(0)}</span>
                  </div>
                  {r.rel_strength_1w != null && (
                    <div title="Performance del stock menos la del SPY, última semana">
                      <span className="text-muted-foreground">vs SPY 1w: </span>
                      <span className={`font-mono ${tone(r.rel_strength_1w)}`}>{signed(r.rel_strength_1w, 'pp')}</span>
                    </div>
                  )}
                  {r.perf_13w != null && (
                    <div>
                      <span className="text-muted-foreground">13w: </span>
                      <span className={`font-mono ${tone(r.perf_13w)}`}>{r.perf_13w >= 0 ? '+' : ''}{r.perf_13w.toFixed(0)}%</span>
                    </div>
                  )}
                </>
              )}
              <Link href={`/stock/${r.symbol}`} className="text-primary hover:text-primary/80">
                detail →
              </Link>
              <a
                href={r.tradingview_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-primary hover:text-primary/80"
              >
                TV <ExternalLink className="w-3 h-3" />
              </a>
              <TakeFromQueueButton symbol={r.symbol} setup="rs-leader" />
            </div>
          </div>
        </Card>
      ))}
    </div>
  )
}
