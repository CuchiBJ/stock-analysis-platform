import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import test from 'node:test'
import Module from 'node:module'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import ts from 'typescript'

const helperPath = fileURLToPath(new URL('./market-context-explanation.ts', import.meta.url))
const helperModule = new Module(helperPath)
helperModule.filename = helperPath
helperModule.paths = Module._nodeModulePaths(dirname(helperPath))
helperModule._compile(ts.transpileModule(readFileSync(helperPath, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText, helperPath)
const { explainMarketPosture } = helperModule.exports

const componentPath = fileURLToPath(new URL('../components/market-context/PostureExplanation.tsx', import.meta.url))
const componentModule = new Module(componentPath)
componentModule.filename = componentPath
componentModule.paths = Module._nodeModulePaths(dirname(componentPath))
const originalLoad = Module._load
Module._load = function (request, parent, isMain) {
  if (request === '@/lib/market-context-explanation') return helperModule.exports
  return originalLoad.call(this, request, parent, isMain)
}
try {
  componentModule._compile(ts.transpileModule(readFileSync(componentPath, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2020 },
  }).outputText, componentPath)
} finally {
  Module._load = originalLoad
}
const PostureExplanation = componentModule.exports.default

function context(overrides = {}) {
  return {
    as_of: '2026-10-20', universe_size: 500, engines_pending: [],
    participation: { descriptor: 'EXPANDING', delta_5d: 5.25, metrics: { breadth_above_ema21: 0.5, breadth_momentum_5d: 5.25 } },
    leadership: { descriptor: 'EXPANDING', delta_5d: 31.5, metrics: { leader_density: 0.12 } },
    posture: {
      state: 'FUERA', instruction: 'Sin compras nuevas — deterioro pesado y activo.',
      reasons: ['memoria dañada con deterioro activo hoy'], unlock: 'unlock original',
      policy: {
        thresholds: { defensive_breadth_entry: 0.4, defensive_leader_density_entry: 0.05 },
        inputs: { breadth_ratio: 0.38, leader_density: 0.04, participation: 'EXPANDING', leadership: 'EXPANDING' },
        base_state: 'DEFENSIVO', health_ceiling: 'DEFENSIVO', final_state: 'FUERA',
        exceptional_retained: false, normal_confirmation_streak: 0,
      },
    },
    health: {
      state: 'DAMAGED', window_days: 20, damaged_days: 8, repair_streak: 1,
      repair_clean_days: 1, repair_window_days: 7, repair_required_clean_days: 5,
      recent_severe_days: 2, severe_lookback_days: 3,
      recovery_confirmation_streak: 0, recovery_confirmation_required_days: 3,
      exceptional_recovery_session: false,
      series: [{ date: '2026-10-19', severity: 'severe' }, { date: '2026-10-20', severity: 'clean' }],
    },
    follow_through: { descriptor: 'UNKNOWN', delivery_rate: null, baseline_rate: null },
    ...overrides,
  }
}

function render(ctx) {
  return renderToStaticMarkup(React.createElement(PostureExplanation, { context: ctx }))
}

function visibleHtml(ctx) {
  return render(ctx).split('<details')[0]
}

test('pure explanation model preserves the input and marks missing recovery evidence unknown', () => {
  const ctx = context()
  delete ctx.health.repair_clean_days
  delete ctx.posture.policy.inputs.breadth_ratio
  const before = structuredClone(ctx)
  const model = explainMarketPosture(ctx)
  assert.equal(model.repairGates[1].status, 'unknown')
  assert.match(model.rows[0].value, /Amplitud Sin datos/)
  assert.deepEqual(ctx, before)
})

test('shows authoritative FUERA posture, level, direction, memory and same-session clean evidence', () => {
  const ctx = context()
  const before = structuredClone(ctx)
  const html = render(ctx)
  const visible = html.split('<details')[0]
  assert.match(visible, /FUERA/)
  assert.match(visible, /Los niveles siguen defensivos y la memoria de daño mantiene la postura en FUERA/)
  assert.match(visible, /mejoran recientemente/)
  assert.match(html, /<details[^>]*><summary[^>]*>Evidencia y condiciones de reparación/)
  assert.match(html, /Amplitud 38\.0% · piso defensivo 40\.0%/)
  assert.match(html, /Participación Expansión \(\+5\.25 pp \/ 5 ruedas\).*liderazgo Expansión \(\+31\.50 % relativo \/ 5 ruedas\)/)
  assert.match(html, /Salud DAMAGED · 8\/20 ruedas dañadas/)
  assert.match(visible, /Rueda actual sin daño clasificado/)
  assert.doesNotMatch(visible, /deterioro pesado y activo/)
  assert.match(html, /Respuesta original del sistema · auditoría/)
  assert.match(html, /deterioro pesado y activo/)
  assert.deepEqual(ctx, before)
})

test('never borrows yesterday severity when the as-of session is missing', () => {
  const ctx = context()
  ctx.health.series = [{ date: '2026-10-19', severity: 'severe' }]
  assert.match(visibleHtml(ctx), /Daño de la rueda actual: sin datos/)
  assert.doesNotMatch(visibleHtml(ctx), /Daño severo en la rueda actual/)
})

test('shows repair evidence with actual counts and keeps incomplete windows pending', () => {
  const pending = render(context())
  assert.match(pending, /Ventana completa de reparación.*Cumplida/s)
  assert.match(pending, /Limpias: 1 · requeridas: 5/)
  assert.match(pending, /2 severas · ventana 3 de 3 ruedas/)
  assert.match(pending, /Acceso anticipado a SELECTIVO/)

  const incomplete = context()
  incomplete.health.repair_window_days = 5
  incomplete.health.repair_clean_days = 5
  incomplete.health.recent_severe_days = 0
  incomplete.health.severe_lookback_days = 3
  incomplete.health.recovery_confirmation_streak = 3
  incomplete.posture.policy.base_state = 'SELECTIVO'
  const html = render(incomplete)
  assert.match(html, /Ventana completa de reparación.*Pendiente/s)
  assert.match(html, /5 de 7 ruedas observadas/)
})

test('protective gates stay pending while exceptional evidence satisfies the OR alternative', () => {
  const ctx = context()
  ctx.health.recent_severe_days = 1
  ctx.health.recovery_confirmation_streak = undefined
  ctx.health.exceptional_recovery_session = true
  ctx.posture.policy.base_state = 'DEFENSIVO'
  const html = render(ctx)
  assert.match(html, /Niveles base fuera de DEFENSIVO\/FUERA.*Pendiente/s)
  assert.match(html, /Cero severos recientes.*Pendiente/s)
  assert.match(html, /Alternativa de confirmación o excepción.*Cumplida/s)
})

test('shows received defensive exit bands only while defensive hysteresis is active', () => {
  const ctx = context()
  ctx.posture.policy.defensive_active = true
  ctx.posture.policy.thresholds.defensive_breadth_exit = 0.43
  ctx.posture.policy.thresholds.defensive_leader_density_exit = 0.06
  const html = render(ctx)
  assert.match(html, /salida defensiva: amplitud 43\.0% \/ densidad 6\.0%/)

  delete ctx.posture.policy.thresholds.defensive_breadth_exit
  assert.match(render(ctx), /salida defensiva: amplitud Sin datos \/ densidad 6\.0%/)
})

test('unknown base state cannot satisfy early recovery protection or alternative evidence', () => {
  const ctx = context()
  ctx.posture.policy.base_state = 'UNKNOWN'
  ctx.health.exceptional_recovery_session = true
  const html = render(ctx)
  assert.match(html, /Niveles base fuera de DEFENSIVO\/FUERA.*Sin datos/s)
  assert.match(html, /Alternativa de confirmación o excepción.*Cumplida/s)
})

test('retained exception is an alternative while independent protections remain visible', () => {
  const ctx = context()
  ctx.posture.policy.exceptional_retained = true
  ctx.health.exceptional_recovery_session = false
  ctx.health.recovery_confirmation_streak = 0
  ctx.health.recent_severe_days = 1
  const model = explainMarketPosture(ctx)
  assert.equal(model.earlyGates[2].status, 'satisfied')
  assert.equal(model.earlyGates[0].status, 'pending')
  assert.equal(model.earlyGates[1].status, 'pending')
})

test('false plus missing early recovery alternatives remain unknown', () => {
  const ctx = context()
  ctx.posture.policy.exceptional_retained = false
  ctx.health.exceptional_recovery_session = false
  ctx.health.recovery_confirmation_streak = undefined
  const model = explainMarketPosture(ctx)
  assert.equal(model.earlyGates[2].status, 'unknown')
})

test('follow-through NOT_PAYING is described as a ceiling, never as the sole cause of FUERA', () => {
  const ctx = context({ follow_through: { descriptor: 'NOT_PAYING', delivery_rate: 0.25, baseline_rate: 0.5 } })
  const html = visibleHtml(ctx)
  assert.match(html, /Continuidad insuficiente: limita la postura como máximo a SELECTIVO · entrega 25\.0% vs base 50\.0%/)
  assert.doesNotMatch(html, /NOT_PAYING.*causa de FUERA/)
})

test('repair checklist is omitted for ROBUST and RECOVERING, and partial data stays unknown', () => {
  for (const state of ['ROBUST', 'RECOVERING']) {
    const ctx = context()
    ctx.health.state = state
    const html = render(ctx)
    assert.doesNotMatch(html, /Reparación de salud/)
    assert.doesNotMatch(html, /Acceso anticipado a SELECTIVO/)
  }
  const partial = context()
  delete partial.posture.policy
  partial.health = undefined
  const html = render(partial)
  assert.match(html, /evidencia de política o salud está incompleta/)
  assert.match(html, /Amplitud Sin datos/)
  assert.match(html, /Daño de la rueda actual: sin datos/)
})

test('ContextEvidence delegates only the posture branch to the explanation component', () => {
  const source = readFileSync(new URL('../components/market-context/ContextEvidence.tsx', import.meta.url), 'utf8')
  assert.match(source, /if \(section === 'posture'\) return <PostureExplanation context=\{ctx\} \/>/)
})
