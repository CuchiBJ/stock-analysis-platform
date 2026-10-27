import type { ReactNode } from 'react'
import { DamageStrip, healthStateColor, followThroughColor, densityLevelColor, type MarketContextData } from '@/components/dashboard/MarketContextBar'
import PostureExplanation from './PostureExplanation'
import { breadthStatus, changeText, numberText, percentText } from '@/lib/market-context'
import { marketContextLabel, type MarketContextLabelFamily } from '@/lib/market-context-labels'

const summaryStyle = 'cursor-pointer py-3 text-sm text-muted-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-400'
function Row({ label, children }: { label: string; children: ReactNode }) {
  return <div className="flex flex-wrap justify-between gap-3 border-b border-border py-3 text-sm"><span className="text-muted-foreground">{label}</span><span className="font-mono tabular-nums">{children}</span></div>
}
function Descriptor({ value, family }: { value: string; family: MarketContextLabelFamily }) {
  const color = ['COLLAPSING', 'EXHAUSTED'].includes(value) ? 'text-red-400' : ['NARROWING', 'THINNING'].includes(value) ? 'text-amber-400' : ['EXPANDING', 'HEALTHY'].includes(value) ? 'text-green-400' : 'text-muted-foreground'
  return <span className={color} title={`Código original: ${value}`}>{marketContextLabel(family, value)}</span>
}
function Audit({ value }: { value: unknown }) {
  return <pre className="max-h-96 overflow-auto rounded border border-border bg-card p-3 text-xs leading-relaxed text-muted-foreground">{JSON.stringify(value, null, 2)}</pre>
}

export default function ContextEvidence({ context: ctx, section }: { context: MarketContextData; section: 'posture' | 'participation' | 'comparisons' | 'quality' | 'additional' }) {
  const p = ctx.participation
  const l = ctx.leadership
  const h = ctx.health
  const f = ctx.follow_through
  if (section === 'posture') return <PostureExplanation context={ctx} />
  if (section === 'participation') return <><div className="flex flex-wrap justify-between gap-2"><h3 className="text-lg font-medium">Participación del mercado</h3><p className="text-sm"><Descriptor value={p.descriptor} family="participation" /> <span className="font-mono">{changeText(p.delta_5d, ' pp')} / 5 ruedas</span></p></div><Row label="Universo sobre EMA21">{percentText(p.metrics.breadth_above_ema21)}</Row><Row label="Momentum 5 ruedas">{changeText(p.metrics.breadth_momentum_5d * 100, ' pp')}</Row></>
  if (section === 'comparisons') {
    const comparisons = p.breadth_comparisons
    return comparisons ? <div>{([
      ['up_from_open_vs_down', 'Suben desde la apertura vs bajan'],
      ['up_4pct_vs_down_4pct', 'Suben ≥4% vs bajan ≥4%'],
    ] as const).map(([key, label]) => { const measure = comparisons[key]; return <div key={key}><Row label={label}>{measure.eligible_symbols > 0 ? `${measure.up_count} / ${measure.down_count}` : 'Sin datos'} <span className="text-xs text-muted-foreground">· {breadthStatus(measure)}</span></Row><p className="mt-1 text-xs text-muted-foreground">{comparisons.date} · {measure.eligible_symbols} elegibles · {measure.excluded_symbols} excluidas</p></div> })}</div> : <p className="text-sm text-muted-foreground">Comparaciones desde apertura y ±4% no disponibles.</p>
  }
  if (section === 'quality') return <section><h3 className="text-lg font-medium">Calidad y continuidad</h3>
    <Row label="Liderazgo"><Descriptor value={l.descriptor} family="leadership" /> · {l.metrics.leader_count} líderes</Row>
    <p className="mt-2 text-xs text-muted-foreground">Cambio 5 ruedas: {changeText(l.delta_5d)} · Densidad {percentText(l.metrics.leader_density)} · <span className={densityLevelColor(l.metrics.leader_density_level)} title={`Código original: ${l.metrics.leader_density_level}`}>{marketContextLabel('density', l.metrics.leader_density_level)}</span></p>
    <details><summary className={summaryStyle}>Detalle de liderazgo</summary><Row label="Densidad Δ5 ruedas">{changeText(l.metrics.leader_density_delta_5d)}</Row><Row label="Densidad Δ20 ruedas">{changeText(l.metrics.leader_density_delta_20d)}</Row><Row label="Percentil de densidad">{percentText(l.metrics.leader_density_percentile)} · {l.metrics.leader_density_sample_size} ruedas</Row><Row label="Calidad media de pullback">{numberText(l.metrics.leader_pullback_quality_avg, 1)}</Row><Row label="Líderes climácticos">{l.metrics.leader_climactic_count}</Row></details>
    <Row label="Memoria de deterioro"><span className={healthStateColor(h?.state ?? 'UNKNOWN')} title={`Código original: ${h?.state ?? 'UNKNOWN'}`}>{marketContextLabel('health', h?.state)}</span></Row>
    {h && <><p className="my-2 text-xs text-muted-foreground">{h.window_days} ruedas · {h.episodes} episodios · {h.damaged_days} días dañados · Reparación {h.repair_clean_days ?? h.repair_streak}/{h.repair_window_days ?? 7} limpias</p><details><summary className={summaryStyle}>Detalle de recuperación</summary><div className="max-w-full overflow-x-auto"><DamageStrip series={h.series} cellWidth={16} height={14} /></div><p className="mt-2 text-xs text-muted-foreground">Ámbar: pullback leve · Rojo: daño severo · Gris: sin daño clasificado</p><Row label="Confirmación acelerada">{h.exceptional_recovery_session ? 'Excepcional · ' : ''}{h.recovery_confirmation_streak ?? 0}/{h.recovery_confirmation_required_days ?? 3} ruedas</Row><Row label="Reparación requerida">{h.repair_required_clean_days ?? 5} limpias en {h.repair_window_days ?? 7} ruedas</Row><Row label="Daño severo reciente">{h.recent_severe_days ?? 0}/{h.severe_lookback_days ?? 3} ruedas</Row><Row label="Racha limpia">{h.repair_streak} ruedas</Row><Row label="Ruedas desde el último daño">{h.days_since_last_damage ?? 'Sin datos'}</Row><details><summary className={summaryStyle}>Historial por sesión</summary><Audit value={h.series} /></details></details></>}
    <Row label="Continuidad"><span className={followThroughColor(f?.descriptor ?? 'UNKNOWN')} title={`Código original: ${f?.descriptor ?? 'UNKNOWN'}`}>{marketContextLabel('continuity', f?.descriptor)}</span>{f && <> · {percentText(f.delivery_rate)} <span className="text-xs text-muted-foreground">vs base {percentText(f.baseline_rate)}</span></>}</Row>
    {f && <><p className="mt-2 text-xs text-muted-foreground">Continuidad de señales recientes · Ventana {f.window_days} ruedas · {f.signals} señales</p><details><summary className={summaryStyle}>Detalle de señales</summary><Row label="Resueltas / pendientes">{f.resolved} / {f.pending}</Row><Row label="Pagaron / fallaron / neutras">{f.success} / {f.failure} / {f.neutral}</Row><Row label="Frescas: en curso / fallando / sin definición">{f.provisional_on_track} / {f.provisional_failing} / {f.provisional_unclear}</Row><Row label="Delivery vs base histórica">{changeText(f.delta_pp, ' pp')}</Row><Row label="Muestra de referencia">{f.baseline_n}</Row><Row label="Base de evaluación">{f.basis}</Row>{Object.entries(f.per_family).map(([family, evidence]) => <Row key={family} label={family}>{evidence.signals} señales · {evidence.resolved} resueltas · {evidence.success} pagaron · {percentText(evidence.delivery)}</Row>)}</details></>}
    <details><summary className={summaryStyle}>Códigos originales de estados</summary><p className="text-xs text-muted-foreground">Participación: {p.descriptor} · liderazgo: {l.descriptor} · densidad: {l.metrics.leader_density_level} · salud: {h?.state ?? 'UNKNOWN'} · continuidad: {f?.descriptor ?? 'UNKNOWN'}</p></details>
  </section>
  return <details className="border-t border-border"><summary className={summaryStyle}>Métricas adicionales y metodología</summary>
    <Row label="Universo sobre EMA50 / EMA200">{percentText(p.metrics.breadth_above_ema50)} / {percentText(p.metrics.breadth_above_ema200)}</Row>
    <Row label="Momentum 20 ruedas">{changeText(p.metrics.breadth_momentum_20d * 100, ' pp')}</Row>
    <Row label="Ratio proximidad / distancia a máximos">{numberText(p.metrics.highs_lows_ratio)}</Row>
    <Row label="Cerca de máximos / lejos de máximos">{p.metrics.near_highs_count} / {p.metrics.near_lows_count}</Row>
    <Row label="Persistencia de participación">{numberText(p.metrics.participation_persistence, 4)}</Row>
    <Row label="Muestra de cambios de participación (20 ruedas)">{p.delta_sample_size_20d}</Row>
    <Row label="Cambio bruto de líderes 5 / 20 ruedas">{l.metrics.leader_count_delta_5d} / {l.metrics.leader_count_delta_20d}</Row>
    <Row label="Compresión semanal media">{numberText(l.metrics.leader_tightness_avg, 3)}</Row>
    <Row label="Contracción media de volumen">{numberText(l.metrics.leader_vol_contraction_avg, 3)}</Row>
    <Row label="Persistencia RS 10 ruedas">{percentText(l.metrics.leader_rs_persistence_10d)}</Row>
    <Row label="Extensión >3 ATR">{l.metrics.leader_extension_count}</Row>
    <Row label="Rotación de liderazgo 5 ruedas">{l.metrics.leadership_turnover_5d}</Row>
    <div className="mt-4 space-y-2 text-xs leading-relaxed text-muted-foreground"><p>Máximos y mínimos nuevos: el máximo intradiario supera el máximo de la sesión anterior del calendario SPY, o el mínimo intradiario cae por debajo del mínimo de esa sesión. Empates no generan eventos. La proporción es positivos ÷ eventos positivos y negativos.</p><p>Desde apertura compara el cierre con la apertura de la sesión. ±4% compara el cierre con el de la rueda previa del calendario SPY. Cada comparación informa su propia cobertura.</p><p>El ratio de proximidad compara acciones cerca de máximos con las alejadas; no cuenta nuevos extremos. Sectores y nombres corresponden a la metadata actual. Los precios OHLC almacenados conservan sus limitaciones ante acciones corporativas.</p><p>SPY y QQQ muestran precios e indicadores fechados. Su referencia de máximo de 52 semanas usa cierres e incluye empates, a diferencia de los nuevos extremos intradiarios. VIX muestra la cotización demorada de Cboe con su hora de observación cuando está disponible para la sesión. El cierre diario se conserva como respaldo y para las comparaciones entre sesiones.</p></div>
    <details><summary className={summaryStyle}>Historial de participación y liderazgo</summary><Audit value={{ participation: p.history ?? [], leadership: l.history ?? [] }} /></details>
  </details>
}
