import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import test from 'node:test'
import Module from 'node:module'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import ts from 'typescript'

const libPath = fileURLToPath(new URL('./market-context-sectors.ts', import.meta.url))
const componentPath = fileURLToPath(new URL('../components/market-context/SectorBreadth.tsx', import.meta.url))
function loadTs(path, mocks = {}) {
  const mod = new Module(path)
  mod.filename = path
  mod.paths = Module._nodeModulePaths(dirname(path))
  const originalLoad = Module._load
  Module._load = function (request, parent, isMain) {
    if (Object.hasOwn(mocks, request)) return mocks[request]
    return originalLoad.call(this, request, parent, isMain)
  }
  try {
    const source = readFileSync(path, 'utf8')
    const output = ts.transpileModule(source, {
      compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2020 },
    }).outputText
    mod._compile(output, path)
  } finally {
    Module._load = originalLoad
  }
  return mod.exports
}

const sectors = loadTs(libPath)
const mockContext = {
  breadthStatus: () => '80% positivos entre eventos',
}
const mockLink = ({ href, children, ...props }) => React.createElement('a', { href, ...props }, children)
const SectorBreadth = loadTs(componentPath, {
  '@/lib/market-context': mockContext,
    '@/lib/market-context-sectors': sectors,
    'next/link': { __esModule: true, default: mockLink },
}).default

function stock(symbol) { return { symbol, name: `${symbol} Inc.` } }
function sector(name, eligible, highs, lows = [], excluded = 0) {
  return { sector: name, eligible_symbols: eligible, excluded_symbols: excluded, highs: highs.map(stock), lows: lows.map(stock) }
}

test('derives incidence from eligible stocks, concentration from events, and deterministic sort order', () => {
  const values = [
    sector('Alpha', 100, ['A1', 'A2', 'A3', 'A4', 'A5', 'A6']),
    sector('Beta', 10, ['B1', 'B2', 'B3']),
    sector('Gamma', 10, ['G1', 'G2', 'G3', 'G4', 'G5', 'G6']),
    sector('Sin sector', 0, [], [], 2),
    { sector: 'Legacy', highs: [], lows: [] },
  ]
  assert.deepEqual(sectors.sectorRate(values[0], 'highs'), { state: 'available', count: 6, eligible: 100, ratio: 0.06 })
  assert.equal(sectors.sectorRate(values[1], 'highs').ratio, 0.3)
  assert.deepEqual(sectors.sectorRate(values[3], 'highs'), { state: 'no-coverage' })
  assert.deepEqual(sectors.sectorRate(values[4], 'highs'), { state: 'unavailable' })
  assert.deepEqual(sectors.incidenceRate(Number.NaN, 10), { state: 'unavailable' })
  assert.deepEqual(sectors.incidenceRate(-1, 10), { state: 'unavailable' })
  assert.deepEqual(sectors.incidenceRate(11, 10), { state: 'unavailable' })
  assert.deepEqual(sectors.incidenceRate(0, Number.NaN), { state: 'unavailable' })
  assert.deepEqual(sectors.incidenceRate(0, -1), { state: 'unavailable' })
  const concentration = sectors.sectorConcentration(values.slice(0, 3), 15, 'highs')
  assert.deepEqual(concentration, { state: 'available', count: 12, total: 15, percent: 0.8, sectors: ['Alpha', 'Gamma'] })
  assert.equal(sectors.sectorConcentration(values.slice(0, 2), 15, 'highs').state, 'incomplete')
  assert.equal(sectors.sectorConcentration([sector('Contradiction', 5, ['X'])], 0, 'highs').state, 'incomplete')
  assert.deepEqual(sectors.sortSectors(values, 'high-rate').map(item => item.sector), ['Gamma', 'Beta', 'Alpha', 'Legacy', 'Sin sector'])
  const lowRateValues = [sector('Low', 100, [], ['L1']), sector('High', 10, [], ['H1', 'H2']), sector('No coverage', 0, [], [], 4)]
  assert.deepEqual(sectors.sortSectors(lowRateValues, 'low-rate').map(item => item.sector), ['High', 'Low', 'No coverage'])
  assert.deepEqual(sectors.sortSectors(values, 'events').map(item => item.sector)[0], 'Alpha')
  assert.deepEqual(values.map(item => item.sector), ['Alpha', 'Beta', 'Gamma', 'Sin sector', 'Legacy'])
})

test('renders paired fixed-scale sector rates, concentration, legacy coverage, and stock disclosures', () => {
  const data = {
    date: '2026-10-20', up_count: 15, down_count: 1, eligible_symbols: 120, excluded_symbols: 2,
    up_ratio: 0.9375, sectors: [
      sector('Alpha', 100, ['A1', 'A2', 'A3', 'A4', 'A5', 'A6'], ['A1']),
      sector('Beta', 10, ['B1', 'B2', 'B3']),
      sector('Gamma', 10, ['G1', 'G2', 'G3', 'G4', 'G5', 'G6']),
      sector('Sin sector', 0, [], [], 2),
      { sector: 'Legacy', highs: [], lows: [] },
    ],
  }
  const html = renderToStaticMarkup(React.createElement(SectorBreadth, { data }))
  assert.match(html, /6\/100 \(6\.0%\)/)
  assert.match(html, /3\/10 \(30\.0%\)/)
  assert.match(html, /Concentración de máximos: Alpha, Gamma reúnen 12\/15 \(80\.0%\)/)
  assert.match(html, /Sin cobertura suficiente/)
  assert.match(html, /Cobertura no disponible/)
  assert.match(html, /Escala fija 0–100%/)
  assert.match(html, /Extremos de la sesión/)
  assert.match(html, /Máximos y mínimos intradiarios respecto de la rueda previa; no son máximos de 52 semanas/)
  assert.match(html, /sesión anterior del calendario SPY/)
  assert.match(html, /Los empates no generan eventos/)
  assert.doesNotMatch(html, /252 ruedas/)
  assert.match(html, /Una acción puede registrar ambos extremos/)
  assert.match(html, /href="\/stock\/A1"/)
  assert.match(html, /A1 Inc\./)
  assert.equal((html.match(/href="\/stock\/A1"/g) ?? []).length, 2, 'dual-event stock remains present on both sides')

  const noEvents = { ...data, up_count: 0, down_count: 0, sectors: data.sectors.map(item => ({ ...item, highs: [], lows: [] })) }
  const noEventsHtml = renderToStaticMarkup(React.createElement(SectorBreadth, { data: noEvents }))
  assert.match(noEventsHtml, /Sin eventos en esta sesión/)
  assert.match(noEventsHtml, /Concentración de máximos: sin eventos/)
  assert.match(noEventsHtml, /0\/120 \(0\.0% de elegibles\)/)

  const noCoverage = { ...noEvents, eligible_symbols: 0, excluded_symbols: 120, sectors: [] }
  const noCoverageHtml = renderToStaticMarkup(React.createElement(SectorBreadth, { data: noCoverage }))
  assert.match(noCoverageHtml, /Sin cobertura suficiente/)
  assert.doesNotMatch(noCoverageHtml, /0\/0 \(0\.0%/)

  const incomplete = { ...data, up_count: 16 }
  const incompleteHtml = renderToStaticMarkup(React.createElement(SectorBreadth, { data: incomplete }))
  assert.match(incompleteHtml, /detalle incompleto; concentración no calculada/)
})
