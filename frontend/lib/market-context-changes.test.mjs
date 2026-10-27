import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import Module from 'node:module'
import ts from 'typescript'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

function loadTs(path, aliases = {}) {
  const instance = new Module(path)
  instance.filename = path
  instance.paths = Module._nodeModulePaths(dirname(path))
  const originalLoad = Module._load
  Module._load = function (request, parent, isMain) {
    if (aliases[request]) return aliases[request]
    return originalLoad.call(this, request, parent, isMain)
  }
  try {
    instance._compile(ts.transpileModule(readFileSync(path, 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2020 },
    }).outputText, path)
  } finally {
    Module._load = originalLoad
  }
  return instance.exports
}

const evolutionPath = fileURLToPath(new URL('./market-context-evolution.ts', import.meta.url))
const evolution = loadTs(evolutionPath)
const helperPath = fileURLToPath(new URL('./market-context-changes.ts', import.meta.url))
const { summarizeSessionChanges } = loadTs(helperPath, { './market-context-evolution': evolution })

function fixture() {
  return {
    context: { as_of: '2026-10-22' },
    indices: [
      { symbol: 'SPY', date: '2026-10-22', previous_date: '2026-10-21', price: 99, previous_price: 100 },
      { symbol: 'QQQ', date: '2026-10-22', previous_date: '2026-10-21', price: 102, previous_price: 100 },
    ],
    evolution: [
      { date: '2026-10-21', breadth_ratio: 0.5, leader_count: 10 },
      { date: '2026-10-22', breadth_ratio: 0.48, leader_count: 12 },
    ],
  }
}

function vix(overrides = {}) {
  return { vix: { symbol: 'VIX', date: '2026-10-22', previous_date: '2026-10-21', previous_price: 20, price: 21, source: 'Cboe', source_url: 'https://example.test', status: 'current', ...overrides } }
}

test('uses exact reference dates, expresses units, and sorts deterioration first', () => {
  const result = summarizeSessionChanges(fixture(), vix())
  assert.equal(result.length, 6)
  assert.deepEqual(result.map(row => row.id), ['participation', 'spy', 'vix', 'leaders', 'qqq', 'posture'])
  assert.equal(result[0].summary, '-2.00 pp')
  assert.match(result[0].evidence, /2026-10-21.*2026-10-22/)
  assert.equal(result.find(row => row.id === 'leaders').summary, '+2 líderes')
  assert.match(result.find(row => row.id === 'vix').summary, /Volatilidad aumenta.*\+1.00 pts/)
  assert.match(result.find(row => row.id === 'posture').evidence, /servidor no ofrece registros/)
})

test('does not skip missing exact evolution dates or accept a nonmatching benchmark date', () => {
  const data = fixture()
  data.evolution = [data.evolution[0], { date: '2026-10-20', breadth_ratio: 0.1, leader_count: 2 }]
  data.indices[1].previous_date = '2026-10-20'
  const result = summarizeSessionChanges(data, vix())
  assert.equal(result.find(row => row.id === 'participation').direction, 'unavailable')
  assert.match(result.find(row => row.id === 'participation').evidence, /fechas exactas/)
  assert.equal(result.find(row => row.id === 'qqq').direction, 'unavailable')
})

test('rejects invalid SPY reference pairs and surfaces pending, failed, and cached VIX warnings', () => {
  const data = fixture()
  data.indices[0].date = '2026-10-21'
  let result = summarizeSessionChanges(data, undefined, { pending: true })
  assert.match(result.find(row => row.id === 'vix').evidence, /cargando/)
  assert.match(result.find(row => row.id === 'participation').evidence, /fecha SPY igual a la fecha del contexto/)
  result = summarizeSessionChanges(fixture(), undefined, { error: true })
  assert.match(result.find(row => row.id === 'vix').evidence, /Falló la consulta/)
  result = summarizeSessionChanges(fixture(), vix({ refresh_failed: true }), { error: true })
  assert.match(result.find(row => row.id === 'vix').evidence, /caché.*advertencia/)
})

test('classifies rounded zero as unchanged and refuses invalid prices', () => {
  const data = fixture()
  data.indices[0].price = 100.004
  const result = summarizeSessionChanges(data, vix({ price: 20.004 }))
  assert.equal(result.find(row => row.id === 'vix').direction, 'unchanged')
  data.indices[1].previous_price = 0
  assert.equal(summarizeSessionChanges(data, vix()).find(row => row.id === 'qqq').direction, 'unavailable')
})


test('rejects legacy fields, invalid dates, conflicting metrics and mismatched VIX observations', () => {
  for (const previousDate of [undefined, '2026-02-30', '2026-10-22', '2026-10-23']) {
    const data = fixture()
    data.indices[0].previous_date = previousDate
    assert.ok(summarizeSessionChanges(data, vix()).every(row => row.direction === 'unavailable'))
  }
  const data = fixture()
  data.evolution.push({ date: '2026-10-21', breadth_ratio: 0.9, leader_count: 10 })
  const rows = summarizeSessionChanges(data, vix({ previous_date: '2026-10-20' }))
  assert.equal(rows.find(row => row.id === 'participation').direction, 'unavailable')
  assert.equal(rows.find(row => row.id === 'leaders').direction, 'improvement')
  assert.equal(rows.find(row => row.id === 'vix').direction, 'unavailable')
  const decline = summarizeSessionChanges(fixture(), vix({ price: 19 })).find(row => row.id === 'vix')
  assert.equal(decline.direction, 'improvement')
  assert.match(decline.summary, /disminuye.*-1.00 pts/)
  assert.equal(summarizeSessionChanges(fixture(), vix(), { error: true }).find(row => row.id === 'vix').direction, 'unavailable')
})

test('renders dated evidence and missing-reference states in the real component', () => {
  const componentPath = fileURLToPath(new URL('../components/market-context/SessionChanges.tsx', import.meta.url))
  const Component = loadTs(componentPath, {
    '@/lib/market-context-changes': { summarizeSessionChanges },
    '@/lib/market-context-evolution': evolution,
  }).default
  const render = overview => renderToStaticMarkup(React.createElement(Component, {
    overview, volatility: vix(), volatilityPending: false, volatilityError: false,
  }))
  const markup = render(fixture())
  assert.match(markup, /Comparación entre 2026-10-21 y 2026-10-22/)
  assert.match(markup, /50.00%.*48.00%/)
  assert.match(markup, /servidor no ofrece registros/)
  assert.equal((markup.match(/<li /g) ?? []).length, 6)
  const invalid = fixture()
  invalid.context.as_of = '2026-10-32'
  invalid.indices[0].date = invalid.context.as_of
  const missing = render(invalid)
  assert.match(missing, /No hay un par de fechas SPY válido/)
  assert.doesNotMatch(missing, /Comparación entre/)
})

function withRecordedPostures(beforeState = 'NORMAL', afterState = 'DEFENSIVO') {
  const data = fixture()
  data.context.posture = { state: afterState }
  data.posture_history = {
    status: 'available',
    records: [
      { date: '2026-10-21', state: beforeState, instruction: 'Antes', recorded_at: '2026-10-21T15:30:00.123456+00:00' },
      { date: '2026-10-22', state: afterState, instruction: 'Ahora', recorded_at: '2026-10-22T18:45:00Z' },
    ],
  }
  return data
}

test('compares only valid recorded posture pairs, orders restrictiveness, and cites observed UTC times', () => {
  for (const [before, after, summary, direction] of [
    ['NORMAL', 'DEFENSIVO', 'Más restrictiva', 'deterioration'],
    ['DEFENSIVO', 'NORMAL', 'Menos restrictiva', 'improvement'],
    ['SELECTIVO', 'SELECTIVO', 'Sin cambio', 'unchanged'],
  ]) {
    const data = withRecordedPostures(before, after)
    data.context.posture.state = after
    const row = summarizeSessionChanges(data, vix()).find(item => item.id === 'posture')
    assert.equal(row.summary, summary)
    assert.equal(row.direction, direction)
    assert.match(row.evidence, /2026-10-21T15:30:00\.123456\+00:00.*2026-10-22T18:45:00Z/)
    assert.match(row.evidence, /no representan un cierre oficial/)
  }
})

test('fails closed for missing or duplicate dates, invalid states or UTC times, and current posture mismatch', () => {
  const cases = [
    data => { data.posture_history.records.pop() },
    data => { data.posture_history.records.push({ ...data.posture_history.records[0] }) },
    data => { data.posture_history.records[0].state = 'DESCONOCIDO' },
    data => { data.posture_history.records[1].recorded_at = '2026-10-22T18:45:00-03:00' },
    data => { data.context.posture.state = 'NORMAL' },
    data => { data.posture_history.status = 'unavailable' },
  ]
  for (const mutate of cases) {
    const data = withRecordedPostures()
    mutate(data)
    assert.equal(summarizeSessionChanges(data, vix()).find(item => item.id === 'posture').direction, 'unavailable')
  }
})
