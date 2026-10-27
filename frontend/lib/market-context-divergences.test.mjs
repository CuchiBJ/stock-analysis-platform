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
      compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2020 },
    }).outputText, path)
  } finally {
    Module._load = originalLoad
  }
  return instance.exports
}

const contextPath = fileURLToPath(new URL('./market-context.ts', import.meta.url))
const context = loadTs(contextPath)
const changesPath = fileURLToPath(new URL('./market-context-changes.ts', import.meta.url))
const changes = loadTs(changesPath, { './market-context-evolution': loadTs(fileURLToPath(new URL('./market-context-evolution.ts', import.meta.url))) })
const helperPath = fileURLToPath(new URL('./market-context-divergences.ts', import.meta.url))
const { summarizeMarketDivergences } = loadTs(helperPath, { './market-context-changes': changes, './market-context': context })
const componentPath = fileURLToPath(new URL('../components/market-context/MarketDivergences.tsx', import.meta.url))
const Component = loadTs(componentPath, { '@/lib/market-context-divergences': { summarizeMarketDivergences } }).default

function fixture() {
  return {
    context: { as_of: '2026-10-22' },
    indices: [
      { symbol: 'SPY', date: '2026-10-22', previous_date: '2026-10-21', price: 101, previous_price: 100 },
      { symbol: 'QQQ', date: '2026-10-22', previous_date: '2026-10-21', price: 101, previous_price: 100 },
    ],
    evolution: [
      { date: '2026-10-21', breadth_ratio: 0.5, leader_count: 10 },
      { date: '2026-10-22', breadth_ratio: 0.4, leader_count: 9 },
    ],
  }
}

function render(overview) {
  return renderToStaticMarkup(React.createElement(Component, { overview }))
}

function setDirection(data, id, direction) {
  if (id === 'spy' || id === 'qqq') {
    const index = data.indices.find(item => item.symbol === id.toUpperCase())
    index.price = direction === 'up' ? 101 : direction === 'down' ? 99 : 100
    return
  }
  const before = data.evolution[0]
  const after = data.evolution[1]
  if (id === 'participation') after.breadth_ratio = direction === 'up' ? before.breadth_ratio + 0.1 : direction === 'down' ? before.breadth_ratio - 0.1 : before.breadth_ratio
  else after.leader_count = direction === 'up' ? before.leader_count + 1 : direction === 'down' ? before.leader_count - 1 : before.leader_count
}

test('evaluates all nine rounded index/internal direction pairs', () => {
  for (const indexDirection of ['up', 'down', 'flat']) {
    for (const internalDirection of ['up', 'down', 'flat']) {
      const data = fixture()
      setDirection(data, 'spy', indexDirection)
      setDirection(data, 'participation', internalDirection)
      const finding = summarizeMarketDivergences(data).findings.find(item => item.id === 'spy-participation')
      if (indexDirection === 'up' && internalDirection === 'down') assert.equal(finding?.direction, 'deterioration')
      else if (indexDirection === 'down' && internalDirection === 'up') assert.equal(finding?.direction, 'improvement')
      else assert.equal(finding, undefined, `${indexDirection}/${internalDirection} should not diverge`)
    }
  }
})

test('findings include both labeled deltas and dated evidence with deterioration first', () => {
  const data = fixture()
  data.indices[1].price = 99
  data.evolution[1].leader_count = 12
  const result = summarizeMarketDivergences(data)
  assert.deepEqual(result.findings.map(item => [item.id, item.direction]), [
    ['spy-participation', 'deterioration'],
    ['qqq-leaders', 'improvement'],
  ])
  assert.match(result.findings[0].narrative, /SPY avanza mientras la participación sobre EMA21 retrocede/)
  assert.match(result.findings[0].indexEvidence, /SPY: \+1\.00%.*2026-10-21.*2026-10-22/)
  assert.match(result.findings[0].internalEvidence, /Participación sobre EMA21: -10\.00 pp.*2026-10-21.*2026-10-22/)
  assert.match(result.findings[1].narrative, /aumenta la cantidad de líderes/)
  assert.equal(result.total, 4)
})

test('renders deterioration evidence and the partial-coverage empty state with reasons', () => {
  const data = fixture()
  data.indices[1].previous_price = null
  data.evolution[1].leader_count = null
  const html = render(data)
  assert.match(html, /Divergencias de la sesión/)
  assert.match(html, /SPY avanza mientras la participación sobre EMA21 retrocede/)
  assert.match(html, /SPY: \+1\.00%/)
  assert.match(html, /1 de 4 comparaciones evaluables/)
  assert.match(html, /Comparaciones sin evidencia suficiente/)
  assert.match(html, /Falta un cierre positivo válido/)
})

test('renders a partial no-finding state without claiming global absence', () => {
  const data = fixture()
  data.indices[1].previous_price = null
  data.evolution[1].leader_count = null
  data.evolution[1].breadth_ratio = 0.6
  const html = render(data)
  assert.match(html, /No se observan movimientos opuestos entre 1 comparación evaluable/)
  assert.doesNotMatch(html, /No se observan movimientos opuestos en estas cuatro/)
})

test('distinguishes full no-finding coverage from zero coverage', () => {
  const complete = fixture()
  complete.indices[1].price = 102
  complete.evolution[1].breadth_ratio = 0.6
  complete.evolution[1].leader_count = 11
  const fullHtml = render(complete)
  assert.match(fullHtml, /4 de 4 comparaciones evaluables/)
  assert.match(fullHtml, /No se observan movimientos opuestos en estas cuatro comparaciones/)

  const missing = fixture()
  missing.indices[0].date = '2026-10-21'
  const zeroHtml = render(missing)
  assert.match(zeroHtml, /0 de 4 comparaciones evaluables/)
  assert.match(zeroHtml, /Evidencia comparable insuficiente/)
  assert.doesNotMatch(zeroHtml, /No se observan movimientos opuestos/)
})

test('legacy dates, mismatched benchmark dates, and conflicting evolution values stay unevaluable', () => {
  for (const mutate of [
    data => { delete data.indices[0].previous_date },
    data => { data.indices[1].previous_date = '2026-10-20' },
    data => { data.evolution.push({ date: '2026-10-22', breadth_ratio: 0.7, leader_count: 9 }) },
  ]) {
    const data = fixture()
    mutate(data)
    const result = summarizeMarketDivergences(data)
    if (!data.indices[0].previous_date) assert.equal(result.evaluatedCount, 0)
    else if (data.indices[1].previous_date !== data.indices[0].previous_date) assert.equal(result.evaluatedCount, 2)
    else {
      assert.equal(result.evaluatedCount, 2)
      assert.deepEqual(result.unavailable.map(item => item.id), ['spy-participation', 'qqq-participation'])
    }
  }
})
