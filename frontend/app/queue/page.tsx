'use client'

import { useState, useEffect, useCallback } from 'react'
import { API_URL } from '@/lib/utils'
import DashboardLayout from '@/components/layout/DashboardLayout'
import UnderCutRallyQueue from '@/components/queue/UnderCutRallyQueue'
import EmergingLeadersQueue from '@/components/queue/EmergingLeadersQueue'
import BuildingBasesQueue from '@/components/queue/BuildingBasesQueue'

type Tab = 'u-and-r' | 'emerging' | 'building-bases'

interface Counts {
  uAndR: number | null
  emerging: number | null
  buildingBases: number | null
}

export default function QueuePage() {
  const [activeTab, setActiveTab] = useState<Tab>('u-and-r')
  const [counts, setCounts] = useState<Counts>({ uAndR: null, emerging: null, buildingBases: null })
  const [refreshKey, setRefreshKey] = useState(0)

  const fetchCounts = useCallback(async () => {
    try {
      const [uar, em, bb] = await Promise.all([
        fetch(`${API_URL}/api/v1/queue/u-and-r`).then(r => r.ok ? r.json() : []),
        fetch(`${API_URL}/api/v1/queue/emerging-leaders`).then(r => r.ok ? r.json() : []),
        fetch(`${API_URL}/api/v1/queue/building-bases`).then(r => r.ok ? r.json() : []),
      ])
      const count = (d: unknown) =>
        Array.isArray(d) ? d.length : (d as { results?: unknown[] })?.results?.length ?? 0
      setCounts({
        uAndR:        count(uar),
        emerging:     count(em),
        buildingBases: count(bb),
      })
    } catch {
      // leave counts as-is
    }
  }, [])

  useEffect(() => {
    fetchCounts()
    const interval = setInterval(() => {
      fetchCounts()
      setRefreshKey(k => k + 1)
    }, 60_000)
    return () => clearInterval(interval)
  }, [fetchCounts])

  const tabClass = (t: Tab) =>
    `px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
      activeTab === t
        ? 'border-primary text-foreground'
        : 'border-transparent text-muted-foreground hover:text-foreground'
    }`

  return (
    <DashboardLayout>
    <div className="container mx-auto p-6 max-w-6xl">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-foreground">Setup Queue</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Líderes en corrección listos para ejecución. Click en un símbolo para ver su diagnostic completo.
        </p>
      </header>

      <div className="flex gap-1 border-b border-border mb-4">
        <button onClick={() => setActiveTab('u-and-r')} className={tabClass('u-and-r')}>
          U&R{counts.uAndR !== null && <span className="ml-2 text-xs text-muted-foreground">({counts.uAndR})</span>}
        </button>
        <button onClick={() => setActiveTab('emerging')} className={tabClass('emerging')}>
          Emerging Leaders{counts.emerging !== null && <span className="ml-2 text-xs text-muted-foreground">({counts.emerging})</span>}
        </button>
        <button onClick={() => setActiveTab('building-bases')} className={tabClass('building-bases')}>
          Building Bases{counts.buildingBases !== null && <span className="ml-2 text-xs text-muted-foreground">({counts.buildingBases})</span>}
        </button>
      </div>

      <div>
        {activeTab === 'u-and-r' && <UnderCutRallyQueue refreshKey={refreshKey} />}
        {activeTab === 'emerging' && <EmergingLeadersQueue refreshKey={refreshKey} />}
        {activeTab === 'building-bases' && <BuildingBasesQueue refreshKey={refreshKey} />}
      </div>
    </div>
    </DashboardLayout>
  )
}
