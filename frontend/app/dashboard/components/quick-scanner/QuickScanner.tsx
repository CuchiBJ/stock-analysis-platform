'use client'

import { useState } from 'react'
import { QuickScannerProps } from './types'
import FilterPreset from './FilterPreset'
import { QUICK_PRESETS } from './presets'
import Card from '@/components/base/Card'
import LoadingSkeleton from '@/components/base/LoadingSkeleton'
import { useQuickScanner } from '@/lib/hooks/useScanner'
import { useScannerStore } from '@/lib/store/scannerStore'
import { TrendingUp, TrendingDown, Activity, Zap, Flame } from 'lucide-react'

export default function QuickScanner({ loading }: QuickScannerProps) {
  const [activePreset, setActivePreset] = useState<string>('earnings')
  const { scanResults, scanLoading, scanError } = useScannerStore()
  const quickScanner = useQuickScanner()

  const handlePresetClick = async (presetId: string) => {
    setActivePreset(presetId)
    const preset = QUICK_PRESETS.find(p => p.id === presetId)
    if (preset) {
      await quickScanner.mutateAsync(preset.filters)
    }
  }

  const getChangeColor = (value: number) => {
    if (value > 0) return 'text-green-400'
    if (value < 0) return 'text-red-400'
    return 'text-muted-foreground'
  }

  const getRVOLColor = (rvol: number) => {
    if (rvol >= 2) return 'text-green-400 font-semibold'
    if (rvol >= 1.5) return 'text-green-400'
    if (rvol >= 1.2) return 'text-yellow-400'
    return 'text-muted-foreground'
  }

  if (loading) {
    return (
      <Card className="p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Quick Scanner</h3>
        </div>
        <div className="space-y-2">
          {[...Array(8)].map((_, i) => (
            <LoadingSkeleton key={i} variant="card" />
          ))}
        </div>
      </Card>
    )
  }

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Quick Scanner</h3>
        <div className="flex gap-1">
          {QUICK_PRESETS.map((preset) => (
            <button
              key={preset.id}
              onClick={() => handlePresetClick(preset.id)}
              className={`px-2 py-1 text-[10px] uppercase tracking-wide rounded border transition-all ${activePreset === preset.id
                ? 'bg-primary/10 border-primary text-primary font-medium'
                : 'bg-transparent border-border text-muted-foreground hover:bg-muted'
                }`}
            >
              {preset.name}
            </button>
          ))}
        </div>
      </div>

      {scanLoading && (
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => (
            <LoadingSkeleton key={i} variant="card" />
          ))}
        </div>
      )}

      {scanError && (
        <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
          <p className="text-sm text-red-400">{scanError}</p>
        </div>
      )}

      {scanResults && Array.isArray(scanResults) && scanResults.length > 0 && !scanLoading && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs text-muted-foreground">{scanResults.length} results</span>
            <div className="flex items-center gap-1">
              <span className="text-[10px] text-muted-foreground uppercase tracking-wide">
                {QUICK_PRESETS.find(p => p.id === activePreset)?.name}
              </span>
            </div>
          </div>

          {/* Terminal-style table header */}
          <div className="grid grid-cols-8 gap-2 px-2 py-2 text-[10px] font-semibold text-muted-foreground border-b border-border bg-muted/30 sticky top-0">
            <div className="col-span-1">Ticker</div>
            <div className="col-span-2">Sector</div>
            <div className="col-span-1 text-right">% Day</div>
            <div className="col-span-1 text-right">RVOL</div>
            <div className="col-span-1 text-right">RS</div>
            <div className="col-span-1 text-right">Price</div>
            <div className="col-span-1 text-center">Badges</div>
          </div>

          {/* Terminal-style table body */}
          <div className="max-h-[300px] overflow-y-auto">
            {scanResults.slice(0, 20).map((result: any, index: number) => (
              <div
                key={result.symbol}
                className="grid grid-cols-8 gap-2 px-2 py-2 text-[11px] border-b border-border/50 hover:bg-muted/50 transition-colors group"
              >
                <div className="col-span-1 font-bold text-white group-hover:text-primary transition-colors">
                  {result.symbol}
                </div>
                <div className="col-span-2 text-muted-foreground truncate text-[10px]">
                  {result.sector}
                </div>
                <div className={`col-span-1 font-mono text-right ${getChangeColor(result.gain_pct || 0)}`}>
                  {result.gain_pct ? (result.gain_pct > 0 ? '+' : '') + result.gain_pct.toFixed(2) + '%' : 'N/A'}
                </div>
                <div className={`col-span-1 font-mono text-right ${getRVOLColor(result.rvol || 0)}`}>
                  {result.rvol ? result.rvol.toFixed(2) + 'x' : 'N/A'}
                </div>
                <div className={`col-span-1 font-mono text-right ${result.rs_rank >= 90 ? 'text-green-400' : result.rs_rank >= 80 ? 'text-green-400' : 'text-muted-foreground'}`}>
                  {result.rs_rank ? '#' + result.rs_rank : 'N/A'}
                </div>
                <div className="col-span-1 font-mono text-right text-muted-foreground">
                  {result.price ? '$' + result.price.toFixed(2) : 'N/A'}
                </div>
                <div className="col-span-1 flex items-center gap-1 flex-wrap justify-center">
                  {result.badges?.slice(0, 2).map((badge: string, i: number) => (
                    <span
                      key={i}
                      className={`px-1.5 py-0.5 rounded text-[9px] font-medium border flex items-center gap-0.5 ${badge === 'breakout' ? 'bg-green-500/20 text-green-400 border-green-500/30' :
                        badge === 'near ATH' ? 'bg-blue-500/20 text-blue-400 border-blue-500/30' :
                          badge === 'squeeze' ? 'bg-orange-500/20 text-orange-400 border-orange-500/30' :
                            badge === 'unusual volume' ? 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30' :
                              'bg-muted text-muted-foreground border-border'
                        }`}
                    >
                      {badge === 'breakout' && <TrendingUp className="w-3 h-3" />}
                      {badge === 'near ATH' && <Flame className="w-3 h-3" />}
                      {badge === 'squeeze' && <Zap className="w-3 h-3" />}
                      {badge === 'unusual volume' && <Activity className="w-3 h-3" />}
                      <span className="hidden sm:inline">{badge}</span>
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>

          {scanResults.length > 20 && (
            <div className="mt-3 text-center">
              <button className="text-xs text-muted-foreground hover:text-foreground transition-colors">
                View all {scanResults.length} results →
              </button>
            </div>
          )}
        </div>
      )}

      {!scanResults && !scanLoading && (
        <div className="p-8 text-center">
          <Activity className="w-8 h-8 mx-auto text-muted-foreground mb-2" />
          <p className="text-sm text-muted-foreground">Select a preset to scan</p>
        </div>
      )}
    </Card>
  )
}
