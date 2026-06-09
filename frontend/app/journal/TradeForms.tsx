'use client'

import { useState, useEffect } from 'react'
import { API_URL } from '@/lib/utils'
import { X } from 'lucide-react'

export interface Vocab {
  setup_options: string[]
  context_options: string[]
  entry_reason_options: string[]
  exit_reason_options: string[]
  default_commission: number
}

export interface Trade {
  id: number
  symbol: string
  setup: string
  context: string
  entry_date: string | null
  entry_price: number
  qty: number
  stop_price: number | null
  exit_date: string | null
  exit_price: number | null
  duration_days: number | null
  pnl_dollars: number | null
  pnl_pct: number | null
  r_multiple: number | null
  error_note: string | null
  post_venta: string | null
  linked_observation_id: number | null
  is_open: boolean
  from_queue: boolean | null
  entry_reason: string
  exit_reason: string
  planned_risk_dollars: number | null
  account_balance_at_entry: number | null
  effective_risk_dollars: number | null
  risk_pct_of_account: number | null
  regime_at_entry: string | null
  system_score_at_entry: number | null
  group_strength_at_entry: string | null
  leader_health_at_entry: number | null
  initial_stop_price: number | null
  is_risk_free: boolean
  parent_trade_id: number | null
  decision_id: number
}

export interface StopEvent {
  id: number
  old_stop_price: number | null
  new_stop_price: number | null
  kind: string
  occurred_at: string | null
  auto_classified: boolean
}

const ACCOUNT_BALANCE_LS_KEY = 'journal_account_balance'

function loadAccountBalance(): string {
  if (typeof window === 'undefined') return ''
  return window.localStorage.getItem(ACCOUNT_BALANCE_LS_KEY) || ''
}

function saveAccountBalance(value: string) {
  if (typeof window === 'undefined') return
  if (value) window.localStorage.setItem(ACCOUNT_BALANCE_LS_KEY, value)
}

export function StopEventBadge({ kind }: { kind: string }) {
  const styles: Record<string, string> = {
    initial:     'bg-blue-500/15 border-blue-500/30 text-blue-300',
    moved_to_be: 'bg-green-500/15 border-green-500/30 text-green-300',
    trailed_up:  'bg-cyan-500/15 border-cyan-500/30 text-cyan-300',
    widened:     'bg-amber-500/15 border-amber-500/30 text-amber-300',
    removed:     'bg-red-500/15 border-red-500/30 text-red-300',
  }
  const cls = styles[kind] || 'bg-muted/30 border-border text-muted-foreground'
  return (
    <span className={`inline-block text-[10px] px-1.5 py-0.5 rounded border ${cls}`}>
      {kind}
    </span>
  )
}

function RiskPercentBadge({ riskDollars, balance }: { riskDollars: number | null; balance: number | null }) {
  if (riskDollars == null || balance == null || balance <= 0) {
    return <span className="text-muted-foreground/60">Risk %: —</span>
  }
  const pct = riskDollars / balance
  const pctStr = (pct * 100).toFixed(2) + '%'
  let badge = null
  let toneCls = 'text-foreground'
  if (pct >= 0.015) {
    toneCls = 'text-amber-400'
    badge = <span className="inline-flex items-center gap-0.5 ml-2 text-[10px] px-1.5 py-0.5 rounded bg-amber-500/15 border border-amber-500/30 text-amber-300">⚠ sobre-tamaño (&gt;1.5%)</span>
  } else if (pct < 0.001) {
    toneCls = 'text-muted-foreground'
    badge = <span className="inline-flex items-center gap-0.5 ml-2 text-[10px] px-1.5 py-0.5 rounded bg-muted/30 border border-border text-muted-foreground">insignificante (&lt;0.1%)</span>
  }
  return (
    <span>Risk %: <span className={`tabular-nums ${toneCls}`}>{pctStr}</span>{badge}</span>
  )
}

const inputCls = "w-full bg-background border border-border rounded px-2 py-1.5 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-blue-400/50"
const labelCls = "text-[10px] uppercase tracking-widest text-muted-foreground"

function today(): string {
  return new Date().toISOString().slice(0, 10)
}

export interface TradeDraftPrefill {
  symbol: string
  setup: string
  entry_price: number
  stop_price_suggested: number | null
  from_queue: boolean
  entry_reason: string
  regime_at_entry: string | null
  system_score_at_entry: number | null
  group_strength_at_entry: string | null
  leader_health_at_entry: number | null
}

export function NewTradeModal({
  vocab, onClose, onSaved, prefill,
}: {
  vocab: Vocab
  onClose: () => void
  onSaved: () => void
  prefill?: TradeDraftPrefill
}) {
  const hasPrefill = !!prefill
  const [symbol, setSymbol] = useState(prefill?.symbol ?? '')
  const [entryDate, setEntryDate] = useState(today())
  const [entryPrice, setEntryPrice] = useState(prefill?.entry_price != null ? String(prefill.entry_price) : '')
  const [qty, setQty] = useState('')
  const [stopPrice, setStopPrice] = useState(prefill?.stop_price_suggested != null ? String(prefill.stop_price_suggested) : '')
  const [setup, setSetup] = useState(prefill?.setup ?? vocab.setup_options[0])
  // context manual deprecated — regime_at_entry from engine replaces it.
  // Field stays in payload as 'unknown' default so backend NOT NULL stays happy.
  const [entryReason, setEntryReason] = useState(prefill?.entry_reason ?? 'discretionary')
  const [plannedRiskDollars, setPlannedRiskDollars] = useState('')
  const [accountBalance, setAccountBalance] = useState(loadAccountBalance())
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const entryNum = parseFloat(entryPrice)
  const stopNum = parseFloat(stopPrice)
  const qtyNum = parseFloat(qty)
  const riskPerShare = stopNum && entryNum ? entryNum - stopNum : null
  const totalRisk = riskPerShare != null && qtyNum ? riskPerShare * qtyNum : null
  const costTotal = entryNum && qtyNum ? entryNum * qtyNum + vocab.default_commission : null
  // Live effective risk: planned wins, else infer from stop. Drives the Risk % badge.
  const plannedRiskNum = parseFloat(plannedRiskDollars)
  const balanceNum = parseFloat(accountBalance)
  const effectiveRisk = plannedRiskNum > 0 ? plannedRiskNum : (totalRisk && totalRisk > 0 ? totalRisk : null)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true); setErr(null)
    try {
      const body: any = {
        symbol, entry_date: entryDate,
        entry_price: entryNum, qty: qtyNum,
        setup, context: 'unknown',
        entry_reason: entryReason,
      }
      if (stopPrice) body.stop_price = stopNum
      if (plannedRiskNum > 0) body.planned_risk_dollars = plannedRiskNum
      if (balanceNum > 0) {
        body.account_balance_at_entry = balanceNum
        saveAccountBalance(accountBalance)
      }
      // When prefilled from queue, persist the provenance flag
      if (hasPrefill && prefill?.from_queue) body.from_queue = true
      const res = await fetch(`${API_URL}/api/v1/journal/trades`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      })
      if (!res.ok) {
        const d = await res.json().catch(() => ({}))
        throw new Error(d.detail || `HTTP ${res.status}`)
      }
      onSaved()
      onClose()
    } catch (e: any) {
      setErr(e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <ModalShell title={hasPrefill ? `Tomar trade desde queue · ${prefill?.symbol} · ${prefill?.setup}` : "Nuevo trade"} onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        {hasPrefill && (
          <div className="border border-blue-500/30 bg-blue-500/[0.06] rounded p-3 text-[11px] space-y-1">
            <div className="text-blue-300 font-semibold flex items-center gap-1">
              <span>🎯</span>
              <span>Trade del queue · provenance lock</span>
            </div>
            <div className="text-muted-foreground grid grid-cols-2 gap-x-3 gap-y-0.5">
              <span>Regime preview:</span><span className="font-mono text-foreground">{prefill?.regime_at_entry ?? '—'}</span>
              <span>System score:</span><span className="font-mono text-foreground">{prefill?.system_score_at_entry != null ? prefill.system_score_at_entry.toFixed(2) : '—'}</span>
              <span>Group strength:</span><span className="font-mono text-foreground">{prefill?.group_strength_at_entry ?? '—'}</span>
              <span>Leader health:</span><span className="font-mono text-foreground">{prefill?.leader_health_at_entry != null ? prefill.leader_health_at_entry.toFixed(3) : '—'}</span>
            </div>
            <div className="text-muted-foreground/70 text-[10px] mt-1">
              Snapshots reales se toman al confirmar — no en este click. Editá qty y eventualmente entry/stop.
            </div>
          </div>
        )}
        <div className="grid grid-cols-2 gap-3">
          <Field label="Symbol" required>
            <input className={`${inputCls} ${hasPrefill ? 'opacity-60 cursor-not-allowed' : ''}`} value={symbol} onChange={e => setSymbol(e.target.value.toUpperCase())} required autoFocus={!hasPrefill} readOnly={hasPrefill} />
          </Field>
          <Field label="Fecha entry" required>
            <input type="date" className={inputCls} value={entryDate} onChange={e => setEntryDate(e.target.value)} required />
          </Field>
          <Field label="Entry price" required>
            <input type="number" step="0.01" className={inputCls} value={entryPrice} onChange={e => setEntryPrice(e.target.value)} required autoFocus={hasPrefill} />
          </Field>
          <Field label="Qty" required>
            <input type="number" step="any" className={inputCls} value={qty} onChange={e => setQty(e.target.value)} required />
          </Field>
          <Field label="Stop price">
            <input type="number" step="0.01" className={inputCls} value={stopPrice} onChange={e => setStopPrice(e.target.value)} />
          </Field>
          <Field label="">
            <div className="text-[11px] text-muted-foreground space-y-0.5 pt-1">
              {costTotal != null && <div>Cost: <span className="text-foreground tabular-nums">${costTotal.toFixed(2)}</span></div>}
              {totalRisk != null && totalRisk > 0 && <div>Risk: <span className="text-red-400 tabular-nums">-${totalRisk.toFixed(2)}</span> ({riskPerShare && entryNum ? ((riskPerShare / entryNum) * 100).toFixed(2) : ''}%)</div>}
            </div>
          </Field>
          <Field label="Setup" required>
            <select className={`${inputCls} ${hasPrefill ? 'opacity-60 cursor-not-allowed' : ''}`} value={setup} onChange={e => setSetup(e.target.value)} disabled={hasPrefill}>
              {vocab.setup_options.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </Field>
          <Field label="Origen del trade" required>
            <select className={`${inputCls} ${hasPrefill ? 'opacity-60 cursor-not-allowed' : ''}`} value={entryReason} onChange={e => setEntryReason(e.target.value)} disabled={hasPrefill}>
              {vocab.entry_reason_options.map(r => <option key={r} value={r}>{r}</option>)}
            </select>
          </Field>
          <Field label="Planned risk $">
            <input type="number" step="0.01" className={inputCls} value={plannedRiskDollars} onChange={e => setPlannedRiskDollars(e.target.value)} placeholder="ej: 10" />
          </Field>
          <Field label="Account balance $">
            <input type="number" step="0.01" className={inputCls} value={accountBalance} onChange={e => setAccountBalance(e.target.value)} placeholder="prefilled del último trade" />
          </Field>
          <div className="col-span-2 text-[11px] text-muted-foreground bg-muted/20 rounded px-3 py-2 flex items-center">
            <RiskPercentBadge riskDollars={effectiveRisk} balance={balanceNum > 0 ? balanceNum : null} />
            {effectiveRisk != null && plannedRiskNum > 0 && (
              <span className="ml-auto text-[10px] text-muted-foreground">explícito · ${effectiveRisk.toFixed(2)}</span>
            )}
            {effectiveRisk != null && !(plannedRiskNum > 0) && (
              <span className="ml-auto text-[10px] text-muted-foreground">inferido de stop · ${effectiveRisk.toFixed(2)}</span>
            )}
          </div>
        </div>
        {err && <p className="text-xs text-red-400">{err}</p>}
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" onClick={onClose} className="text-xs px-3 py-1.5 rounded border border-border text-muted-foreground hover:bg-muted/30">Cancelar</button>
          <button type="submit" disabled={saving} className="text-xs px-3 py-1.5 rounded bg-blue-500/20 border border-blue-500/40 text-blue-300 hover:bg-blue-500/30 disabled:opacity-50">
            {saving ? 'Guardando…' : 'Crear posición'}
          </button>
        </div>
      </form>
    </ModalShell>
  )
}

export function CloseTradeModal({
  trade, defaultCommission, onClose, onSaved,
}: {
  trade: Trade
  defaultCommission: number
  onClose: () => void
  onSaved: () => void
}) {
  const [exitDate, setExitDate] = useState(today())
  const [exitPrice, setExitPrice] = useState('')
  const [qty, setQty] = useState(String(trade.qty))
  const [exitReason, setExitReason] = useState('')
  const [errorNote, setErrorNote] = useState('')
  const [postVenta, setPostVenta] = useState('')
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const exitNum = parseFloat(exitPrice)
  const qtyNum = parseFloat(qty)
  const qtyValid = qtyNum > 0 && qtyNum <= trade.qty + 1e-9
  const isPartial = qtyValid && qtyNum < trade.qty - 1e-9
  const remaining = qtyValid ? trade.qty - qtyNum : 0
  const previewPnl = exitNum && qtyValid ? (exitNum - trade.entry_price) * qtyNum - 2 * defaultCommission : null
  const previewR = exitNum && trade.stop_price && trade.entry_price > trade.stop_price
    ? (exitNum - trade.entry_price) / (trade.entry_price - trade.stop_price)
    : null

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true); setErr(null)
    try {
      const body: any = {
        exit_date: exitDate, exit_price: exitNum,
        error_note: errorNote || null, post_venta: postVenta || null,
      }
      // Only send qty if it's a partial close — full close just omits the field
      if (isPartial) body.qty = qtyNum
      // exit_reason: empty string = auto-infer (backend assigns partial_take on partial, keeps current on full)
      if (exitReason) body.exit_reason = exitReason
      const res = await fetch(`${API_URL}/api/v1/journal/trades/${trade.id}/close`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      })
      if (!res.ok) {
        const d = await res.json().catch(() => ({}))
        throw new Error(d.detail || `HTTP ${res.status}`)
      }
      onSaved(); onClose()
    } catch (e: any) {
      setErr(e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <ModalShell title={`Cerrar ${trade.symbol} (entry ${trade.entry_date} @ $${trade.entry_price.toFixed(2)})`} onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Fecha exit" required>
            <input type="date" className={inputCls} value={exitDate} onChange={e => setExitDate(e.target.value)} required />
          </Field>
          <Field label="Exit price" required>
            <input type="number" step="0.01" className={inputCls} value={exitPrice} onChange={e => setExitPrice(e.target.value)} required autoFocus />
          </Field>
          <Field label={`Qty a cerrar (de ${trade.qty})`} required>
            <div className="flex items-center gap-2">
              <input type="number" step="any" min="0" max={trade.qty} className={inputCls} value={qty} onChange={e => setQty(e.target.value)} required />
              <button type="button" onClick={() => setQty(String(trade.qty))} className="text-[10px] px-2 py-1 rounded border border-border text-muted-foreground hover:bg-muted/30">Total</button>
              <button type="button" onClick={() => setQty(String(trade.qty / 2))} className="text-[10px] px-2 py-1 rounded border border-border text-muted-foreground hover:bg-muted/30">½</button>
            </div>
          </Field>
          <Field label="">
            <div className="text-[11px] text-muted-foreground pt-1">
              {isPartial ? <span className="text-blue-300">Parcial · queda {remaining} abierto</span> : qtyValid ? <span>Cierre total</span> : <span className="text-red-400">qty inválida</span>}
            </div>
          </Field>
          <div className="col-span-2 text-[11px] text-muted-foreground bg-muted/20 rounded px-3 py-2 space-y-0.5">
            {previewPnl != null && (
              <div>P&L: <span className={`tabular-nums ${previewPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {previewPnl >= 0 ? '+' : ''}${previewPnl.toFixed(2)}
              </span></div>
            )}
            {previewR != null && (
              <div>R: <span className={`tabular-nums ${previewR >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {previewR >= 0 ? '+' : ''}{previewR.toFixed(2)}
              </span></div>
            )}
            {trade.stop_price == null && <div className="text-amber-400">⚠ Sin stop cargado — no se podrá calcular R</div>}
          </div>
          <Field label="Motivo de salida">
            <select className={inputCls} value={exitReason} onChange={e => setExitReason(e.target.value)}>
              <option value="">{isPartial ? '(auto · partial_take)' : '(auto · unknown)'}</option>
              {/* Show all enum options regardless of partial/full so operator can override */}
              <option value="stop_hit">stop_hit</option>
              <option value="target">target</option>
              <option value="trail">trail</option>
              <option value="thesis_broken">thesis_broken</option>
              <option value="discretionary">discretionary</option>
              <option value="partial_take">partial_take</option>
              <option value="unknown">unknown</option>
            </select>
          </Field>
          <Field label="Razón / Nota">
            <input className={inputCls} value={errorNote} onChange={e => setErrorNote(e.target.value)} placeholder="Stop, target, parcial, trail, tesis rota…" />
          </Field>
          <Field label="Post venta">
            <input className={inputCls} value={postVenta} onChange={e => setPostVenta(e.target.value)} placeholder="Qué pasó después" />
          </Field>
        </div>
        {err && <p className="text-xs text-red-400">{err}</p>}
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" onClick={onClose} className="text-xs px-3 py-1.5 rounded border border-border text-muted-foreground hover:bg-muted/30">Cancelar</button>
          <button type="submit" disabled={saving || !qtyValid} className="text-xs px-3 py-1.5 rounded bg-red-500/20 border border-red-500/40 text-red-300 hover:bg-red-500/30 disabled:opacity-50">
            {saving ? 'Guardando…' : isPartial ? `Cerrar ${qtyNum} (parcial)` : 'Cerrar posición'}
          </button>
        </div>
      </form>
    </ModalShell>
  )
}

export function EditTradeModal({
  trade, vocab, onClose, onSaved,
}: {
  trade: Trade
  vocab: Vocab
  onClose: () => void
  onSaved: () => void
}) {
  const [symbol, setSymbol] = useState(trade.symbol)
  const [setup, setSetup] = useState(trade.setup)
  const [context, setContext] = useState(trade.context)
  const [entryDate, setEntryDate] = useState(trade.entry_date ?? '')
  const [entryPrice, setEntryPrice] = useState(String(trade.entry_price))
  const [qty, setQty] = useState(String(trade.qty))
  const [stopPrice, setStopPrice] = useState(trade.stop_price != null ? String(trade.stop_price) : '')
  const [exitDate, setExitDate] = useState(trade.exit_date ?? '')
  const [exitPrice, setExitPrice] = useState(trade.exit_price != null ? String(trade.exit_price) : '')
  const [errorNote, setErrorNote] = useState(trade.error_note ?? '')
  const [postVenta, setPostVenta] = useState(trade.post_venta ?? '')
  const [fromQueue, setFromQueue] = useState<string>(
    trade.from_queue == null ? '' : (trade.from_queue ? 'true' : 'false')
  )
  const [entryReason, setEntryReason] = useState(trade.entry_reason || 'other')
  const [exitReason, setExitReason] = useState(trade.exit_reason || 'unknown')
  const [plannedRiskDollars, setPlannedRiskDollars] = useState(trade.planned_risk_dollars != null ? String(trade.planned_risk_dollars) : '')
  const [accountBalance, setAccountBalance] = useState(trade.account_balance_at_entry != null ? String(trade.account_balance_at_entry) : loadAccountBalance())
  const [stopEvents, setStopEvents] = useState<StopEvent[]>([])
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetch(`${API_URL}/api/v1/journal/trades/${trade.id}/stop-history`)
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(d => { if (!cancelled) setStopEvents(d.events || []) })
      .catch(e => console.warn('stop-history fetch failed', e))
    return () => { cancelled = true }
  }, [trade.id])

  const editPlannedRiskNum = parseFloat(plannedRiskDollars)
  const editBalanceNum = parseFloat(accountBalance)
  const editStopNum = parseFloat(stopPrice)
  const editEntryNum = parseFloat(entryPrice)
  const editQtyNum = parseFloat(qty)
  const editInferredRisk = editStopNum > 0 && editEntryNum > 0 && editQtyNum > 0 && editEntryNum > editStopNum
    ? (editEntryNum - editStopNum) * editQtyNum
    : null
  const editEffectiveRisk = editPlannedRiskNum > 0 ? editPlannedRiskNum : editInferredRisk

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true); setErr(null)
    try {
      const body: any = {
        symbol, setup, context,
        entry_date: entryDate || null,
        entry_price: parseFloat(entryPrice),
        qty: parseFloat(qty),
        stop_price: stopPrice ? parseFloat(stopPrice) : null,
        exit_date: exitDate || null,
        exit_price: exitPrice ? parseFloat(exitPrice) : null,
        error_note: errorNote || null,
        post_venta: postVenta || null,
        from_queue: fromQueue === '' ? null : fromQueue === 'true',
        entry_reason: entryReason,
        exit_reason: exitReason,
        planned_risk_dollars: editPlannedRiskNum > 0 ? editPlannedRiskNum : null,
        account_balance_at_entry: editBalanceNum > 0 ? editBalanceNum : null,
      }
      if (editBalanceNum > 0) saveAccountBalance(accountBalance)
      const res = await fetch(`${API_URL}/api/v1/journal/trades/${trade.id}`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      })
      if (!res.ok) {
        const d = await res.json().catch(() => ({}))
        throw new Error(d.detail || `HTTP ${res.status}`)
      }
      onSaved(); onClose()
    } catch (e: any) {
      setErr(e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <ModalShell title={`Editar trade #${trade.id} — ${trade.symbol}`} onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Symbol"><input className={inputCls} value={symbol} onChange={e => setSymbol(e.target.value.toUpperCase())} /></Field>
          <Field label="Setup">
            <select className={inputCls} value={setup} onChange={e => setSetup(e.target.value)}>
              {vocab.setup_options.map(s => <option key={s} value={s}>{s}</option>)}
              {!vocab.setup_options.includes(setup) && <option value={setup}>{setup}</option>}
            </select>
          </Field>
          <Field label="Contexto">
            <select className={inputCls} value={context} onChange={e => setContext(e.target.value)}>
              {vocab.context_options.map(c => <option key={c} value={c}>{c}</option>)}
              {!vocab.context_options.includes(context) && <option value={context}>{context}</option>}
            </select>
          </Field>
          <Field label="Fecha entry"><input type="date" className={inputCls} value={entryDate} onChange={e => setEntryDate(e.target.value)} /></Field>
          <Field label="Entry price"><input type="number" step="0.01" className={inputCls} value={entryPrice} onChange={e => setEntryPrice(e.target.value)} /></Field>
          <Field label="Qty"><input type="number" step="any" className={inputCls} value={qty} onChange={e => setQty(e.target.value)} /></Field>
          <Field label="Stop price"><input type="number" step="0.01" className={inputCls} value={stopPrice} onChange={e => setStopPrice(e.target.value)} /></Field>
          <Field label="Fecha exit"><input type="date" className={inputCls} value={exitDate} onChange={e => setExitDate(e.target.value)} /></Field>
          <Field label="Exit price"><input type="number" step="0.01" className={inputCls} value={exitPrice} onChange={e => setExitPrice(e.target.value)} /></Field>
          <Field label="Origen del trade">
            <select className={inputCls} value={entryReason} onChange={e => setEntryReason(e.target.value)}>
              {vocab.entry_reason_options.map(r => <option key={r} value={r}>{r}</option>)}
              {!vocab.entry_reason_options.includes(entryReason) && <option value={entryReason}>{entryReason}</option>}
            </select>
          </Field>
          <Field label="Motivo de salida">
            <select className={inputCls} value={exitReason} onChange={e => setExitReason(e.target.value)}>
              {vocab.exit_reason_options.map(r => <option key={r} value={r}>{r}</option>)}
              {!vocab.exit_reason_options.includes(exitReason) && <option value={exitReason}>{exitReason}</option>}
            </select>
          </Field>
          <Field label="From queue">
            <select className={inputCls} value={fromQueue} onChange={e => setFromQueue(e.target.value)}>
              <option value="">— sin marcar —</option>
              <option value="true">true (del queue)</option>
              <option value="false">false (off-system)</option>
            </select>
          </Field>
          <Field label="Planned risk $">
            <input type="number" step="0.01" className={inputCls} value={plannedRiskDollars} onChange={e => setPlannedRiskDollars(e.target.value)} />
          </Field>
          <Field label="Account balance $">
            <input type="number" step="0.01" className={inputCls} value={accountBalance} onChange={e => setAccountBalance(e.target.value)} />
          </Field>
          <div className="col-span-2 text-[11px] text-muted-foreground bg-muted/20 rounded px-3 py-1.5">
            <RiskPercentBadge riskDollars={editEffectiveRisk} balance={editBalanceNum > 0 ? editBalanceNum : null} />
          </div>
          <div className="col-span-2 mt-2 border border-border/60 rounded p-3 bg-muted/10">
            <div className="text-[10px] uppercase tracking-widest text-muted-foreground mb-2">Snapshots del sistema al entry (read-only)</div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[11px]">
              <div className="text-muted-foreground">Regime</div>
              <div className="font-mono text-foreground text-right">{trade.regime_at_entry ?? <span className="text-muted-foreground/50 italic">—</span>}</div>
              <div className="text-muted-foreground">System score</div>
              <div className="font-mono text-foreground text-right tabular-nums">{trade.system_score_at_entry != null ? trade.system_score_at_entry.toFixed(2) : <span className="text-muted-foreground/50 italic">—</span>}</div>
              <div className="text-muted-foreground">Group strength</div>
              <div className="font-mono text-foreground text-right">{trade.group_strength_at_entry ?? <span className="text-muted-foreground/50 italic">—</span>}</div>
              <div className="text-muted-foreground">Leader health</div>
              <div className="font-mono text-foreground text-right tabular-nums">{trade.leader_health_at_entry != null ? trade.leader_health_at_entry.toFixed(3) : <span className="text-muted-foreground/50 italic">—</span>}</div>
              <div className="text-muted-foreground">Initial stop</div>
              <div className="font-mono text-foreground text-right tabular-nums">{trade.initial_stop_price != null ? `$${trade.initial_stop_price.toFixed(2)}` : <span className="text-muted-foreground/50 italic">—</span>}</div>
            </div>
          </div>
          <div className="col-span-2 border border-border/60 rounded p-3 bg-muted/10">
            <div className="text-[10px] uppercase tracking-widest text-muted-foreground mb-2">Historial de stop</div>
            {stopEvents.length === 0 ? (
              <div className="text-[11px] text-muted-foreground/60 italic">sin cambios registrados</div>
            ) : (
              <table className="w-full text-[11px]">
                <thead>
                  <tr className="text-left text-[10px] uppercase tracking-widest text-muted-foreground/70">
                    <th className="pb-1 font-medium">Cuándo</th>
                    <th className="pb-1 font-medium">Tipo</th>
                    <th className="pb-1 font-medium text-right">Old → New</th>
                  </tr>
                </thead>
                <tbody>
                  {stopEvents.map(e => (
                    <tr key={e.id} className="border-t border-border/40">
                      <td className="py-1 font-mono text-muted-foreground">{e.occurred_at ? e.occurred_at.slice(0, 16).replace('T', ' ') : '—'}</td>
                      <td className="py-1 font-mono"><StopEventBadge kind={e.kind} /></td>
                      <td className="py-1 font-mono text-right tabular-nums">
                        {e.old_stop_price != null ? `$${e.old_stop_price.toFixed(2)}` : '—'} → {e.new_stop_price != null ? `$${e.new_stop_price.toFixed(2)}` : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <Field label="Nota"><input className={inputCls} value={errorNote} onChange={e => setErrorNote(e.target.value)} /></Field>
          <Field label="Post venta"><input className={inputCls} value={postVenta} onChange={e => setPostVenta(e.target.value)} /></Field>
        </div>
        {err && <p className="text-xs text-red-400">{err}</p>}
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" onClick={onClose} className="text-xs px-3 py-1.5 rounded border border-border text-muted-foreground hover:bg-muted/30">Cancelar</button>
          <button type="submit" disabled={saving} className="text-xs px-3 py-1.5 rounded bg-blue-500/20 border border-blue-500/40 text-blue-300 hover:bg-blue-500/30 disabled:opacity-50">
            {saving ? 'Guardando…' : 'Guardar'}
          </button>
        </div>
      </form>
    </ModalShell>
  )
}

function ModalShell({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div className="bg-card border border-border rounded-lg max-w-xl w-full p-5 max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-foreground">{title}</h2>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground"><X className="w-4 h-4" /></button>
        </div>
        {children}
      </div>
    </div>
  )
}

function Field({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <div>
      {label && <label className={labelCls}>{label}{required && <span className="text-red-400 ml-0.5">*</span>}</label>}
      <div className={label ? 'mt-1' : ''}>{children}</div>
    </div>
  )
}
