'use client'

import { useState } from 'react'
import { usePipelineHealth } from '@/hooks/usePipelineHealth'
import { computeChipColor, dotClass } from './pipelineHealthUtils'
import PipelineHealthDrawer from './PipelineHealthDrawer'

export default function PipelineHealthChip() {
  const { data: health } = usePipelineHealth()
  const [open, setOpen] = useState(false)

  if (!health) {
    return (
      <button
        type="button"
        aria-label="Pipeline health loading"
        className="flex items-center gap-1.5 text-xs text-muted-foreground"
        disabled
      >
        <span className="h-2 w-2 rounded-full bg-white/20" />
        <span>—</span>
      </button>
    )
  }

  const color = computeChipColor(health)
  const pct = Math.round(health.coverage.pct)

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Open pipeline health detail"
        className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
      >
        <span className={`h-2 w-2 rounded-full ${dotClass(color)}`} />
        <span className="font-mono">{pct}%</span>
        {health.market_state.is_warmup && (
          <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/30">
            WARMUP
          </span>
        )}
      </button>
      <PipelineHealthDrawer
        open={open}
        onClose={() => setOpen(false)}
        snapshot={health}
      />
    </>
  )
}
