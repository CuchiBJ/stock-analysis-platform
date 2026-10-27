import type { MarketOverview, SectorConstituents } from './market-context'

export type SectorSort = 'events' | 'high-rate' | 'low-rate'
export type SectorRate = { state: 'available'; count: number; eligible: number; ratio: number } | { state: 'no-coverage' } | { state: 'unavailable' }
export type SectorConcentration =
  | { state: 'available'; count: number; total: number; percent: number; sectors: string[] }
  | { state: 'no-events' }
  | { state: 'incomplete' }

function validCount(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && Number.isInteger(value) && value >= 0
}

export function sectorRate(sector: SectorConstituents, side: 'highs' | 'lows'): SectorRate {
  return incidenceRate(sector[side].length, sector.eligible_symbols)
}

export function incidenceRate(count: unknown, eligible: unknown): SectorRate {
  if (!validCount(eligible)) return { state: 'unavailable' }
  if (eligible === 0) return { state: 'no-coverage' }
  if (!validCount(count) || count > eligible) return { state: 'unavailable' }
  return { state: 'available', count, eligible, ratio: count / eligible }
}

export function sectorConcentration(sectors: SectorConstituents[], total: number, side: 'highs' | 'lows'): SectorConcentration {
  if (!validCount(total)) return { state: 'incomplete' }
  const sectorTotal = sectors.reduce((sum, sector) => sum + sector[side].length, 0)
  if (!validCount(sectorTotal) || sectorTotal !== total) return { state: 'incomplete' }
  if (total === 0) return { state: 'no-events' }
  const leaders = sectors
    .filter(sector => sector[side].length > 0)
    .slice()
    .sort((a, b) => b[side].length - a[side].length || a.sector.localeCompare(b.sector))
    .slice(0, 2)
  const count = leaders.reduce((sum, sector) => sum + sector[side].length, 0)
  return { state: 'available', count, total, percent: count / total, sectors: leaders.map(sector => sector.sector) }
}

export function sortSectors(sectors: SectorConstituents[], by: SectorSort): SectorConstituents[] {
  return sectors.slice().sort((a, b) => {
    if (by === 'events') {
      return (b.highs.length + b.lows.length) - (a.highs.length + a.lows.length) || a.sector.localeCompare(b.sector)
    }
    const side = by === 'high-rate' ? 'highs' : 'lows'
    const rateA = sectorRate(a, side)
    const rateB = sectorRate(b, side)
    const valueA = rateA.state === 'available' ? rateA.ratio : null
    const valueB = rateB.state === 'available' ? rateB.ratio : null
    if (valueA == null && valueB != null) return 1
    if (valueB == null && valueA != null) return -1
    if (valueA != null && valueB != null && valueA !== valueB) return valueB - valueA
    return a.sector.localeCompare(b.sector)
  })
}

export function sectorTotals(data: MarketOverview['extremes']) {
  return {
    highs: sectorConcentration(data.sectors, data.up_count, 'highs'),
    lows: sectorConcentration(data.sectors, data.down_count, 'lows'),
  }
}
