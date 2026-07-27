'use client'

import { useEffect } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import Card from '@/components/base/Card'
import dynamic from 'next/dynamic'

const MarketContextBar       = dynamic(() => import('@/components/dashboard/MarketContextBar'),       { ssr: false })
const SectorRotationCallout  = dynamic(() => import('@/components/dashboard/SectorRotationCallout'),  { ssr: false })
const TopActionableSetups = dynamic(() => import('@/components/dashboard/TopActionableSetups'),  { ssr: false })
const LiveTransitionFeed  = dynamic(() => import('@/components/dashboard/LiveTransitionFeed'),   { ssr: false })
const SectorHeatmap       = dynamic(() => import('@/components/charts/SectorHeatmap'),           { ssr: false })

export default function DashboardPage() {
  // Keyboard nav — only when no input/textarea/contenteditable has focus
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey) return
      const target = e.target as HTMLElement | null
      if (target) {
        const tag = target.tagName
        if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
        if (target.isContentEditable) return
      }
      if (e.key === 'r') window.location.reload()
      if (e.key === '1') document.getElementById('setups')?.scrollIntoView({ behavior: 'smooth' })
      if (e.key === '2') document.getElementById('transitions')?.scrollIntoView({ behavior: 'smooth' })
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <DashboardLayout>

      {/* STATUS BAR — multi-dimensional market context (participation + leadership) */}
      <div className="mb-4 space-y-2">
        <MarketContextBar />
        <SectorRotationCallout />
      </div>

      {/* PRIMARY PANEL — top actionable setups, full width */}
      <div className="mb-4" id="setups">
        <TopActionableSetups />
      </div>

      {/* SECONDARY ROW — live transitions (signal) + sector context */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4" id="transitions">
        {/* Transitions gets more horizontal space */}
        <div className="lg:col-span-3">
          <LiveTransitionFeed />
        </div>
        <div className="lg:col-span-2">
          <Card blockType="sector" className="p-4 h-full">
            <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">
              Sector Leadership
            </h3>
            <SectorHeatmap />
          </Card>
        </div>
      </div>

    </DashboardLayout>
  )
}
