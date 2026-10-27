import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import Module from 'node:module'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import ts from 'typescript'
import { evolutionSegments, joinEvolutionSeverity, normalizeEvolution } from './market-context-evolution.ts'

const helperPath = fileURLToPath(new URL('./market-context-evolution.ts', import.meta.url))
const helperModule = new Module(helperPath)
helperModule.filename = helperPath
helperModule.paths = Module._nodeModulePaths(dirname(helperPath))
helperModule._compile(ts.transpileModule(readFileSync(helperPath, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText, helperPath)

const componentPath = fileURLToPath(new URL('../components/market-context/MarketEvolution.tsx', import.meta.url))
const componentModule = new Module(componentPath)
componentModule.filename = componentPath
componentModule.paths = Module._nodeModulePaths(dirname(componentPath))
const originalLoad = Module._load
Module._load = function (request, parent, isMain) {
  if (request === '@/lib/market-context-evolution') return helperModule.exports
  return originalLoad.call(this, request, parent, isMain)
}
try {
  componentModule._compile(ts.transpileModule(readFileSync(componentPath, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2020 },
  }).outputText, componentPath)
} finally {
  Module._load = originalLoad
}
const MarketEvolution = componentModule.exports.default

function renderEvolution(data) {
  return renderToStaticMarkup(React.createElement(MarketEvolution, { data }))
}

test('normalization keeps missing sessions, rejects malformed and future dates, and caps at twenty', () => {
  const dates = Array.from({ length: 22 }, (_, index) => `2026-10-${String(index + 1).padStart(2, '0')}`)
  const rows = dates.map(date => ({ date, breadth_ratio: 0, leader_count: 0 }))
  rows.push({ date: '2026-10-23', breadth_ratio: 1, leader_count: 3 })
  rows.push({ date: '2026-02-30', breadth_ratio: 1, leader_count: 3 })
  rows[3].breadth_ratio = null
  const result = normalizeEvolution(rows, '2026-10-22')
  assert.equal(result.length, 20)
  assert.equal(result[0].date, '2026-10-03')
  assert.deepEqual(result[0], { date: '2026-10-03', breadthRatio: 0, leaderCount: 0 })
  assert.equal(result.at(-1).date, '2026-10-22')
  assert.equal(result.find(point => point.date === '2026-10-04').breadthRatio, null)
})

test('identical duplicates collapse and conflicting metric duplicates become missing', () => {
  const result = normalizeEvolution([
    { date: '2026-10-20', breadth_ratio: 0.5, leader_count: 3 },
    { date: '2026-10-20', breadth_ratio: 0.5, leader_count: 3 },
    { date: '2026-10-19', breadth_ratio: 0.2, leader_count: 2 },
    { date: '2026-10-19', breadth_ratio: 0.3, leader_count: 2 },
  ], '2026-10-20')
  assert.deepEqual(result, [
    { date: '2026-10-19', breadthRatio: null, leaderCount: 2 },
    { date: '2026-10-20', breadthRatio: 0.5, leaderCount: 3 },
  ])
})

test('invalid metric values remain missing instead of becoming zero', () => {
  const result = normalizeEvolution([
    { date: '2026-10-20', breadth_ratio: 1.1, leader_count: -2 },
    { date: '2026-10-19', breadth_ratio: 0, leader_count: 0 },
  ], '2026-10-20')
  assert.deepEqual(result, [
    { date: '2026-10-19', breadthRatio: 0, leaderCount: 0 },
    { date: '2026-10-20', breadthRatio: null, leaderCount: null },
  ])
})

test('series segments break on gaps without interpolating', () => {
  const points = normalizeEvolution([
    { date: '2026-10-18', breadth_ratio: 0.2, leader_count: 1 },
    { date: '2026-10-19', breadth_ratio: null, leader_count: 2 },
    { date: '2026-10-20', breadth_ratio: 0.8, leader_count: 3 },
  ], '2026-10-20')
  assert.deepEqual(evolutionSegments(points, 'breadthRatio').map(segment => segment.map(point => point.date)), [
    ['2026-10-18'], ['2026-10-20'],
  ])
  assert.deepEqual(evolutionSegments(points, 'leaderCount').map(segment => segment.map(point => point.date)), [
    ['2026-10-18', '2026-10-19', '2026-10-20'],
  ])
})

test('severity joins by exact date and distinguishes absent from unclassified dates', () => {
  const points = normalizeEvolution([
    { date: '2026-10-18', breadth_ratio: 0.2, leader_count: 1 },
    { date: '2026-10-19', breadth_ratio: 0.3, leader_count: 2 },
    { date: '2026-10-20', breadth_ratio: 0.4, leader_count: 3 },
  ], '2026-10-20')
  const result = joinEvolutionSeverity(points, [
    { date: '2026-10-19', severity: 'mild' },
    { date: '2026-10-20', severity: 'unexpected' },
    { date: '2026-10-21', severity: 'clean' },
  ], '2026-10-20')
  assert.deepEqual(result.map(({ severity, hasHealthSession }) => [severity, hasHealthSession]), [
    [null, false], ['mild', true], [null, true],
  ])
})

test('conflicting dated severity is unknown', () => {
  const points = normalizeEvolution([{ date: '2026-10-20', breadth_ratio: 0, leader_count: 0 }], '2026-10-20')
  const result = joinEvolutionSeverity(points, [
    { date: '2026-10-20', severity: 'clean' },
    { date: '2026-10-20', severity: 'severe' },
  ], '2026-10-20')
  assert.equal(result[0].severity, null)
  assert.equal(result[0].hasHealthSession, true)
})

test('legacy or empty evolution renders unavailable without substituting history', () => {
  const data = { context: { as_of: '2026-10-20', health: { series: [] } } }
  const html = renderEvolution(data)
  assert.match(html, /Evolución no disponible/)
  assert.doesNotMatch(html, /Historial de participación|Historial de liderazgo/)
})

test('static charts preserve gaps, units, coverage and unknown versus classified clean severity', () => {
  const data = {
    context: {
      as_of: '2026-10-20',
      health: { series: [
        { date: '2026-10-18', severity: 'clean' },
        { date: '2026-10-20', severity: null },
      ] },
    },
    evolution: [
      { date: '2026-10-18', breadth_ratio: 0.2, leader_count: 1 },
      { date: '2026-10-19', breadth_ratio: null, leader_count: null },
      { date: '2026-10-20', breadth_ratio: 0.5, leader_count: 3 },
    ],
  }
  const html = renderEvolution(data)
  assert.match(html, /Sobre EMA21 \(%\)/)
  assert.match(html, /Cantidad de líderes/)
  assert.match(html, /2\/3/)
  assert.match(html, /Daño · 1\/3 clasificados/)
  assert.match(html, /Sin datos/)
  assert.doesNotMatch(html, /Densidad|densidad/)
  assert.equal((html.match(/<path /g) ?? []).length, 4, 'each sparse line is split at the missing session')

  const clean = renderEvolution({
    context: { as_of: '2026-10-18', health: { series: [{ date: '2026-10-18', severity: 'clean' }] } },
    evolution: [{ date: '2026-10-18', breadth_ratio: 0, leader_count: 0 }],
  })
  assert.match(clean, /Sin daño clasificado/)
})
