'use client'

import DashboardLayout from '@/components/layout/DashboardLayout'
import dynamic from 'next/dynamic'
import IndexGrid from './components/market-overview/IndexGrid'
import BreadthPanel from './components/market-breadth/BreadthPanel'
import MarketStatePanel from './components/market-state/MarketStatePanel'
import CapitalFlowPanel from './components/capital-flow/CapitalFlowPanel'
import { useMarketStore } from '@/lib/store/marketStore'
import { useIndices, useBreadth } from '@/lib/hooks/useMarketData'

const SectorHeatmap = dynamic(() => import('@/components/charts/SectorHeatmap'), { ssr: false })
const LeadersTable = dynamic(() => import('./components/leaders/LeadersTable'), { ssr: false })
const QuickScanner = dynamic(() => import('./components/quick-scanner/QuickScanner'), { ssr: false })
const QualityPullbacks = dynamic(() => import('./components/pullbacks/QualityPullbacks'), { ssr: false })
const LeadersUnderPressure = dynamic(() => import('./components/pullbacks/LeadersUnderPressure'), { ssr: false })
const EarlyReclaims = dynamic(() => import('./components/pullbacks/EarlyReclaims'), { ssr: false })
const ControlledPullbacks = dynamic(() => import('./components/pullbacks/ControlledPullbacks'), { ssr: false })
const WeeklyStructurePanel = dynamic(() => import('./components/weekly-structure/WeeklyStructurePanel'), { ssr: false })
const MarketEnvironmentPanel = dynamic(() => import('./components/market-environment/MarketEnvironmentPanel'), { ssr: false })
const QualitySwingScanner = dynamic(() => import('./components/quality-swing-scanner/QualitySwingScanner'), { ssr: false })
const WeeklyFirstVisuals = dynamic(() => import('./components/weekly-first-visuals/WeeklyFirstVisuals'), { ssr: false })
const RelativeStrengthVisuals = dynamic(() => import('./components/relative-strength/RelativeStrengthVisuals'), { ssr: false })

export default function DashboardPage() {
  useIndices()
  useBreadth()
  const indices = useMarketStore((state) => state.indices)
  const indicesLoading = useMarketStore((state) => state.indicesLoading)

  return (
    <DashboardLayout>
      {/* TOP ROW: Market State + Indices */}
      <div className="mb-4">
        <MarketStatePanel />
      </div>

      <div className="mb-4">
        <IndexGrid indices={indices} loading={indicesLoading} />
      </div>

      {/* MARKET ENVIRONMENT ROW */}
      <div className="mb-4">
        <MarketEnvironmentPanel />
      </div>

      {/* PRIMARY ROW: Quality Pullbacks (Most Important - Top Priority) */}
      <div className="mb-4">
        <QualityPullbacks />
      </div>

      {/* SECONDARY ROW: Leaders Under Pressure + Controlled Pullbacks */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <LeadersUnderPressure />
        <ControlledPullbacks />
      </div>

      {/* TERTIARY ROW: Early Reclaims + Weekly Structure */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <EarlyReclaims />
        <WeeklyStructurePanel />
      </div>

      {/* QUATERNARY ROW: Weekly First Visuals */}
      <div className="mb-4">
        <WeeklyFirstVisuals />
      </div>

      {/* QUINARY ROW: Relative Strength Visuals */}
      <div className="mb-4">
        <RelativeStrengthVisuals />
      </div>

      {/* SENARY ROW: Sector Rotation + Quality Swing Scanner */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <div>
          <h2 className="text-sm font-semibold text-muted-foreground mb-2 uppercase tracking-wide">Sector Rotation</h2>
          <SectorHeatmap />
        </div>
        <QualitySwingScanner />
      </div>

      {/* BOTTOM ROW: Market Breadth + Capital Flow */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <BreadthPanel />
        <CapitalFlowPanel />
      </div>
    </DashboardLayout>
  )
}
