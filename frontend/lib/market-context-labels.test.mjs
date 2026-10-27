import assert from 'node:assert/strict'
import test from 'node:test'
import { marketContextLabel } from './market-context-labels.ts'

test('market context labels translate known descriptors by family', () => {
  assert.equal(marketContextLabel('participation', 'NARROWING'), 'Contracción')
  assert.equal(marketContextLabel('health', 'RECOVERING'), 'En recuperación')
  assert.equal(marketContextLabel('leadership', 'THINNING'), 'Adelgazamiento')
  assert.equal(marketContextLabel('density', 'WEAK'), 'Débil')
  assert.equal(marketContextLabel('continuity', 'NOT_PAYING'), 'Desfavorable')
})

test('all known descriptor codes have family-specific Spanish labels', () => {
  const cases = [
    ['participation', 'EXPANDING', 'Expansión'], ['participation', 'STABLE', 'Estable'],
    ['participation', 'NARROWING', 'Contracción'], ['participation', 'COLLAPSING', 'Colapso'],
    ['leadership', 'HEALTHY', 'Saludable'], ['leadership', 'THINNING', 'Adelgazamiento'],
    ['leadership', 'EXHAUSTED', 'Agotamiento'], ['health', 'ROBUST', 'Sólida'],
    ['health', 'RECOVERING', 'En recuperación'], ['health', 'FRAGILE', 'Frágil'],
    ['health', 'DAMAGED', 'Dañada'], ['density', 'STRONG', 'Fuerte'],
    ['density', 'NORMAL', 'Normal'], ['density', 'WEAK', 'Débil'],
    ['continuity', 'PAYING', 'Favorable'], ['continuity', 'MIXED', 'Mixta'],
    ['continuity', 'NOT_PAYING', 'Desfavorable'],
  ]
  for (const [family, code, label] of cases) assert.equal(marketContextLabel(family, code), label)
})

test('missing and unknown values stay neutral and retain their source code', () => {
  assert.equal(marketContextLabel('health', null), 'Sin clasificación')
  assert.equal(marketContextLabel('health', 'NEW_STATE'), 'Sin clasificación (NEW_STATE)')
})
