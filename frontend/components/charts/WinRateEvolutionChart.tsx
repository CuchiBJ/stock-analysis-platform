'use client'

import { useLayoutEffect, useMemo, useRef, useState } from 'react'

export interface WinRatePoint {
  i: number
  decision_id: number
  entry_date: string | null
  outcome: 'win' | 'loss' | 'breakeven'
  cumulative_win_rate: number | null
  rolling_win_rate: number | null
  cumulative_wins: number
  cumulative_losses: number
}

// Palette validated (dataviz skill, light+dark) — CVD-safe pair, both series
// also carry a legend + direct end-labels so identity is never colour-alone.
const CUM_COLOR = '#3b82f6'   // cumulative win rate — the career trajectory
const ROLL_COLOR = '#d97706'  // rolling win rate — recent form

const PAD = { top: 16, right: 64, bottom: 26, left: 34 }
const HEIGHT = 240

function pctLabel(v: number | null): string {
  return v == null ? '—' : `${Math.round(v * 100)}%`
}

// Build an SVG path over points whose value may be null, breaking the line into
// segments across gaps (early break-even-only stretches leave rolling undefined).
function buildPath(
  pts: { x: number; v: number | null }[],
  yFor: (v: number) => number,
): string {
  let d = ''
  let pen = false
  for (const p of pts) {
    if (p.v == null) { pen = false; continue }
    const y = yFor(p.v)
    d += `${pen ? 'L' : 'M'}${p.x.toFixed(1)} ${y.toFixed(1)} `
    pen = true
  }
  return d.trim()
}

export default function WinRateEvolutionChart({
  data,
  rollingWindow,
}: {
  data: WinRatePoint[]
  rollingWindow: number
}) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(720)
  const [hover, setHover] = useState<number | null>(null)

  useLayoutEffect(() => {
    if (!wrapRef.current) return
    const el = wrapRef.current
    const ro = new ResizeObserver(() => setWidth(el.clientWidth))
    setWidth(el.clientWidth)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const geom = useMemo(() => {
    const n = data.length
    const innerW = Math.max(1, width - PAD.left - PAD.right)
    const innerH = HEIGHT - PAD.top - PAD.bottom
    // Single point degenerates to a centred dot; otherwise spread by index.
    const xFor = (idx: number) =>
      PAD.left + (n <= 1 ? innerW / 2 : (idx / (n - 1)) * innerW)
    const yFor = (v: number) => PAD.top + (1 - v) * innerH
    const cumPts = data.map((p, idx) => ({ x: xFor(idx), v: p.cumulative_win_rate }))
    const rollPts = data.map((p, idx) => ({ x: xFor(idx), v: p.rolling_win_rate }))
    return { n, innerW, innerH, xFor, yFor, cumPts, rollPts }
  }, [data, width])

  if (data.length === 0) {
    return (
      <div className="px-4 py-6 text-xs text-muted-foreground">
        Todavía no hay decisiones cerradas — cuando resuelvas trades aparecerá tu curva de win rate.
      </div>
    )
  }

  const { n, xFor, yFor, cumPts, rollPts } = geom
  const lastCum = data[n - 1].cumulative_win_rate
  const lastRoll = data[n - 1].rolling_win_rate

  // Keep the two end-labels from colliding when the lines finish close together.
  const cumLabelY = lastCum != null ? yFor(lastCum) : null
  const rollLabelY = lastRoll != null ? yFor(lastRoll) : null
  let cumLy = cumLabelY, rollLy = rollLabelY
  if (cumLy != null && rollLy != null && Math.abs(cumLy - rollLy) < 12) {
    if (cumLy <= rollLy) { cumLy -= 6; rollLy += 6 } else { cumLy += 6; rollLy -= 6 }
  }

  // Date ticks: first / middle / last decisions that have a date.
  const dateTickIdx = n <= 1 ? [0] : [0, Math.floor((n - 1) / 2), n - 1]

  const hp = hover != null ? data[hover] : null

  function onMove(e: React.MouseEvent<SVGRectElement>) {
    const rect = e.currentTarget.getBoundingClientRect()
    const x = e.clientX - rect.left
    if (n <= 1) { setHover(0); return }
    const frac = (x - PAD.left) / (width - PAD.left - PAD.right)
    const idx = Math.round(frac * (n - 1))
    setHover(Math.max(0, Math.min(n - 1, idx)))
  }

  return (
    <div ref={wrapRef} className="w-full select-none">
      {/* Legend — always present for ≥2 series */}
      <div className="flex items-center gap-4 px-1 pb-2 text-[10px] text-muted-foreground flex-wrap">
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block w-3 h-0.5 rounded" style={{ background: CUM_COLOR }} />
          Win rate acumulado
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block w-3 h-0.5 rounded" style={{ background: ROLL_COLOR }} />
          Forma reciente (últimas {rollingWindow})
        </span>
        <span className="text-muted-foreground/50">· win rate a nivel decisión · scratches (BE) excluidos del denominador</span>
      </div>

      <svg width={width} height={HEIGHT} className="overflow-visible">
        {/* Horizontal gridlines + y labels at 0/25/50/75/100% */}
        {[0, 0.25, 0.5, 0.75, 1].map(g => {
          const y = yFor(g)
          const mid = g === 0.5
          return (
            <g key={g}>
              <line
                x1={PAD.left} x2={width - PAD.right} y1={y} y2={y}
                className={mid ? 'text-muted-foreground/40' : 'text-border'}
                stroke="currentColor" strokeWidth={1}
                strokeDasharray={mid ? '4 3' : undefined}
              />
              <text
                x={PAD.left - 6} y={y + 3} textAnchor="end"
                className="fill-muted-foreground/70 text-[9px] tabular-nums"
              >
                {Math.round(g * 100)}
              </text>
            </g>
          )
        })}

        {/* X date ticks */}
        {dateTickIdx.map(idx => {
          const p = data[idx]
          if (!p?.entry_date) return null
          return (
            <text
              key={idx}
              x={xFor(idx)} y={HEIGHT - 8}
              textAnchor={idx === 0 ? 'start' : idx === n - 1 ? 'end' : 'middle'}
              className="fill-muted-foreground/60 text-[9px] tabular-nums"
            >
              {p.entry_date}
            </text>
          )
        })}

        {/* Series lines */}
        <path d={buildPath(cumPts, yFor)} fill="none" stroke={CUM_COLOR} strokeWidth={2}
          strokeLinejoin="round" strokeLinecap="round" />
        <path d={buildPath(rollPts, yFor)} fill="none" stroke={ROLL_COLOR} strokeWidth={2}
          strokeLinejoin="round" strokeLinecap="round" opacity={0.9} />

        {/* Single-point fallback dots so a lone decision is still visible */}
        {n === 1 && (
          <>
            {lastCum != null && <circle cx={xFor(0)} cy={yFor(lastCum)} r={4} fill={CUM_COLOR} />}
            {lastRoll != null && <circle cx={xFor(0)} cy={yFor(lastRoll)} r={4} fill={ROLL_COLOR} />}
          </>
        )}

        {/* Direct end-labels (secondary encoding beyond colour) */}
        {cumLy != null && (
          <text x={width - PAD.right + 6} y={cumLy + 3} className="text-[10px] font-semibold tabular-nums"
            fill={CUM_COLOR}>{pctLabel(lastCum)}</text>
        )}
        {rollLy != null && (
          <text x={width - PAD.right + 6} y={rollLy + 3} className="text-[10px] font-semibold tabular-nums"
            fill={ROLL_COLOR}>{pctLabel(lastRoll)}</text>
        )}

        {/* Hover crosshair + markers */}
        {hp && (
          <g>
            <line x1={xFor(hp.i - 1)} x2={xFor(hp.i - 1)} y1={PAD.top} y2={HEIGHT - PAD.bottom}
              className="text-muted-foreground/40" stroke="currentColor" strokeWidth={1} strokeDasharray="3 3" />
            {hp.cumulative_win_rate != null && (
              <circle cx={xFor(hp.i - 1)} cy={yFor(hp.cumulative_win_rate)} r={3.5}
                fill={CUM_COLOR} className="stroke-background" strokeWidth={1.5} />
            )}
            {hp.rolling_win_rate != null && (
              <circle cx={xFor(hp.i - 1)} cy={yFor(hp.rolling_win_rate)} r={3.5}
                fill={ROLL_COLOR} className="stroke-background" strokeWidth={1.5} />
            )}
          </g>
        )}

        {/* Interaction capture layer */}
        <rect
          x={PAD.left} y={PAD.top}
          width={Math.max(1, width - PAD.left - PAD.right)} height={HEIGHT - PAD.top - PAD.bottom}
          fill="transparent"
          onMouseMove={onMove}
          onMouseLeave={() => setHover(null)}
        />
      </svg>

      {/* Tooltip readout — below the plot, avoids clipping at the SVG edges */}
      <div className="px-1 pt-1 min-h-[2.25rem] text-[11px]">
        {hp ? (
          <div className="flex flex-wrap items-center gap-x-4 gap-y-0.5">
            <span className="text-muted-foreground">
              Decisión <span className="text-foreground tabular-nums">#{hp.i}</span>
              {hp.entry_date && <span className="text-muted-foreground/70"> · {hp.entry_date}</span>}
            </span>
            <span style={{ color: CUM_COLOR }} className="tabular-nums">
              Acumulado {pctLabel(hp.cumulative_win_rate)}
            </span>
            <span style={{ color: ROLL_COLOR }} className="tabular-nums">
              Reciente {pctLabel(hp.rolling_win_rate)}
            </span>
            <span className="text-muted-foreground/70 tabular-nums">
              {hp.cumulative_wins}W / {hp.cumulative_losses}L acum.
            </span>
            <span className={
              hp.outcome === 'win' ? 'text-green-400'
                : hp.outcome === 'loss' ? 'text-red-400' : 'text-muted-foreground'
            }>
              {hp.outcome === 'win' ? 'ganada' : hp.outcome === 'loss' ? 'perdida' : 'scratch'}
            </span>
          </div>
        ) : (
          <span className="text-muted-foreground/50">Pasá el cursor sobre la curva para ver cada decisión.</span>
        )}
      </div>
    </div>
  )
}
