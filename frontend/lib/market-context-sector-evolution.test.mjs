import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import Module from 'node:module'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import ts from 'typescript'

function loadTs(path, aliases = {}) {
  const instance = new Module(path)
  instance.filename = path
  instance.paths = Module._nodeModulePaths(dirname(path))
  const originalLoad = Module._load
  Module._load = function (request, parent, isMain) {
    if (Object.hasOwn(aliases, request)) return aliases[request]
    return originalLoad.call(this, request, parent, isMain)
  }
  try {
    instance._compile(ts.transpileModule(readFileSync(path, 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
    }).outputText, path)
  } finally {
    Module._load = originalLoad
  }
  return instance.exports
}

const helperPath = fileURLToPath(new URL('./market-context-sector-evolution.ts', import.meta.url))
const { normalizeSectorEvolution } = loadTs(helperPath)
const componentPath = fileURLToPath(new URL('../components/market-context/SectorEvolution.tsx', import.meta.url))
const Component = loadTs(componentPath).default

const AS_OF = '2026-10-22'
function session(date, sectors) {
  return {
    date,
    eligible_symbols: sectors.reduce((sum, item) => sum + item.eligible_symbols, 0),
    excluded_symbols: sectors.reduce((sum, item) => sum + item.excluded_symbols, 0),
    high_count: sectors.reduce((sum, item) => sum + item.high_count, 0),
    low_count: sectors.reduce((sum, item) => sum + item.low_count, 0),
    sectors,
  }
}
function sec(sector, eligible_symbols, excluded_symbols, high_count, low_count) {
  return { sector, eligible_symbols, excluded_symbols, high_count, low_count }
}
function fixture() {
  return {
    as_of: AS_OF,
    status: 'available',
    sessions: [
      session('2026-10-21', [sec('Energy', 60, 6, 4, 1), sec('Technology', 40, 4, 1, 3)]),
      session('2026-10-22', [sec('Energy', 50, 8, 1, 6), sec('Technology', 40, 7, 1, 2)]),
    ],
  }
}
function render(result, props = {}) {
  return renderToStaticMarkup(React.createElement(Component, {
    result, pending: false, error: false, fetching: false, onRetry() {}, ...props,
  }))
}

test('normalizes validated totals and derives endpoint rates, coverage, active sectors and concentration', () => {
  const result = normalizeSectorEvolution(fixture(), AS_OF)
  assert.equal(result.state, 'available')
  assert.deepEqual(result.sectors.map(row => [row.sector, row.direction]), [['Energy', 'deterioration'], ['Technology', 'improvement']])
  const energy = result.sectors[0]
  assert.equal(energy.comparison.high_delta_pp, -4.7)
  assert.equal(energy.comparison.low_delta_pp, 10.3)
  assert.equal(energy.comparison.eligible_delta, -10)
  assert.equal(energy.comparison.excluded_delta, 2)
  assert.deepEqual(result.summary.highs.first, { active_sectors: 2, eligible_sectors: 2 })
  assert.deepEqual(result.summary.lows.last, { active_sectors: 2, eligible_sectors: 2 })
  assert.equal(result.summary.concentration.highs.first.percent, 1)
  assert.deepEqual(result.summary.concentration.highs.last.sectors, ['Energy', 'Technology'])
})

test('keeps an absent intermediate sector as a sparkline gap and missing endpoint unavailable', () => {
  const data = fixture()
  data.sessions = [
    session('2026-10-20', [sec('Energy', 60, 6, 4, 1), sec('Technology', 40, 4, 1, 3)]),
    session('2026-10-21', [sec('Technology', 40, 4, 1, 3)]),
    session(AS_OF, [sec('Energy', 50, 8, 1, 6), sec('Technology', 40, 7, 1, 2)]),
  ]
  const result = normalizeSectorEvolution(data, AS_OF)
  const energy = result.sectors.find(row => row.sector === 'Energy')
  assert.equal(energy.points[1], null)
  assert.equal(energy.comparison.state, 'available')
  const html = render(result)
  assert.doesNotMatch(html, /2026-10-21: sin observación para este sector/)
  assert.doesNotMatch(html, /<svg/)
  const componentSource = readFileSync(new URL('../components/market-context/SectorEvolution.tsx', import.meta.url), 'utf8')
  assert.match(componentSource, /dateEvidence\(point\)/)

  const endpointMissing = fixture()
  endpointMissing.sessions[0].sectors = [sec('Technology', 100, 10, 5, 4)]
  endpointMissing.sessions[0] = session(endpointMissing.sessions[0].date, endpointMissing.sessions[0].sectors)
  const absent = normalizeSectorEvolution(endpointMissing, AS_OF)
  assert.equal(absent.sectors.find(row => row.sector === 'Energy').comparison.state, 'unavailable')
  assert.match(absent.sectors.find(row => row.sector === 'Energy').comparison.reason, /ambas fechas/)
  assert.doesNotMatch(render(absent), /<svg/)
})

test('distinguishes valid zero events from zero coverage and leaves concentration unavailable without events', () => {
  const data = {
    as_of: AS_OF,
    status: 'available',
    sessions: [
      session('2026-10-21', [sec('A', 10, 2, 0, 0), sec('Sin sector', 0, 3, 0, 0)]),
      session(AS_OF, [sec('A', 8, 4, 0, 0), sec('Sin sector', 0, 5, 0, 0)]),
    ],
  }
  const result = normalizeSectorEvolution(data, AS_OF)
  const covered = result.sectors.find(row => row.sector === 'A')
  const noCoverage = result.sectors.find(row => row.sector === 'Sin sector')
  assert.equal(covered.points[0].high_rate, 0)
  assert.equal(covered.direction, 'unchanged')
  assert.equal(noCoverage.points[0].high_rate, null)
  assert.equal(noCoverage.comparison.state, 'unavailable')
  assert.deepEqual(result.summary.concentration.highs.last, { state: 'no-events' })
  assert.match(render(result), /Sin cobertura/)
  assert.match(render(result), /Sin eventos; concentración no disponible/)
})

test('reconciles aggregate counters and rejects invalid, duplicate, unordered, excess or non-ending sessions', () => {
  const cases = [
    data => { data.sessions[1].high_count += 1 },
    data => { data.sessions[1].sectors[0].eligible_symbols += 1 },
    data => { data.sessions[1].sectors.push({ ...data.sessions[1].sectors[0] }) },
    data => { data.sessions[1].date = '2026-02-30' },
    data => { data.sessions.reverse() },
    data => { data.sessions[1].date = '2026-10-23' },
    data => { data.sessions.push(...Array.from({ length: 4 }, (_, index) => ({ ...data.sessions[1], date: `2026-10-${String(23 + index).padStart(2, '0')}` }))) },
    data => { data.sessions[1].sectors[0].high_count = -1 },
  ]
  for (const mutate of cases) {
    const data = structuredClone(fixture())
    mutate(data)
    assert.equal(normalizeSectorEvolution(data, AS_OF).state, 'unavailable')
  }
})

test('invalid intermediate or endpoint rows fail closed instead of shortening comparison window', () => {
  const intermediate = fixture()
  intermediate.sessions = [
    session('2026-10-20', [sec('Energy', 60, 6, 4, 1), sec('Technology', 40, 4, 1, 3)]),
    { ...session('2026-10-21', [sec('Technology', 40, 4, 1, 3)]), eligible_symbols: -1 },
    session(AS_OF, [sec('Energy', 50, 8, 1, 6), sec('Technology', 40, 7, 1, 2)]),
  ]
  assert.equal(normalizeSectorEvolution(intermediate, AS_OF).state, 'unavailable')

  const endpoint = fixture()
  endpoint.sessions[0].eligible_symbols = -5
  assert.equal(normalizeSectorEvolution(endpoint, AS_OF).state, 'unavailable')
  const lastEndpoint = fixture()
  lastEndpoint.sessions[1].sectors[0].high_count = 99
  assert.equal(normalizeSectorEvolution(lastEndpoint, AS_OF).state, 'unavailable')
})

test('handles no-reference, legacy API and isolated loading/error states', () => {
  assert.deepEqual(normalizeSectorEvolution({ as_of: AS_OF, status: 'no_reference_session', sessions: [] }, AS_OF), { state: 'no-reference-session', as_of: AS_OF })
  assert.equal(normalizeSectorEvolution({ as_of: AS_OF, status: 'no_reference_session', sessions: [fixture().sessions[1]] }, AS_OF).state, 'unavailable')
  assert.match(render(null), /aún no ofrece el historial sectorial/i)
  assert.match(render(undefined, { pending: true }), /Cargando evolución sectorial/)
  assert.match(render(normalizeSectorEvolution(fixture(), AS_OF), { error: true }), /Se conserva el último dato recibido/)
  assert.match(render(normalizeSectorEvolution(fixture(), AS_OF), { error: true }), /No se pudo actualizar/)
})

test('zero total eligibility is no coverage, not no events or zero concentration', () => {
  const data = { as_of: AS_OF, status: 'available', sessions: [
    session('2026-10-21', [sec('Sin sector', 0, 3, 0, 0)]),
    session(AS_OF, [sec('Sin sector', 0, 4, 0, 0)]),
  ] }
  const result = normalizeSectorEvolution(data, AS_OF)
  assert.deepEqual(result.summary.concentration.highs.first, { state: 'no-coverage' })
  assert.match(render(result), /Sin cobertura; concentración no disponible/)
  assert.match(render(result), /Sin cobertura suficiente/)
  assert.doesNotMatch(render(result), /0\/0 \(2026-10-21\).*0\/0 \(2026-10-22\)/)
})

test('one returned session shows levels once and does not imply an endpoint change', () => {
  const data = { as_of: AS_OF, status: 'available', sessions: [fixture().sessions[1]] }
  const result = normalizeSectorEvolution(data, AS_OF)
  assert.equal(result.sectors[0].comparison.state, 'unavailable')
  const html = render(result)
  assert.match(html, /Hay una sola sesión/)
  assert.match(html, /Sectores con máximos: 2\/2 \(2026-10-22\)/)
  assert.doesNotMatch(html, /Sectores con máximos: .*→/)
  assert.match(html, /Concentración top 2 de máximos: .*\(2026-10-22\)/)
})

test('renders a six-column dated sector summary with no graphs until a sector is selected', () => {
  const html = render(normalizeSectorEvolution(fixture(), AS_OF))
  assert.match(html, /Evolución de extremos por sector/)
  assert.match(html, /sesión anterior del calendario SPY/)
  assert.match(html, /Los empates no generan eventos/)
  assert.doesNotMatch(html, /máximo anual|mínimo anual|252 sesiones/)
  assert.equal((html.match(/scope="col"/g) ?? []).length, 6)
  assert.match(html, /Tasas y cobertura al <span class="whitespace-nowrap">2026-10-22<\/span> · Cambios entre <span class="whitespace-nowrap">2026-10-21<\/span> y <span class="whitespace-nowrap">2026-10-22<\/span>/)
  assert.match(html, /<th scope="col"[^>]*>Máximos<\/th>.*<th scope="col"[^>]*>Mínimos<\/th>.*<th scope="col"[^>]*>Δ máximos<\/th>.*<th scope="col"[^>]*>Δ mínimos<\/th>.*<th scope="col"[^>]*>Cobertura<\/th>/)
  assert.match(html, /-4\.7 pp.*\+10\.3 pp/)
  assert.match(html, /1\/50 \(2\.0%\).*6\/50 \(12\.0%\)/)
  assert.match(html, /50 elegibles · 8 excluidas/)
  assert.match(html, /aria-expanded="false" aria-controls="[^"]+"/)
  assert.match(html, /<article id="[^"]+" hidden=""/)
  assert.equal(html.match(/aria-controls="([^"]+)"/)[1], html.match(/<article id="([^"]+)" hidden=""/)[1])
  assert.doesNotMatch(html, /<svg|Historial de Energy/)
  const source = readFileSync(new URL('../components/market-context/SectorEvolution.tsx', import.meta.url), 'utf8')
  assert.match(source, /setSelection\(current => current\.sector === row\.sector && !current\.dismissed/)
  assert.match(source, /result\.sectors\.find\(row => row\.sector === selection\.sector\)/)
  assert.match(source, /selection\.dismissed \? undefined/)
  assert.match(source, /La cobertura cambió entre las fechas/)
  assert.match(html, /La atribución sectorial y la capitalización usan metadata actual/)
})
