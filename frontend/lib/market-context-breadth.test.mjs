import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import test from 'node:test'
import Module from 'node:module'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import ts from 'typescript'

const drawerPath = fileURLToPath(new URL('../components/dashboard/MarketContextDrawer.tsx', import.meta.url))
const mockBar = {
  breadthLevelColor: () => '', densityLevelColor: () => '', followThroughColor: () => '',
  healthStateColor: () => '', postureColor: () => '', DamageStrip: () => null,
}
const drawerModule = new Module(drawerPath)
drawerModule.filename = drawerPath
drawerModule.paths = Module._nodeModulePaths(dirname(drawerPath))
const originalLoad = Module._load
Module._load = function (request, parent, isMain) {
  if (request === './MarketContextBar') return mockBar
  return originalLoad.call(this, request, parent, isMain)
}
try {
  const source = readFileSync(drawerPath, 'utf8')
  const output = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2020 },
  }).outputText
  drawerModule._compile(output, drawerPath)
} finally {
  Module._load = originalLoad
}

const MarketContextDrawer = drawerModule.exports.default

function context() {
  return {
    as_of: '2026-10-20', universe_size: 500, engines_pending: [],
    participation: {
      descriptor: 'STABLE', delta_5d: 0, delta_sample_size_20d: 20,
      metrics: {
        breadth_above_ema21: 0.5, breadth_momentum_5d: 0, highs_lows_ratio: 1.25,
        breadth_above_ema50: 0.5, breadth_above_ema200: 0.5, breadth_momentum_20d: 0,
        near_highs_count: 10, near_lows_count: 8, participation_persistence: 0.5,
      },
      breadth_comparisons: {
        date: '2026-10-20',
        new_session_highs_vs_lows: { up_count: 12, down_count: 3, eligible_symbols: 450, excluded_symbols: 50, up_ratio: 0.8 },
        up_from_open_vs_down: { up_count: 300, down_count: 100, eligible_symbols: 480, excluded_symbols: 20, up_ratio: 0.75 },
        up_4pct_vs_down_4pct: { up_count: 0, down_count: 0, eligible_symbols: 430, excluded_symbols: 70, up_ratio: null },
      },
    },
    leadership: {
      descriptor: 'HEALTHY', delta_5d: 0,
      metrics: {
        leader_count: 20, leader_density_level: 'NORMAL', leader_density_percentile: null,
        leader_density_delta_20d: 0, leader_pullback_quality_avg: 50, leader_climactic_count: 0,
        leader_density: 0.04, leader_count_delta_5d: 0, leader_count_delta_20d: 0,
        leader_density_delta_5d: 0, leader_density_sample_size: 20, leader_tightness_avg: 0,
        leader_vol_contraction_avg: 0, leader_rs_persistence_10d: 0,
        leader_extension_count: 0, leadership_turnover_5d: 0,
      },
    },
  }
}

function render(ctx = context()) {
  return renderToStaticMarkup(React.createElement(MarketContextDrawer, { ctx, onClose: () => {} }))
}

test('renders OHLC breadth counts, date, coverage and zero-event state', () => {
  const html = render()
  assert.match(html, /Nuevos máximos vs nuevos mínimos \(sesión anterior\)/)
  assert.match(html, /Suben desde la apertura vs bajan/)
  assert.match(html, /Suben ≥4% vs bajan ≥4%/)
  assert.match(html, /2026-10-20/)
  assert.match(html, /450 elegibles · 50 excluidas/)
  assert.match(html, /80%/)
  assert.match(html, /Sin eventos/)
  assert.match(html, /Ratio proximidad \/ distancia a máximos/)
  assert.match(html, /no cuenta nuevos extremos/)
})

test('renders missing coverage as no data and keeps legacy responses working', () => {
  const noCoverage = context()
  noCoverage.participation.breadth_comparisons.new_session_highs_vs_lows = {
    up_count: 0, down_count: 0, eligible_symbols: 0, excluded_symbols: 500, up_ratio: null,
  }
  assert.match(render(noCoverage), /Sin datos/)

  const legacy = context()
  delete legacy.participation.breadth_comparisons
  const legacyHtml = render(legacy)
  assert.match(legacyHtml, /Ratio proximidad \/ distancia a máximos/)
  assert.doesNotMatch(legacyHtml, /Suben desde la apertura vs bajan/)
})


test('does not relabel annual payloads as previous-session extremes', () => {
  const legacy = context()
  const comparisons = legacy.participation.breadth_comparisons
  comparisons.new_52w_highs_vs_lows = comparisons.new_session_highs_vs_lows
  delete comparisons.new_session_highs_vs_lows
  const html = render(legacy)
  assert.doesNotMatch(html, /Nuevos máximos vs nuevos mínimos \(sesión anterior\)/)
  assert.match(html, /Suben desde la apertura vs bajan/)
})
