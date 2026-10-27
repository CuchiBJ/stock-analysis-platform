import test from 'node:test'
import assert from 'node:assert/strict'
import { benchmarkPriceFreshness, benchmarksComparable, breadthStatus, evidenceDate, evidenceFreshness, numberText, changeText, percentText, vixFreshnessState, vixPresentation } from './market-context.ts'

test('breadth distinguishes insufficient coverage from zero events', () => {
  assert.equal(breadthStatus({ eligible_symbols: 0, up_count: 0, down_count: 0, up_ratio: null }), 'Sin cobertura suficiente')
  assert.equal(breadthStatus({ eligible_symbols: 12, up_count: 0, down_count: 0, up_ratio: null }), 'Sin eventos en esta sesión')
  assert.equal(breadthStatus({ eligible_symbols: 12, up_count: 0, down_count: 2, up_ratio: 0 }), '0.0% positivos entre eventos')
})
test('missing quotes and changes are never represented as zero', () => {
  assert.equal(numberText(null), 'Sin datos')
  assert.equal(changeText(null), 'Sin datos')
  assert.equal(percentText(null), 'Sin datos')
  assert.equal(numberText(0), '0.00')
  assert.equal(changeText(0), '0.00%')
  assert.equal(changeText(-0.5, ' pts'), '-0.50 pts')
})
test('evidence explicitly labels earlier dates while preserving exact session', () => {
  assert.equal(evidenceDate('2026-10-19', '2026-10-20'), '2026-10-19 · Dato anterior al contexto')
  assert.equal(evidenceDate('2026-10-20', '2026-10-20'), '2026-10-20')
  assert.equal(evidenceDate(null, '2026-10-20'), 'Fecha no disponible')
})
test('freshness uses strict calendar dates and handles dates on either side of context', () => {
  assert.equal(evidenceFreshness('2026-10-21', '2026-10-21'), 'current')
  assert.equal(evidenceFreshness('2026-08-17', '2026-10-21'), 'earlier')
  assert.equal(evidenceFreshness('2026-10-22', '2026-10-21'), 'later')
  for (const invalid of ['2026-02-29', '2026-13-01', '2026-10-1', 'bad']) {
    assert.equal(evidenceFreshness(invalid, '2026-10-21'), 'unavailable')
  }
  assert.equal(evidenceFreshness('2024-02-29', '2024-02-29'), 'current')
})
test('benchmark price validity and pair comparability require finite current quotes', () => {
  const current = (symbol, price, date = '2026-10-21') => ({ symbol, price, date })
  assert.equal(benchmarkPriceFreshness(null, '2026-10-21', '2026-10-21'), 'unavailable')
  assert.equal(benchmarkPriceFreshness(Number.POSITIVE_INFINITY, '2026-10-21', '2026-10-21'), 'unavailable')
  assert.equal(benchmarksComparable([current('SPY', 600), current('QQQ', 500)], '2026-10-21'), true)
  assert.equal(benchmarksComparable([current('SPY', 600), current('QQQ', 500, '2026-08-17')], '2026-10-21'), false)
  assert.equal(benchmarksComparable([current('SPY', 600), current('QQQ', null)], '2026-10-21'), false)
})
test('VIX quote age and refresh health remain independent', () => {
  const asOf = '2026-10-21'
  assert.deepEqual(vixFreshnessState('2026-10-20', asOf, false, 'stale'), {
    freshness: 'earlier', isPreviousClose: true, refreshWarning: null, dateWarning: null,
  })
  assert.equal(vixFreshnessState(asOf, asOf, true, 'stale').refreshWarning, 'Falló la actualización de la fuente')
  assert.equal(vixFreshnessState(asOf, asOf, undefined, 'stale').refreshWarning, 'Actualización no confirmada')
  assert.equal(vixFreshnessState(asOf, asOf, false, 'current').refreshWarning, null)
  assert.equal(vixFreshnessState('invalid', asOf, false, 'current').dateWarning, 'Fecha de VIX no válida; no comparable')
})
test('VIX prefers only same-session spot while preserving explicit daily fallback', () => {
  const daily = { symbol: 'VIX', price: 19.45, change_points: 1, change_pct: 5, date: '2026-10-23', source: 'Cboe', source_url: 'https://example.com', status: 'stale' }
  const spot = { symbol: 'VIX', price: 18.33, previous_close: 19.45, change_points: -1.12, change_pct: -5.7, date: '2026-10-26', observed_at: '2026-10-26T18:13:31+00:00', fetched_at: '2026-10-26T18:30:00+00:00', source: 'Cboe', source_url: 'https://example.com', delay_minutes: 20, status: 'current', refresh_failed: false }
  assert.equal(vixPresentation({ vix: daily, current_quote: spot }, '2026-10-26').kind, 'spot')
  assert.equal(vixPresentation({ vix: daily, current_quote: { ...spot, status: 'stale' } }, '2026-10-26').kind, 'spot')
  assert.deepEqual(vixPresentation({ vix: daily, current_quote: { ...spot, date: '2026-10-23' } }, '2026-10-26'), { kind: 'daily', quote: daily, earlierSpot: true })
  assert.deepEqual(vixPresentation({ vix: null, current_quote: null }, '2026-10-26'), { kind: 'unavailable', earlierSpot: false })
})
