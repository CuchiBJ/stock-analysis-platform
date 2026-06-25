'use client'

import { useEffect, useState, useCallback } from 'react'
import { TrendingUp, TrendingDown, RotateCw } from 'lucide-react'
import { useWebSocket } from '@/hooks/useWebSocket'
import { API_URL } from '@/lib/utils'
import type { SectorRotation, SectorRotationEntry, SectorRotationGroup } from '@/types/sector'
import SectorConstituentsDrawer from '@/components/dashboard/SectorConstituentsDrawer'

function rankDeltaLabel(d: number): string {
  if (d > 0) return `subió ${d} puesto${d === 1 ? '' : 's'}`
  if (d < 0) return `bajó ${Math.abs(d)} puesto${d === -1 ? '' : 's'}`
  return 'sin cambio de ranking'
}

export default function SectorRotationCallout() {
  const [rot, setRot] = useState<SectorRotation | null>(null)
  const [error, setError] = useState(false)
  const [selectedGroup, setSelectedGroup] = useState<string | null>(null)

  const { data: metricsEvent } = useWebSocket<{ event: string }>({ channel: 'metrics' })

  const fetchRotation = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/v1/sectors/rotation`)
      if (!res.ok) throw new Error('failed')
      setRot(await res.json())
      setError(false)
    } catch {
      setError(true)
    }
  }, [])

  useEffect(() => {
    fetchRotation()
    const id = setInterval(fetchRotation, 60000)
    return () => clearInterval(id)
  }, [fetchRotation])

  useEffect(() => {
    if (metricsEvent?.event === 'updated') fetchRotation()
  }, [metricsEvent, fetchRotation])

  if (error || !rot) return null

  const hasRotation = rot.rotating_in.length > 0 || rot.rotating_out.length > 0

  // Fallback: sin rotación marcada → mostramos los líderes actuales por ranking.
  const leaders = rot.groups.slice(0, 3)

  const Chip = ({ e, dir }: { e: SectorRotationEntry; dir: 'in' | 'out' }) => (
    <button
      onClick={() => setSelectedGroup(e.name)}
      className={`inline-flex items-center gap-0.5 hover:underline ${dir === 'in' ? 'text-green-400' : 'text-red-400'}`}
      title={`${e.name} — ${rankDeltaLabel(e.rank_delta)} (RS Δ${e.rs_delta >= 0 ? '+' : ''}${e.rs_delta}) · ahora #${e.rank_now} · clic para ver acciones`}
    >
      {e.name}
      {dir === 'in' ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
    </button>
  )

  return (
   <>
    <div className="px-4 py-2 rounded-lg border border-border/50 bg-[hsl(var(--block-sector))] flex items-center gap-x-4 gap-y-1 flex-wrap text-xs">
      <span className="inline-flex items-center gap-1.5 text-muted-foreground uppercase tracking-wide shrink-0">
        <RotateCw className="w-3.5 h-3.5" />
        Rotación
      </span>

      {hasRotation ? (
        <>
          {rot.rotating_in.length > 0 && (
            <span className="inline-flex items-center gap-1.5 flex-wrap">
              <span className="text-white/40">Rotando hacia:</span>
              {rot.rotating_in.map((e, i) => (
                <span key={e.name} className="inline-flex items-center">
                  <Chip e={e} dir="in" />
                  {i < rot.rotating_in.length - 1 && <span className="text-white/20 mx-1">·</span>}
                </span>
              ))}
            </span>
          )}
          {rot.rotating_out.length > 0 && (
            <span className="inline-flex items-center gap-1.5 flex-wrap">
              <span className="text-white/20">|</span>
              <span className="text-white/40">Saliendo:</span>
              {rot.rotating_out.map((e, i) => (
                <span key={e.name} className="inline-flex items-center">
                  <Chip e={e} dir="out" />
                  {i < rot.rotating_out.length - 1 && <span className="text-white/20 mx-1">·</span>}
                </span>
              ))}
            </span>
          )}
        </>
      ) : (
        <span className="inline-flex items-center gap-1.5 flex-wrap">
          <span className="text-white/40">Sin rotación marcada · líderes:</span>
          {leaders.map((g: SectorRotationGroup, i) => (
            <span key={g.name} className="inline-flex items-center">
              <button onClick={() => setSelectedGroup(g.name)} className="text-foreground/80 hover:underline">
                {g.name}
              </button>
              {i < leaders.length - 1 && <span className="text-white/20 mx-1">·</span>}
            </span>
          ))}
        </span>
      )}

      <span className="ml-auto text-[10px] text-white/30 shrink-0">
        vs {rot.lookback_sessions} ruedas
      </span>
    </div>

    <SectorConstituentsDrawer group={selectedGroup} onClose={() => setSelectedGroup(null)} />
   </>
  )
}
