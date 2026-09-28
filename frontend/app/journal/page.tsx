'use client'

import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { apiFetch } from '@/lib/api-client'
import DashboardLayout from '@/components/layout/DashboardLayout'
import Card from '@/components/base/Card'
import LoadingSkeleton from '@/components/base/LoadingSkeleton'
import { Upload, Download, AlertTriangle, Link2, Plus, X, Pencil, Trash2 } from 'lucide-react'
import { NewTradeModal, CloseTradeModal, EditTradeModal, type Trade, type Vocab } from './TradeForms'
import WinRateEvolutionChart, { type WinRatePoint } from '@/components/charts/WinRateEvolutionChart'

interface Aggregate {
  n: number
  win_rate: number | null
  expectancy: number | null
  profit_factor: number | null
  avg_r: number | null
  total_r: number | null
  avg_duration_days: number | null
  total_pnl: number
  wins: number
  losses: number
  breakeven: number
}

interface SetupRow extends Aggregate { setup: string }
interface ContextRow extends Aggregate { context: string }
interface MatrixRow extends Aggregate { setup: string; context: string }

interface EntryReasonRow extends Aggregate { entry_reason: string }

interface RiskEvolutionRow {
  month: string
  n: number
  avg_planned_risk_dollars: number | null
  avg_risk_pct_of_account: number | null
  win_rate: number | null
  wins: number
  losses: number
  total_r: number | null
  total_pnl: number
}

interface RegimeRow extends Aggregate { regime_at_entry: string }
interface SetupRegimeMatrixRow extends Aggregate { setup: string; regime_at_entry: string }

interface DecisionOverall {
  n_decisions_total: number
  n_fully_resolved: number
  n_partially_resolved: number
  n_fully_open: number
  decision_wins: number
  decision_losses: number
  decision_breakeven: number
  decision_win_rate: number | null
  decision_total_realized_pnl: number
  decision_total_r: number | null
  decision_average_gain: number | null
  decision_average_loss: number | null
  decision_total_gains: number
  decision_total_losses: number
}

type DecisionOutcome = 'win' | 'loss' | 'breakeven'
type TradeFilter = 'all' | DecisionOutcome

interface StatsResponse {
  overall: Aggregate
  by_setup: SetupRow[]
  by_context: ContextRow[]
  by_setup_context: MatrixRow[]
  by_entry_reason: EntryReasonRow[]
  risk_evolution: RiskEvolutionRow[]
  by_regime_at_entry: RegimeRow[]
  by_setup_regime_matrix: SetupRegimeMatrixRow[]
  decision_overall: DecisionOverall
  win_rate_evolution: WinRatePoint[]
  rolling_window: number
  open_positions: number
  linked_to_observations: number
  underpowered_buckets: number
}

function fmtMoney(n: number | null | undefined): string {
  if (n == null) return '—'
  const sign = n < 0 ? '-' : ''
  return `${sign}$${Math.abs(n).toFixed(2)}`
}
function fmtPct(n: number | null | undefined, decimals = 1): string {
  if (n == null) return '—'
  return `${(n * 100).toFixed(decimals)}%`
}
function fmtNum(n: number | null | undefined, decimals = 2): string {
  if (n == null) return '—'
  return n.toFixed(decimals)
}
function colorPnl(n: number | null | undefined): string {
  if (n == null || n === 0) return 'text-muted-foreground'
  return n > 0 ? 'text-green-400' : 'text-red-400'
}

export default function JournalPage() {
  const [stats, setStats] = useState<StatsResponse | null>(null)
  const [allTrades, setAllTrades] = useState<Trade[]>([])
  const [vocab, setVocab] = useState<Vocab | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [importResult, setImportResult] = useState<string | null>(null)
  const [showNew, setShowNew] = useState(false)
  const [closeTarget, setCloseTarget] = useState<Trade | null>(null)
  const [editTarget, setEditTarget] = useState<Trade | null>(null)
  const [backfilling, setBackfilling] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [tradeFilter, setTradeFilter] = useState<TradeFilter>('all')
  const [closedSectionOpen, setClosedSectionOpen] = useState(false)
  const [focusRequest, setFocusRequest] = useState<{ decisionId: number; nonce: number } | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const decisionGroups = useMemo(() => buildDecisionGroups(allTrades), [allTrades])
  const openPositionGroups = useMemo(() => buildOpenPositionGroups(allTrades), [allTrades])
  const dcaPositionGroups = useMemo(() => buildDcaPositionGroups(allTrades), [allTrades])
  const realizedDecisionGroups = useMemo(
    () => decisionGroups.filter(
      group => group.setup !== 'dca' && group.legs.some(leg => !leg.is_open),
    ),
    [decisionGroups],
  )
  const filteredDecisionGroups = useMemo(
    () => tradeFilter === 'all'
      ? realizedDecisionGroups
      : realizedDecisionGroups.filter(group => group.outcome === tradeFilter),
    [realizedDecisionGroups, tradeFilter],
  )

  const reload = useCallback(async () => {
    setLoading(true)
    try {
      const [s, all, v] = await Promise.all([
        apiFetch('/api/v1/journal/stats').then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))),
        apiFetch('/api/v1/journal/trades?closed_only=false').then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))),
        apiFetch('/api/v1/journal/vocab').then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))),
      ])
      setStats(s)
      setAllTrades(all.trades)
      setVocab(v as Vocab)
      setError(null)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { queueMicrotask(() => void reload()) }, [reload])

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true); setImportResult(null)
    try {
      const fd = new FormData(); fd.append('file', file)
      const res = await apiFetch('/api/v1/journal/import?replace=true', { method: 'POST', body: fd })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`)
      setImportResult(
        `Imported: ${data.trades_closed} closed · ${data.positions_open} open · ${data.linked_observations} linked` +
        (data.parse_errors?.length ? ` · ${data.parse_errors.length} warnings` : '')
      )
      await reload()
    } catch (err: unknown) {
      setImportResult(`Error: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  async function backfillRegime() {
    setBackfilling(true); setImportResult(null)
    try {
      const res = await apiFetch('/api/v1/journal/backfill-regime', { method: 'POST' })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`)
      setImportResult(
        `Contexto reconstruido: ${data.updated} trades actualizados` +
        (data.out_of_range ? ` · ${data.out_of_range} fuera del rango de datos (sin métricas en esa fecha)` : '')
      )
      await reload()
    } catch (err: unknown) {
      setImportResult(`Error: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setBackfilling(false)
    }
  }

  async function deleteTrade(id: number) {
    if (!confirm('¿Borrar este trade? No se puede deshacer.')) return
    const res = await apiFetch(`/api/v1/journal/trades/${id}`, { method: 'DELETE' })
    if (res.ok) await reload()
    else alert(`Error: HTTP ${res.status}`)
  }

  async function exportCsv() {
    setExporting(true)
    try {
      const response = await apiFetch('/api/v1/journal/export.csv')
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      const downloadUrl = URL.createObjectURL(await response.blob())
      const anchor = document.createElement('a')
      anchor.href = downloadUrl
      anchor.download = 'journal.csv'
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      URL.revokeObjectURL(downloadUrl)
    } catch (error) {
      alert(`Error exportando CSV: ${error instanceof Error ? error.message : String(error)}`)
    } finally {
      setExporting(false)
    }
  }

  function selectTradeFilter(filter: TradeFilter) {
    setTradeFilter(filter)
    setClosedSectionOpen(true)
    setFocusRequest(null)
  }

  function openDecisionDetail(decisionId: number) {
    setTradeFilter('all')
    setClosedSectionOpen(true)
    setFocusRequest({ decisionId, nonce: Date.now() })
  }

  return (
    <DashboardLayout>
      <div className="max-w-6xl mx-auto space-y-4">
        <div className="flex items-end justify-between flex-wrap gap-2">
          <div>
            <h1 className="text-xl font-bold text-foreground">Journal</h1>
            <p className="text-xs text-muted-foreground mt-1">
              Trades reales del broker. Cada operación cerrada es un outcome verificado y alimenta la verdad empírica del sistema.
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setShowNew(true)}
              disabled={!vocab}
              className="inline-flex items-center gap-1.5 text-xs px-3 py-2 rounded bg-blue-500/20 border border-blue-500/40 text-blue-300 hover:bg-blue-500/30 disabled:opacity-50"
            >
              <Plus className="w-3.5 h-3.5" /> Nuevo trade
            </button>
            <button
              type="button"
              onClick={exportCsv}
              disabled={exporting}
              className="inline-flex items-center gap-1.5 text-xs px-3 py-2 rounded border border-border bg-card hover:bg-muted/40 transition-colors"
              title="Descarga el journal como CSV (mismo formato que tu sheet). La app es la fuente de verdad; esto mantiene tu Excel como respaldo actualizado."
            >
              <Download className="w-3.5 h-3.5" /> {exporting ? 'Exportando…' : 'Exportar CSV'}
            </button>
            <label className="cursor-pointer inline-flex items-center gap-1.5 text-xs px-3 py-2 rounded border border-border bg-card hover:bg-muted/40 transition-colors">
              <Upload className="w-3.5 h-3.5" />
              {uploading ? 'Subiendo…' : 'Importar CSV'}
              <input ref={fileRef} type="file" accept=".csv" className="hidden" onChange={onFile} disabled={uploading} />
            </label>
          </div>
        </div>

        {importResult && (
          <Card className="p-3 text-xs text-muted-foreground border-amber-400/30 bg-amber-400/5 flex items-start justify-between gap-2">
            <span className="whitespace-pre-line">{importResult}</span>
            <button onClick={() => setImportResult(null)} className="text-muted-foreground hover:text-foreground"><X className="w-3 h-3" /></button>
          </Card>
        )}

        {loading && <LoadingSkeleton variant="card" />}
        {error && <p className="text-sm text-destructive">Error: {error}</p>}

        {stats && stats.overall.n === 0 && openPositionGroups.length === 0 && dcaPositionGroups.length === 0 && (
          <Card className="p-6 text-center">
            <p className="text-sm text-muted-foreground">
              No hay trades cargados. Cargá uno con &quot;Nuevo trade&quot; o subí el CSV histórico con &quot;Importar CSV&quot;.
            </p>
          </Card>
        )}

        {/* Open positions */}
        {openPositionGroups.length > 0 && (
          <OpenPositionsTable
            groups={openPositionGroups}
            onClose={setCloseTarget}
            onEdit={setEditTarget}
            onDelete={deleteTrade}
          />
        )}

        {/* DCA holdings are visible, but intentionally stay outside trading metrics/open positions. */}
        {dcaPositionGroups.length > 0 && (
          <DcaPositionsTable
            groups={dcaPositionGroups}
            onEdit={setEditTarget}
            onDelete={deleteTrade}
          />
        )}

        {stats && stats.overall.n > 0 && (
          <>
            <Card className="p-4 border-blue-500/20 bg-blue-500/[0.03]">
              <div className="text-[10px] uppercase tracking-widest text-blue-300/80 mb-2 flex items-center gap-2">
                <span>Decisiones (institucional)</span>
                <span className="text-muted-foreground/60 normal-case tracking-normal text-[10px]" title="Una decisión = una compra y todas sus ventas parciales. WR y total R agregan ejecuciones de la misma entrada como una unidad.">
                  ⓘ
                </span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
                <Metric label="Decisiones" value={String(stats.decision_overall.n_decisions_total)} />
                <Metric label="Win Rate" value={fmtPct(stats.decision_overall.decision_win_rate)} tone={stats.decision_overall.decision_win_rate != null && stats.decision_overall.decision_win_rate >= 0.4 ? 'pos' : 'neg'} />
                <Metric label="Total R (weighted)" value={stats.decision_overall.decision_total_r != null ? `${stats.decision_overall.decision_total_r >= 0 ? '+' : ''}${stats.decision_overall.decision_total_r.toFixed(2)} R` : '—'} tone={(stats.decision_overall.decision_total_r ?? 0) >= 0 ? 'pos' : 'neg'} />
                <Metric label="Resolved / Total" value={`${stats.decision_overall.n_fully_resolved}/${stats.decision_overall.n_decisions_total}`} />
              </div>
              <div className="mt-4 pt-3 border-t border-border/60 grid grid-cols-2 lg:grid-cols-4 gap-2">
                <EconomicMetric label="Ganancia promedio" value={stats.decision_overall.decision_average_gain} tone="pos" />
                <EconomicMetric label="Pérdida promedio" value={stats.decision_overall.decision_average_loss} tone="neg" />
                <EconomicMetric label="Ganancias acumuladas" value={stats.decision_overall.decision_total_gains} tone="pos" />
                <EconomicMetric label="Pérdidas acumuladas" value={stats.decision_overall.decision_total_losses} tone="neg" />
              </div>
              <div className="mt-3 text-[10px] text-muted-foreground flex flex-wrap gap-3">
                {stats.decision_overall.n_partially_resolved > 0 && <span>Partials: {stats.decision_overall.n_partially_resolved}</span>}
                {stats.decision_overall.n_fully_open > 0 && <span>Open: {stats.decision_overall.n_fully_open}</span>}
              </div>
            </Card>

            <details className="group" open>
              <summary className="cursor-pointer list-none px-4 py-2 bg-muted/30 border border-border rounded text-[10px] uppercase tracking-widest text-muted-foreground hover:bg-muted/50 select-none flex items-center justify-between">
                <span>Evolución del win rate · cómo fuiste performando</span>
                <span className="text-muted-foreground/60 group-open:rotate-90 transition-transform">▸</span>
              </summary>
              <Card className="p-3 mt-2">
                <WinRateEvolutionChart
                  data={stats.win_rate_evolution}
                  rollingWindow={stats.rolling_window}
                  onOpenDecision={openDecisionDetail}
                />
              </Card>
            </details>

            <div className="flex items-center gap-4 text-[11px] text-muted-foreground flex-wrap">
              <span title="Suma de R-multiples — invariante a cambios de tamaño de posición">
                R total: <span className={`tabular-nums ${colorPnl(stats.overall.total_r)}`}>{stats.overall.total_r != null ? `${stats.overall.total_r >= 0 ? '+' : ''}${stats.overall.total_r.toFixed(2)} R` : '—'}</span>
              </span>
              <span>·</span>
              <span title="P&L en dólares — afectado por cambios de tamaño de posición a lo largo del tiempo">
                P&L $: <span className={`tabular-nums ${colorPnl(stats.overall.total_pnl)}`}>{fmtMoney(stats.overall.total_pnl)}</span>
              </span>
              <span>·</span>
              <span>PF: <span className={`tabular-nums ${(stats.overall.profit_factor ?? 0) >= 1 ? 'text-green-400' : 'text-red-400'}`}>{fmtNum(stats.overall.profit_factor)}</span></span>
              <span>·</span>
              <span className="inline-flex items-center gap-1">
                <Link2 className="w-3 h-3" />
                {stats.linked_to_observations}/{stats.overall.n} linked
              </span>
              {stats.underpowered_buckets > 0 && (
                <>
                  <span>·</span>
                  <span className="inline-flex items-center gap-1 text-amber-400">
                    <AlertTriangle className="w-3 h-3" />
                    {stats.underpowered_buckets} buckets n &lt; 5
                  </span>
                </>
              )}
            </div>

            <div>
              <div className="rounded border border-border bg-muted/30 overflow-hidden">
                <button
                  type="button"
                  aria-expanded={closedSectionOpen}
                  aria-controls="closed-trades-list"
                  onClick={() => setClosedSectionOpen(open => !open)}
                  className="w-full px-4 py-2 text-[10px] uppercase tracking-widest text-muted-foreground hover:bg-muted/50 select-none flex items-center justify-between"
                >
                  <span>
                    Operaciones cerradas ({filteredDecisionGroups.length}
                    {tradeFilter !== 'all' ? ` de ${realizedDecisionGroups.length}` : ''})
                    {tradeFilter !== 'all' ? ` · ${outcomeLabel(tradeFilter)}` : ''}
                  </span>
                  <span className={`text-muted-foreground/60 transition-transform ${closedSectionOpen ? 'rotate-90' : ''}`}>▸</span>
                </button>
                <div
                  role="group"
                  aria-label="Filtrar operaciones cerradas"
                  className="px-4 py-2 border-t border-border/70 flex flex-wrap items-center gap-2"
                >
                  <span className="text-[9px] uppercase tracking-widest text-muted-foreground mr-1">Filtrar operaciones</span>
                  <OutcomeFilterButton label="Todos" count={realizedDecisionGroups.length} active={tradeFilter === 'all'} onClick={() => selectTradeFilter('all')} tone="all" />
                  <OutcomeFilterButton label="Ganados" count={stats.decision_overall.decision_wins} active={tradeFilter === 'win'} onClick={() => selectTradeFilter('win')} tone="win" />
                  <OutcomeFilterButton label="Pérdidas" count={stats.decision_overall.decision_losses} active={tradeFilter === 'loss'} onClick={() => selectTradeFilter('loss')} tone="loss" />
                  <OutcomeFilterButton label="Break even" count={stats.decision_overall.decision_breakeven} active={tradeFilter === 'breakeven'} onClick={() => selectTradeFilter('breakeven')} tone="breakeven" />
                </div>
              </div>
              {closedSectionOpen && (
                <div id="closed-trades-list">
                  <ClosedTradesTable
                    groups={filteredDecisionGroups}
                    focusRequest={focusRequest}
                    onEdit={setEditTarget}
                    onDelete={deleteTrade}
                  />
                </div>
              )}
            </div>

            <details className="group" open>
              <summary className="cursor-pointer list-none px-4 py-2 bg-muted/30 border border-border rounded text-[10px] uppercase tracking-widest text-muted-foreground hover:bg-muted/50 select-none flex items-center justify-between">
                <span>¿Qué setup funciona en qué contexto? · Setup × Régimen (engine)</span>
                <span className="text-muted-foreground/60 group-open:rotate-90 transition-transform">▸</span>
              </summary>
              <Card className="p-3 mt-2 space-y-3">
                <SetupRegimeToolbar
                  rows={stats.by_setup_regime_matrix}
                  onBackfill={backfillRegime}
                  backfilling={backfilling}
                />
                <SetupRegimeHeatmap rows={stats.by_setup_regime_matrix} />
              </Card>
            </details>

            <details className="group">
              <summary className="cursor-pointer list-none px-4 py-2 bg-muted/30 border border-border rounded text-[10px] uppercase tracking-widest text-muted-foreground hover:bg-muted/50 select-none flex items-center justify-between">
                <span>R unit Trend · evolución mensual del sizing</span>
                <span className="text-muted-foreground/60 group-open:rotate-90 transition-transform">▸</span>
              </summary>
              <Card className="p-0 overflow-hidden mt-2">
                <RiskEvolutionTable rows={stats.risk_evolution} />
              </Card>
            </details>
          </>
        )}
      </div>

      {showNew && vocab && (
        <NewTradeModal vocab={vocab} onClose={() => setShowNew(false)} onSaved={reload} />
      )}
      {closeTarget && vocab && (
        <CloseTradeModal trade={closeTarget} defaultCommission={vocab.default_commission}
          onClose={() => setCloseTarget(null)} onSaved={reload} />
      )}
      {editTarget && vocab && (
        <EditTradeModal trade={editTarget} vocab={vocab}
          onClose={() => setEditTarget(null)} onSaved={reload} />
      )}
    </DashboardLayout>
  )
}

interface OpenPositionGroup {
  symbol: string
  legs: Trade[]
  entryDate: string | null
  setup: string
  context: string
  averageEntry: number
  totalQty: number
  stopPrice: number | null
  multipleStops: boolean
  risk: number | null
}

function buildOpenPositionGroups(trades: Trade[]): OpenPositionGroup[] {
  return buildPositionGroups(trades.filter(trade => trade.is_open && trade.setup !== 'dca'))
}

function buildDcaPositionGroups(trades: Trade[]): OpenPositionGroup[] {
  return buildPositionGroups(trades.filter(trade => trade.is_open && trade.setup === 'dca'))
}

function buildPositionGroups(trades: Trade[]): OpenPositionGroup[] {
  const bySymbol = new Map<string, Trade[]>()
  for (const trade of trades) {
    const current = bySymbol.get(trade.symbol)
    if (current) current.push(trade)
    else bySymbol.set(trade.symbol, [trade])
  }

  return [...bySymbol.entries()].map(([symbol, rawLegs]) => {
    const legs = [...rawLegs].sort(
      (a, b) => (a.entry_date ?? '').localeCompare(b.entry_date ?? '') || a.id - b.id,
    )
    const totalQty = legs.reduce((sum, leg) => sum + leg.qty, 0)
    const stops = [...new Set(legs.map(leg => leg.stop_price))]
    const risks = legs.map(leg => leg.stop_price == null
      ? null
      : Math.max((leg.entry_price - leg.stop_price) * leg.qty, 0))
    const setups = [...new Set(legs.map(leg => leg.setup))]
    const contexts = [...new Set(legs.map(leg => leg.context))]
    return {
      symbol,
      legs,
      entryDate: legs[0]?.entry_date ?? null,
      setup: setups.length === 1 ? setups[0] : 'mixto',
      context: contexts.length === 1 ? contexts[0] : 'mixto',
      averageEntry: totalQty > 0
        ? legs.reduce((sum, leg) => sum + leg.entry_price * leg.qty, 0) / totalQty
        : 0,
      totalQty,
      stopPrice: stops.length === 1 ? stops[0] : null,
      multipleStops: stops.length > 1,
      risk: risks.every(value => value != null)
        ? risks.reduce<number>((sum, value) => sum + (value ?? 0), 0)
        : null,
    }
  }).sort((a, b) => (b.entryDate ?? '').localeCompare(a.entryDate ?? '') || a.symbol.localeCompare(b.symbol))
}

function HoldingActions({
  trade, onEdit, onDelete,
}: {
  trade: Trade
  onEdit: (trade: Trade) => void
  onDelete: (id: number) => void
}) {
  return (
    <div className="flex items-center gap-1 justify-end" onClick={event => event.stopPropagation()}>
      <button onClick={() => onEdit(trade)} className="p-1 text-muted-foreground hover:text-foreground" title="Editar compra"><Pencil className="w-3 h-3" /></button>
      <button onClick={() => onDelete(trade.id)} className="p-1 text-muted-foreground hover:text-red-400" title="Borrar compra"><Trash2 className="w-3 h-3" /></button>
    </div>
  )
}

function DcaPositionsTable({
  groups, onEdit, onDelete,
}: {
  groups: OpenPositionGroup[]
  onEdit: (trade: Trade) => void
  onDelete: (id: number) => void
}) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  function toggle(symbol: string) {
    setExpanded(previous => {
      const next = new Set(previous)
      if (next.has(symbol)) next.delete(symbol)
      else next.add(symbol)
      return next
    })
  }

  return (
    <Card className="p-0 overflow-hidden border-violet-500/30 bg-violet-500/5">
      <div className="px-4 py-2 bg-violet-500/10 border-b border-violet-500/20 flex items-center justify-between gap-3">
        <span className="text-[10px] uppercase tracking-widest text-violet-300">Posiciones DCA · {groups.length}</span>
        <span className="text-[10px] text-muted-foreground">No afectan las métricas del Journal</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="border-b border-border">
            <tr className="text-left text-[10px] uppercase tracking-widest text-muted-foreground">
              <th className="px-2 py-2 w-6"></th>
              <th className="px-3 py-2 font-medium">Primera compra</th>
              <th className="px-3 py-2 font-medium">Activo</th>
              <th className="px-3 py-2 font-medium text-right">Precio prom.</th>
              <th className="px-3 py-2 font-medium text-right">Cantidad</th>
              <th className="px-3 py-2 font-medium text-right">Capital invertido</th>
              <th className="px-3 py-2 font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {groups.map(group => {
              const multiple = group.legs.length > 1
              const isExpanded = expanded.has(group.symbol)
              const single = group.legs[0]
              const invested = group.legs.reduce((sum, leg) => sum + leg.entry_price * leg.qty, 0)
              return (
                <Fragment key={group.symbol}>
                  <tr
                    className={`border-b border-border/50 last:border-0 hover:bg-muted/20 ${multiple ? 'cursor-pointer' : ''}`}
                    onClick={() => multiple && toggle(group.symbol)}
                  >
                    <td className="px-2 py-2 text-center text-muted-foreground/60">
                      {multiple && <span className={`inline-block transition-transform ${isExpanded ? 'rotate-90' : ''}`}>▸</span>}
                    </td>
                    <td className="px-3 py-2 font-mono text-muted-foreground">{group.entryDate}</td>
                    <td className="px-3 py-2 font-semibold text-foreground">
                      {group.symbol}
                      {multiple && <span className="ml-2 rounded border border-violet-500/30 bg-violet-500/15 px-1.5 py-0.5 text-[9px] text-violet-300">{group.legs.length} compras</span>}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">${group.averageEntry.toFixed(2)}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">{group.totalQty}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-violet-300">${invested.toFixed(2)}</td>
                    <td className="px-3 py-2">
                      {single && !multiple && <HoldingActions trade={single} onEdit={onEdit} onDelete={onDelete} />}
                    </td>
                  </tr>
                  {multiple && isExpanded && (
                    <tr className="border-b border-border/50 bg-muted/10">
                      <td></td>
                      <td colSpan={6} className="px-3 py-2">
                        <div className="space-y-1">
                          {group.legs.map(leg => (
                            <div key={leg.id} className="grid grid-cols-[110px_1fr_auto_auto] items-center gap-3 rounded border border-border/50 bg-background/30 px-3 py-2">
                              <span className="font-mono text-[10px] text-muted-foreground">{leg.entry_date}</span>
                              <span className="text-[11px] text-muted-foreground">Compra #{leg.id} · {leg.qty} @ ${leg.entry_price.toFixed(2)}</span>
                              <span className="text-[10px] text-violet-300">${(leg.entry_price * leg.qty).toFixed(2)}</span>
                              <HoldingActions trade={leg} onEdit={onEdit} onDelete={onDelete} />
                            </div>
                          ))}
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

function OpenTradeActions({
  trade, onClose, onEdit, onDelete,
}: {
  trade: Trade
  onClose: (trade: Trade) => void
  onEdit: (trade: Trade) => void
  onDelete: (id: number) => void
}) {
  return (
    <div className="flex items-center gap-1 justify-end" onClick={event => event.stopPropagation()}>
      <button onClick={() => onClose(trade)} className="text-[10px] px-2 py-1 rounded bg-red-500/15 border border-red-500/30 text-red-300 hover:bg-red-500/25">Cerrar</button>
      <button onClick={() => onEdit(trade)} className="p-1 text-muted-foreground hover:text-foreground" title="Editar"><Pencil className="w-3 h-3" /></button>
      <button onClick={() => onDelete(trade.id)} className="p-1 text-muted-foreground hover:text-red-400" title="Borrar"><Trash2 className="w-3 h-3" /></button>
    </div>
  )
}

function OpenPositionsTable({
  groups, onClose, onEdit, onDelete,
}: {
  groups: OpenPositionGroup[]
  onClose: (trade: Trade) => void
  onEdit: (trade: Trade) => void
  onDelete: (id: number) => void
}) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  function toggle(symbol: string) {
    setExpanded(previous => {
      const next = new Set(previous)
      if (next.has(symbol)) next.delete(symbol)
      else next.add(symbol)
      return next
    })
  }

  return (
    <Card className="p-0 overflow-hidden border-blue-500/30 bg-blue-500/5">
      <div className="px-4 py-2 bg-blue-500/10 border-b border-blue-500/20 flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-widest text-blue-300">Posiciones abiertas · {groups.length}</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="border-b border-border">
            <tr className="text-left text-[10px] uppercase tracking-widest text-muted-foreground">
              <th className="px-2 py-2 w-6"></th>
              <th className="px-3 py-2 font-medium">Entry</th>
              <th className="px-3 py-2 font-medium">Symbol</th>
              <th className="px-3 py-2 font-medium">Setup</th>
              <th className="px-3 py-2 font-medium">Contexto</th>
              <th className="px-3 py-2 font-medium text-right">Entry prom.</th>
              <th className="px-3 py-2 font-medium text-right">Qty</th>
              <th className="px-3 py-2 font-medium text-right">Stop</th>
              <th className="px-3 py-2 font-medium text-right">Risk</th>
              <th className="px-3 py-2 font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {groups.map(group => {
              const multiple = group.legs.length > 1
              const isExpanded = expanded.has(group.symbol)
              const single = group.legs[0]
              return (
                <Fragment key={group.symbol}>
                  <tr
                    className={`border-b border-border/50 last:border-0 hover:bg-muted/20 ${multiple ? 'cursor-pointer' : ''}`}
                    onClick={() => multiple && toggle(group.symbol)}
                  >
                    <td className="px-2 py-2 text-center text-muted-foreground/60">
                      {multiple && <span className={`inline-block transition-transform ${isExpanded ? 'rotate-90' : ''}`}>▸</span>}
                    </td>
                    <td className="px-3 py-2 font-mono text-muted-foreground">{group.entryDate}</td>
                    <td className="px-3 py-2 font-semibold text-foreground">
                      {group.symbol}
                      {multiple && <span className="ml-2 rounded border border-blue-500/30 bg-blue-500/15 px-1.5 py-0.5 text-[9px] text-blue-300">{group.legs.length} compras</span>}
                    </td>
                    <td className="px-3 py-2 text-muted-foreground">{group.setup}</td>
                    <td className="px-3 py-2 text-muted-foreground">{group.context}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">${group.averageEntry.toFixed(2)}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">{group.totalQty}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">
                      {group.multipleStops ? 'varios' : group.stopPrice != null ? `$${group.stopPrice.toFixed(2)}` : '—'}
                    </td>
                    <td className={`px-3 py-2 text-right tabular-nums ${group.risk === 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {group.risk != null ? (group.risk === 0 ? '$0.00' : `-$${group.risk.toFixed(2)}`) : '—'}
                    </td>
                    <td className="px-3 py-2">
                      {single && !multiple && <OpenTradeActions trade={single} onClose={onClose} onEdit={onEdit} onDelete={onDelete} />}
                    </td>
                  </tr>
                  {multiple && isExpanded && (
                    <tr className="border-b border-border/50 bg-muted/10">
                      <td></td>
                      <td colSpan={9} className="px-3 py-2">
                        <div className="space-y-1">
                          {group.legs.map(leg => (
                            <div key={leg.id} className="grid grid-cols-[110px_1fr_auto_auto] items-center gap-3 rounded border border-border/50 bg-background/30 px-3 py-2">
                              <span className="font-mono text-[10px] text-muted-foreground">{leg.entry_date}</span>
                              <span className="text-[11px] text-muted-foreground">Compra #{leg.id} · {leg.qty} @ ${leg.entry_price.toFixed(2)}</span>
                              <span className="text-[10px] text-muted-foreground">Stop {leg.stop_price != null ? `$${leg.stop_price.toFixed(2)}` : '—'}</span>
                              <OpenTradeActions trade={leg} onClose={onClose} onEdit={onEdit} onDelete={onDelete} />
                            </div>
                          ))}
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: 'pos' | 'neg' }) {
  const color = tone === 'pos' ? 'text-green-400' : tone === 'neg' ? 'text-red-400' : 'text-foreground'
  return (
    <div>
      <div className={`text-xl font-bold tabular-nums ${color}`}>{value}</div>
      <div className="text-[10px] text-muted-foreground uppercase tracking-widest">{label}</div>
    </div>
  )
}

function EconomicMetric({ label, value, tone }: { label: string; value: number | null; tone: 'pos' | 'neg' }) {
  return (
    <div className="rounded border border-border/60 bg-background/30 px-3 py-2">
      <div className={`text-base font-semibold tabular-nums ${tone === 'pos' ? 'text-green-400' : 'text-red-400'}`}>
        {fmtMoney(value)}
      </div>
      <div className="text-[9px] uppercase tracking-wider text-muted-foreground">{label}</div>
    </div>
  )
}

function OutcomeFilterButton({
  label, count, active, onClick, tone,
}: {
  label: string
  count: number
  active: boolean
  onClick: () => void
  tone: 'all' | DecisionOutcome
}) {
  const activeClass = tone === 'win'
    ? 'border-green-400/70 bg-green-500/20 text-green-200'
    : tone === 'loss'
      ? 'border-red-400/70 bg-red-500/20 text-red-200'
      : tone === 'breakeven'
        ? 'border-amber-400/70 bg-amber-500/20 text-amber-200'
        : 'border-blue-400/70 bg-blue-500/20 text-blue-200'
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={`rounded-full border px-2.5 py-1 text-[10px] tabular-nums transition-colors focus:outline-none focus:ring-1 focus:ring-blue-400/70 ${active ? activeClass : 'border-border bg-card text-muted-foreground hover:text-foreground hover:bg-muted/50'}`}
      title={`Mostrar solo operaciones ${label.toLowerCase()}`}
    >
      {label} · {count}
    </button>
  )
}

function outcomeLabel(outcome: TradeFilter): string {
  if (outcome === 'win') return 'Ganados'
  if (outcome === 'loss') return 'Pérdidas'
  if (outcome === 'breakeven') return 'Break even'
  return 'Todos'
}

// One closed "operation" = one original Compra and all its partial sells, linked
// by decision_id. Trading the same symbol twice produces two separate decisions
// (two rows). The collapsed row aggregates the decision; expanding reveals each
// partial sell.
interface DecisionGroup {
  decisionId: number
  rep: Trade
  symbol: string
  setup: string
  context: string
  entryDate: string | null
  outcome: DecisionOutcome | null
  resultDetail: 'runner_breakeven' | null
  legs: Trade[]
  totalQty: number
  totalPnl: number
  weightedR: number | null
  linked: boolean
}

function buildDecisionGroups(trades: Trade[]): DecisionGroup[] {
  const byDecision = new Map<number, Trade[]>()
  for (const t of trades) {
    const arr = byDecision.get(t.decision_id)
    if (arr) arr.push(t)
    else byDecision.set(t.decision_id, [t])
  }

  const groups: DecisionGroup[] = []
  for (const [decisionId, legsRaw] of byDecision) {
    // Chronological: partial sells in the order they were executed.
    const legs = [...legsRaw].sort(
      (a, b) => (a.exit_date ?? '').localeCompare(b.exit_date ?? '') || a.id - b.id
    )
    // Representative = the original Compra leg (no parent). Falls back to the
    // earliest leg for decisions whose runner is still open (rep not in closed set).
    const rep = legs.find(l => l.parent_trade_id == null) ?? legs[0]
    const totalPnl = legs.reduce((s, l) => s + (l.pnl_dollars ?? 0), 0)
    // Qty-weighted R — matches the backend's decision-level R convention.
    const rLegs = legs.filter(l => l.r_multiple != null && l.qty)
    const totQty = rLegs.reduce((s, l) => s + l.qty, 0)
    const weightedR = rLegs.length && totQty > 0
      ? rLegs.reduce((s, l) => s + (l.r_multiple as number) * l.qty, 0) / totQty
      : null
    groups.push({
      decisionId,
      rep,
      symbol: rep.symbol,
      setup: rep.setup,
      context: rep.context,
      entryDate: rep.entry_date,
      outcome: rep.decision_outcome ?? legs.find(leg => leg.decision_outcome != null)?.decision_outcome ?? null,
      resultDetail: rep.decision_result_detail ?? legs.find(leg => leg.decision_result_detail != null)?.decision_result_detail ?? null,
      legs,
      totalQty: legs.reduce((s, l) => s + (l.qty ?? 0), 0),
      totalPnl,
      weightedR,
      linked: legs.some(l => l.linked_observation_id != null),
    })
  }

  // Most recent entry first; tiebreak by decisionId so order is stable.
  groups.sort(
    (a, b) => (b.entryDate ?? '').localeCompare(a.entryDate ?? '') || b.decisionId - a.decisionId
  )
  return groups
}

function ClosedTradesTable({
  groups, focusRequest, onEdit, onDelete,
}: {
  groups: DecisionGroup[]
  focusRequest: { decisionId: number; nonce: number } | null
  onEdit: (t: Trade) => void
  onDelete: (id: number) => void
}) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set())

  useEffect(() => {
    if (!focusRequest) return
    queueMicrotask(() => setExpanded(prev => new Set(prev).add(focusRequest.decisionId)))
    window.requestAnimationFrame(() => {
      document.getElementById(`journal-decision-${focusRequest.decisionId}`)?.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      })
    })
  }, [focusRequest])

  function toggle(id: number) {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <Card className="p-0 overflow-hidden mt-2">
      {groups.length === 0 ? (
        <div className="px-4 py-5 text-xs text-muted-foreground">
          No hay operaciones en esta categoría. Elegí “Todos” para limpiar el filtro.
        </div>
      ) : (
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="border-b border-border">
            <tr className="text-left text-[10px] uppercase tracking-widest text-muted-foreground">
              <th className="px-2 py-2 w-6"></th>
              <th className="px-3 py-2 font-medium">Entry</th>
              <th className="px-3 py-2 font-medium">Symbol</th>
              <th className="px-3 py-2 font-medium">Setup</th>
              <th className="px-3 py-2 font-medium">Contexto</th>
              <th className="px-3 py-2 font-medium text-right">P&L</th>
              <th className="px-3 py-2 font-medium text-right">R</th>
              <th className="px-3 py-2 font-medium text-center" title="Ejecuciones (ventas) de la operación">Ej.</th>
              <th className="px-3 py-2 font-medium text-center">Obs</th>
            </tr>
          </thead>
          <tbody>
            {groups.map(g => {
              const multi = g.legs.length > 1
              const isExpanded = expanded.has(g.decisionId)
              return (
                <Fragment key={g.decisionId}>
                  <tr
                    id={`journal-decision-${g.decisionId}`}
                    className="border-b border-border/50 last:border-0 hover:bg-muted/20 cursor-pointer"
                    onClick={() => toggle(g.decisionId)}
                  >
                    <td className="px-2 py-2 text-center">
                      <span className={`inline-block text-muted-foreground/60 transition-transform ${isExpanded ? 'rotate-90' : ''}`}>▸</span>
                    </td>
                    <td className="px-3 py-2 font-mono text-muted-foreground">{g.entryDate}</td>
                    <td className="px-3 py-2 font-semibold text-foreground">{g.symbol}</td>
                    <td className="px-3 py-2 text-muted-foreground">{g.setup}</td>
                    <td className="px-3 py-2 text-muted-foreground">{g.context}</td>
                    <td className="px-3 py-2 text-right">
                      <div className={`tabular-nums ${colorPnl(g.totalPnl)}`}>{fmtMoney(g.totalPnl)}</div>
                      {g.resultDetail === 'runner_breakeven' && <RunnerBreakEvenBadge />}
                    </td>
                    <td className={`px-3 py-2 text-right tabular-nums ${colorPnl(g.weightedR)}`}>{fmtNum(g.weightedR)}</td>
                    <td className="px-3 py-2 text-center tabular-nums text-muted-foreground">
                      {multi
                        ? <span className="inline-block text-[10px] px-1.5 py-0.5 rounded bg-blue-500/15 border border-blue-500/30 text-blue-300">{g.legs.length}</span>
                        : <span className="text-muted-foreground/40">1</span>}
                    </td>
                    <td className="px-3 py-2 text-center">
                      {g.linked
                        ? <Link2 className="w-3 h-3 inline text-green-400" />
                        : <span className="text-muted-foreground/40">—</span>}
                    </td>
                  </tr>
                  {isExpanded && (
                    <tr className="border-b border-border/50 last:border-0 bg-muted/10">
                      <td className="px-2 py-0"></td>
                      <td colSpan={8} className="px-3 py-3">
                        <DecisionDetail group={g} onEdit={onEdit} onDelete={onDelete} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
      )}
    </Card>
  )
}

function DetailField({ label, value }: { label: string; value: React.ReactNode }) {
  if (value == null || value === '') return null
  return (
    <span className="text-[11px] text-muted-foreground">
      <span className="text-muted-foreground/50 uppercase tracking-wider text-[9px]">{label} </span>
      <span className="text-foreground/80">{value}</span>
    </span>
  )
}

function DecisionDetail({
  group, onEdit, onDelete,
}: {
  group: DecisionGroup
  onEdit: (t: Trade) => void
  onDelete: (id: number) => void
}) {
  const { rep } = group
  return (
    <div className="space-y-3">
      {/* Entry-level info shared by the whole decision */}
      <div className="flex flex-wrap gap-x-5 gap-y-1">
        <DetailField label="Entry $" value={rep.entry_price != null ? `$${rep.entry_price.toFixed(2)}` : null} />
        <DetailField label="Qty" value={group.totalQty || null} />
        <DetailField label="Stop" value={rep.initial_stop_price != null ? `$${rep.initial_stop_price.toFixed(2)}` : (rep.stop_price != null ? `$${rep.stop_price.toFixed(2)}` : null)} />
        <DetailField label="Risk %" value={rep.risk_pct_of_account != null ? `${(rep.risk_pct_of_account * 100).toFixed(2)}%` : null} />
        <DetailField label="Entry reason" value={rep.entry_reason} />
        <DetailField label="Regime" value={rep.regime_at_entry} />
        <DetailField label="Score" value={rep.system_score_at_entry != null ? rep.system_score_at_entry.toFixed(0) : null} />
        <DetailField label="Group" value={rep.group_strength_at_entry} />
        <DetailField label="From queue" value={rep.from_queue == null ? null : (rep.from_queue ? 'sí' : 'no')} />
        {group.resultDetail === 'runner_breakeven' && (
          <DetailField label="Resultado" value={<RunnerBreakEvenBadge />} />
        )}
      </div>

      {/* Executions: one row per leg (partial sells + final exit) */}
      <div className="rounded border border-border/60 overflow-hidden">
        <table className="w-full text-[11px]">
          <thead className="bg-muted/30">
            <tr className="text-left text-[9px] uppercase tracking-wider text-muted-foreground">
              <th className="px-2 py-1.5 font-medium">Salida</th>
              <th className="px-2 py-1.5 font-medium">Tipo</th>
              <th className="px-2 py-1.5 font-medium">Motivo</th>
              <th className="px-2 py-1.5 font-medium text-right">Qty @ precio</th>
              <th className="px-2 py-1.5 font-medium text-right">P&L</th>
              <th className="px-2 py-1.5 font-medium text-right">R</th>
              <th className="px-2 py-1.5 font-medium">Nota</th>
              <th className="px-2 py-1.5 font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {group.legs.map(leg => (
              <tr key={leg.id} className="border-t border-border/40">
                <td className="px-2 py-1.5 font-mono text-muted-foreground/80">{leg.exit_date ?? '—'}</td>
                <td className="px-2 py-1.5 text-muted-foreground/80">
                  {group.legs.length === 1
                    ? 'cierre'
                    : leg.is_runner_breakeven_exit
                      ? 'runner BE'
                      : group.resultDetail === 'runner_breakeven'
                        ? 'toma parcial'
                        : (leg.parent_trade_id == null ? 'salida final' : 'venta parcial')}
                </td>
                <td className="px-2 py-1.5 text-muted-foreground/80">{leg.exit_reason}</td>
                <td className="px-2 py-1.5 text-right tabular-nums text-muted-foreground/80">
                  {leg.qty} @ {leg.exit_price != null ? `$${leg.exit_price.toFixed(2)}` : '—'}
                </td>
                <td className={`px-2 py-1.5 text-right tabular-nums ${colorPnl(leg.pnl_dollars)}`}>{fmtMoney(leg.pnl_dollars)}</td>
                <td className={`px-2 py-1.5 text-right tabular-nums ${colorPnl(leg.r_multiple)}`}>{fmtNum(leg.r_multiple)}</td>
                <td className="px-2 py-1.5 text-muted-foreground/70 max-w-[200px] truncate" title={leg.error_note ?? ''}>{leg.error_note ?? ''}</td>
                <td className="px-2 py-1.5">
                  <div className="flex items-center gap-1 justify-end">
                    <button onClick={() => onEdit(leg)} className="p-1 text-muted-foreground hover:text-foreground" title="Editar"><Pencil className="w-3 h-3" /></button>
                    <button onClick={() => onDelete(leg.id)} className="p-1 text-muted-foreground hover:text-red-400" title="Borrar"><Trash2 className="w-3 h-3" /></button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function RunnerBreakEvenBadge() {
  return (
    <span
      className="mt-1 inline-block whitespace-nowrap rounded border border-green-500/30 bg-green-500/10 px-1.5 py-0.5 text-[9px] font-medium text-green-300"
      title="La operación terminó con ganancia total; el remanente salió exactamente al precio de entrada."
    >
      Ganada parcial · runner BE
    </span>
  )
}

function RiskEvolutionTable({ rows }: { rows: RiskEvolutionRow[] }) {
  if (rows.length === 0) {
    return <div className="px-4 py-3 text-xs text-muted-foreground">Sin trades con entry_date — no hay evolución que mostrar.</div>
  }
  return (
    <table className="w-full text-xs">
      <thead className="border-b border-border">
        <tr className="text-left text-[10px] uppercase tracking-widest text-muted-foreground">
          <th className="px-3 py-2 font-medium">Mes</th>
          <th className="px-3 py-2 font-medium text-right">N</th>
          <th className="px-3 py-2 font-medium text-right">Avg Risk $</th>
          <th className="px-3 py-2 font-medium text-right">Avg Risk %</th>
          <th className="px-3 py-2 font-medium text-right" title="Win rate del mes — excluye scratches (break-even) del denominador.">WR</th>
          <th className="px-3 py-2 font-medium text-right">Total R</th>
          <th className="px-3 py-2 font-medium text-right">Total P&L</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(r => (
          <tr key={r.month} className="border-b border-border/50 last:border-0 hover:bg-muted/20">
            <td className="px-3 py-2 font-mono text-foreground">{r.month}</td>
            <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">{r.n}</td>
            <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">{r.avg_planned_risk_dollars != null ? `$${r.avg_planned_risk_dollars.toFixed(2)}` : '—'}</td>
            <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">{r.avg_risk_pct_of_account != null ? `${(r.avg_risk_pct_of_account * 100).toFixed(2)}%` : '—'}</td>
            <td className="px-3 py-2 text-right tabular-nums text-muted-foreground" title={r.win_rate != null ? `${r.wins}W / ${r.losses}L` : 'sin trades resueltos'}>{r.win_rate != null ? `${(r.win_rate * 100).toFixed(0)}%` : '—'}</td>
            <td className={`px-3 py-2 text-right tabular-nums ${colorPnl(r.total_r)}`}>{r.total_r != null ? `${r.total_r >= 0 ? '+' : ''}${r.total_r.toFixed(2)} R` : '—'}</td>
            <td className={`px-3 py-2 text-right tabular-nums ${colorPnl(r.total_pnl)}`}>{fmtMoney(r.total_pnl)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

// Descriptor rankings (best → worst) for ordering regime columns so the heatmap
// reads naturally: favorable contexts on the left, deteriorating ones to the
// right. Composite regime is "<participation>/<leadership>".
const PARTICIPATION_ORDER = ['EXPANDING', 'STABLE', 'NARROWING', 'COLLAPSING']
const LEADERSHIP_ORDER = ['EXPANDING', 'HEALTHY', 'THINNING', 'EXHAUSTED', 'COLLAPSING']

function regimeFavorability(regime: string): number {
  const [part, lead] = regime.split('/')
  const p = PARTICIPATION_ORDER.indexOf(part)
  const l = LEADERSHIP_ORDER.indexOf(lead)
  return (p === -1 ? 99 : p) * 10 + (l === -1 ? 9 : l)
}

// Diverging color scale on avg R (the system's decision unit — comparable across
// setups). Green = the combination paid; red = it bled.
function avgRCell(r: number | null): string {
  if (r == null) return 'bg-muted/20 text-muted-foreground/70'
  if (r >= 0.75) return 'bg-green-500/30 text-green-100'
  if (r >= 0.25) return 'bg-green-500/15 text-green-300'
  if (r > -0.25) return 'bg-muted/40 text-muted-foreground'
  if (r > -0.75) return 'bg-red-500/15 text-red-300'
  return 'bg-red-500/30 text-red-100'
}

function SetupRegimeToolbar({
  rows, onBackfill, backfilling,
}: {
  rows: SetupRegimeMatrixRow[]
  onBackfill: () => void
  backfilling: boolean
}) {
  const sinData = rows.filter(r => r.regime_at_entry === 'sin data').reduce((s, r) => s + r.n, 0)
  return (
    <div className="flex items-center justify-between gap-3 flex-wrap">
      <div className="flex items-center gap-2 text-[10px] text-muted-foreground flex-wrap">
        <span>avg R por celda:</span>
        <span className="px-1.5 py-0.5 rounded bg-red-500/30 text-red-100">≤ -0.75</span>
        <span className="px-1.5 py-0.5 rounded bg-red-500/15 text-red-300">&lt; 0</span>
        <span className="px-1.5 py-0.5 rounded bg-muted/40 text-muted-foreground">≈ 0</span>
        <span className="px-1.5 py-0.5 rounded bg-green-500/15 text-green-300">&gt; 0</span>
        <span className="px-1.5 py-0.5 rounded bg-green-500/30 text-green-100">≥ +0.75</span>
        <span className="text-muted-foreground/50">· celda con borde ámbar = n &lt; 5 (poca evidencia)</span>
      </div>
      {sinData > 0 && (
        <button
          onClick={onBackfill}
          disabled={backfilling}
          className="inline-flex items-center gap-1.5 text-[11px] px-2.5 py-1.5 rounded bg-blue-500/20 border border-blue-500/40 text-blue-300 hover:bg-blue-500/30 disabled:opacity-50 whitespace-nowrap"
          title="Reconstruye el régimen objetivo del mercado en la fecha de entrada de los trades que hoy figuran 'sin data'."
        >
          {backfilling ? 'Reconstruyendo…' : `Reconstruir contexto (${sinData} sin data)`}
        </button>
      )}
    </div>
  )
}

function SetupRegimeHeatmap({ rows }: { rows: SetupRegimeMatrixRow[] }) {
  const { setups, regimes, cells } = useMemo(() => {
    const setupN = new Map<string, number>()
    const regimeSet = new Set<string>()
    const cells = new Map<string, SetupRegimeMatrixRow>()
    for (const r of rows) {
      setupN.set(r.setup, (setupN.get(r.setup) ?? 0) + r.n)
      regimeSet.add(r.regime_at_entry)
      cells.set(`${r.setup}|||${r.regime_at_entry}`, r)
    }
    const setups = [...setupN.entries()].sort((a, b) => b[1] - a[1]).map(e => e[0])
    const regimes = [...regimeSet].sort((a, b) => {
      const sa = a === 'sin data' ? 9999 : regimeFavorability(a)
      const sb = b === 'sin data' ? 9999 : regimeFavorability(b)
      return sa - sb
    })
    return { setups, regimes, cells }
  }, [rows])

  if (rows.length === 0) {
    return <div className="px-1 py-3 text-xs text-muted-foreground">Sin trades cerrados — nada que mostrar todavía.</div>
  }

  return (
    <div className="overflow-x-auto">
      <table className="text-xs border-separate border-spacing-1">
        <thead>
          <tr>
            <th className="px-2 py-1 text-left text-[9px] uppercase tracking-widest text-muted-foreground/70 sticky left-0 bg-card z-10">
              Setup ╲ Régimen
            </th>
            {regimes.map(rg => {
              const [part, lead] = rg.split('/')
              return (
                <th key={rg} className="px-2 py-1 text-center font-mono align-bottom" title={rg}>
                  {rg === 'sin data' ? (
                    <span className="text-[9px] italic text-muted-foreground/40">sin data</span>
                  ) : (
                    <div className="leading-tight text-[9px]">
                      <div className="text-muted-foreground">{part}</div>
                      <div className="text-muted-foreground/50">{lead}</div>
                    </div>
                  )}
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          {setups.map(s => (
            <tr key={s}>
              <td className="px-2 py-1 font-mono text-foreground whitespace-nowrap sticky left-0 bg-card z-10">{s}</td>
              {regimes.map(rg => {
                const cell = cells.get(`${s}|||${rg}`)
                if (!cell) {
                  return <td key={rg} className="px-2 py-1 text-center text-muted-foreground/20">·</td>
                }
                const under = cell.n < 5
                const tooltip =
                  `${s} · ${rg}\n` +
                  `N: ${cell.n}\n` +
                  `Win rate: ${fmtPct(cell.win_rate)}\n` +
                  `Avg R: ${fmtNum(cell.avg_r)}\n` +
                  `Total R: ${cell.total_r != null ? (cell.total_r >= 0 ? '+' : '') + cell.total_r.toFixed(2) : '—'}\n` +
                  `Expectancy: ${fmtMoney(cell.expectancy)}\n` +
                  `Total P&L: ${fmtMoney(cell.total_pnl)}`
                return (
                  <td
                    key={rg}
                    title={tooltip}
                    className={`px-2 py-1 text-center rounded tabular-nums cursor-default ${avgRCell(cell.avg_r)} ${under ? 'ring-1 ring-amber-400/40' : ''}`}
                  >
                    <div className="font-semibold">
                      {cell.avg_r != null ? `${cell.avg_r >= 0 ? '+' : ''}${cell.avg_r.toFixed(2)}R` : '—'}
                    </div>
                    <div className="text-[9px] opacity-60">n={cell.n}</div>
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
