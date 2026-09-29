'use client'

import Link from 'next/link'
import { useCallback, useEffect, useState } from 'react'

import LoadingSkeleton from '@/components/base/LoadingSkeleton'
import { FormationCard, type FormationEnvelope } from '@/components/dashboard/SetupsForming'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { useWebSocket } from '@/hooks/useWebSocket'
import { apiFetch } from '@/lib/api-client'

export default function SetupsFormingPage() {
  const [data, setData] = useState<FormationEnvelope | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { data: metricsEvent } = useWebSocket<{ event: string }>({ channel: 'metrics' })

  const load = useCallback(async () => {
    try {
      setError(null)
      const response = await apiFetch('/api/v1/transitions/forming/all')
      if (!response.ok) throw new Error(response.status === 401 ? 'La sesión expiró.' : 'No se pudo cargar la lista completa de setups en formación.')
      setData(await response.json() as FormationEnvelope)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudo cargar la lista completa de setups en formación.')
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
    <DashboardLayout>
      <div className="mx-auto max-w-7xl">
        <header className="mb-6 border-b border-white/10 pb-4">
          <Link href="/dashboard#setups" className="text-xs text-cyan-300 hover:text-cyan-200">
            ← Volver al dashboard
          </Link>
          <div className="mt-3 flex items-end justify-between gap-4">
            <div>
              <h1 className="text-2xl font-semibold text-white">Setups Forming</h1>
              <p className="mt-1 max-w-3xl text-sm text-white/45">
                Lista completa de estructuras sanas que se preparan para una transición, pero todavía no activaron el Setup Feed.
              </p>
            </div>
            {data && <span className="shrink-0 text-xs text-white/35">{data.total_eligible} candidatos</span>}
          </div>
        </header>

        {loading ? (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {Array.from({ length: 8 }, (_, index) => <LoadingSkeleton key={index} variant="card" />)}
          </div>
        ) : error ? (
          <div className="flex items-center justify-between gap-3 border border-red-500/20 bg-red-500/5 p-4 text-sm text-red-400">
            <span>{error}</span>
            <button className="rounded border border-white/15 px-3 py-1 text-xs text-white/70" onClick={() => void load()}>Reintentar</button>
          </div>
        ) : !data?.setups.length ? (
          <p className="border border-white/10 bg-white/5 p-4 text-sm text-white/45">
            No hay estructuras suficientemente preparadas en este snapshot. Los umbrales no se relajaron para llenar la lista.
          </p>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {data.setups.map((setup) => <FormationCard key={setup.symbol} setup={setup} />)}
          </div>
        )}
      </div>
    </DashboardLayout>
  )
}
