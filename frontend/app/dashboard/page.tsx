'use client'

import { useEffect } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import Card from '@/components/base/Card'
import dynamic from 'next/dynamic';

import { usePricePolling } from '@/hooks/usePricePolling';

// Dynamic imports with SSR disabled
const MarketRegimePanel = dynamic(() => import('@/components/dashboard/MarketRegimePanel'), { ssr: false });
const LeaderHealthMap = dynamic(() => import('@/components/dashboard/LeaderHealthMap'), { ssr: false });
const LiveTransitionFeed = dynamic(() => import('@/components/dashboard/LiveTransitionFeed'), { ssr: false });
const TopActionableSetups = dynamic(() => import('@/components/dashboard/TopActionableSetups'), { ssr: false });
const SectorHeatmap = dynamic(() => import('@/components/charts/SectorHeatmap'), { ssr: false });
const WeeklyStructurePanel = dynamic(() => import('./components/weekly-structure/WeeklyStructurePanel'), { ssr: false });

export default function DashboardPage() {
  // Use price polling instead of WebSocket
  const { prices, lastUpdate, isLoading, error } = usePricePolling({
    symbols: ['NVDA', 'AMD', 'INTC'], // Symbols with data in database
    pollInterval: 30000, // 30 seconds
    enabled: true,
  });

  const connectionStatus = isLoading ? 'loading' : (error ? 'error' : 'connected');

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Keyboard shortcuts
      if (e.key === 'r' && !e.ctrlKey && !e.metaKey) {
        // 'r' to refresh
        window.location.reload()
      } else if (e.key === '1') {
        // '1' to scroll to Live Transitions
        document.getElementById('live-transitions')?.scrollIntoView({ behavior: 'smooth' })
      } else if (e.key === '2') {
        // '2' to scroll to Top Actionable Setups
        document.getElementById('actionable-setups')?.scrollIntoView({ behavior: 'smooth' })
      } else if (e.key === '3') {
        // '3' to scroll to Market Context
        document.getElementById('market-context')?.scrollIntoView({ behavior: 'smooth' })
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  return (
    <DashboardLayout>
      {/* Real-time connection indicator */}
      <div className="flex items-center gap-2 mb-4 px-4 py-2 bg-white/5 border border-white/10 rounded-lg">
        <div className={`w-2 h-2 rounded-full ${connectionStatus === 'connected'
          ? 'bg-green-500 animate-pulse'
          : connectionStatus === 'loading'
            ? 'bg-yellow-500 animate-pulse'
            : 'bg-red-500'
          }`} />
        <span className="text-xs text-muted-foreground">
          {connectionStatus === 'connected'
            ? 'Prices connected (polling)'
            : connectionStatus === 'loading'
              ? 'Loading prices...'
              : 'Prices disconnected'
          }
        </span>
        {lastUpdate && (
          <span className="text-xs text-muted-foreground ml-auto">
            Last update: {new Date(lastUpdate).toLocaleTimeString()}
          </span>
        )}
      </div>

      {/* TOP ROW: Market Context (3 panels horizontal - compact) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4" id="market-context">
        <MarketRegimePanel />
        <LeaderHealthMap />
        <div className="bg-white/5 border border-white/10 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-2">Market Forgiveness</h3>
          <p className="text-xs text-muted-foreground">Not yet implemented</p>
        </div>
      </div>

      {/* CENTER ROW: Live Transitions (left) + Top Actionable Setups (right) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <div id="live-transitions">
          <LiveTransitionFeed />
        </div>
        <div id="actionable-setups">
          <TopActionableSetups />
        </div>
      </div>

      {/* BOTTOM ROW: Sector Leadership + Structure Feed (compact) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card blockType="sector" className="p-4">
          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">Sector Leadership</h3>
          <SectorHeatmap />
        </Card>
        <div id="weekly-structure">
          <WeeklyStructurePanel />
        </div>
      </div>
    </DashboardLayout>
  )
}
