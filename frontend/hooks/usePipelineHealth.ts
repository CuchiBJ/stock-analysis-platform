'use client'

import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/lib/api-client'
import type { HealthSnapshot } from '@/types/health'

const REFETCH_MS = 30_000

export function usePipelineHealth() {
  return useQuery<HealthSnapshot>({
    queryKey: ['pipeline-health'],
    queryFn: async () => {
      const r = await apiFetch('/api/v1/health/data-freshness')
      if (!r.ok) throw new Error(`health endpoint returned ${r.status}`)
      return (await r.json()) as HealthSnapshot
    },
    refetchInterval: REFETCH_MS,
    staleTime: REFETCH_MS / 2,
    refetchOnWindowFocus: false,
  })
}
