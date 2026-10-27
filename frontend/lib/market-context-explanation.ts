import type { MarketContextData, HealthData, PostureData } from '@/components/dashboard/MarketContextBar'

export type EvidenceStatus = 'satisfied' | 'pending' | 'unknown'

export interface PostureEvidenceRow {
  label: string
  value: string
}

export interface PostureGate {
  label: string
  status: EvidenceStatus
  evidence: string
}

export interface PostureExplanationModel {
  summary: string[]
  rows: PostureEvidenceRow[]
  currentDamage: string
  continuity: string | null
  repairGates: PostureGate[]
  earlyGates: PostureGate[]
  audit: {
    state: string
    instruction: string
    reasons: string[]
    unlock: string | null
    policy?: PostureData['policy']
  } | null
}

// These are policy window lengths defined by market_health.py. The API reports
// the observed window lengths; a shorter observed sample cannot satisfy them.
const REPAIR_WINDOW_DAYS = 7
const SEVERE_LOOKBACK_DAYS = 3
const UNKNOWN = 'Sin datos'

function finite(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

function count(value: unknown): string {
  return finite(value) ? String(value) : UNKNOWN
}

function ratio(value: unknown): string {
  return finite(value) ? `${(value * 100).toFixed(1)}%` : UNKNOWN
}

function delta(value: unknown, unit: string): string {
  return finite(value) ? `${value > 0 ? '+' : ''}${value.toFixed(2)} ${unit}` : UNKNOWN
}

function descriptor(value: unknown): string {
  const labels: Record<string, string> = {
    EXPANDING: 'Expansión', STABLE: 'Estable', NARROWING: 'Contracción', COLLAPSING: 'Colapso', UNKNOWN: 'Sin descriptor',
    HEALTHY: 'Saludable', THINNING: 'Adelgazamiento', EXHAUSTED: 'Agotamiento',
  }
  return typeof value === 'string' ? labels[value] ?? 'Sin descriptor' : 'Sin descriptor'
}

function statusFor(condition: boolean | null): EvidenceStatus {
  return condition === true ? 'satisfied' : condition === false ? 'pending' : 'unknown'
}

function gate(label: string, condition: boolean | null, evidence: string): PostureGate {
  return { label, status: statusFor(condition), evidence }
}

function summaryFor(ctx: MarketContextData, posture: PostureData | null | undefined): string[] {
  if (!posture) return ['La postura no está disponible en esta respuesta.']
  const policy = posture.policy
  const base = policy?.base_state
  const health = ctx.health?.state
  const p = ctx.participation.descriptor
  const l = ctx.leadership.descriptor
  const statements: string[] = []

  if (posture.state === 'FUERA' && base === 'DEFENSIVO' && health === 'DAMAGED') {
    statements.push('Los niveles siguen defensivos y la memoria de daño mantiene la postura en FUERA.')
    if (p === 'EXPANDING' && l === 'EXPANDING') {
      statements.push('La participación y el liderazgo mejoran recientemente; esa expansión no equivale a reparación de salud.')
    }
  } else if (base && policy?.health_ceiling) {
    statements.push(`Nivel base ${base}; techo por salud ${policy.health_ceiling}; postura vigente ${posture.state}.`)
  } else {
    statements.push(`Postura vigente ${posture.state}; la evidencia de política o salud está incompleta.`)
  }

  if (ctx.health?.state === 'FRAGILE') {
    statements.push('La salud frágil mantiene condiciones de reparación visibles.')
  } else if (!ctx.health || !policy || ctx.health.state === 'UNKNOWN') {
    statements.push('La evidencia parcial limita la explicación de niveles y memoria.')
  }
  return statements.slice(0, 3)
}

function currentDamage(health: HealthData | null | undefined, asOf: string): string {
  const today = health?.series?.find(point => point.date === asOf)
  if (!today || !today.severity) return 'Daño de la rueda actual: sin datos'
  if (today.severity === 'clean') return 'Rueda actual sin daño clasificado'
  if (today.severity === 'mild') return 'Retroceso leve en la rueda actual'
  if (today.severity === 'severe') return 'Daño severo en la rueda actual'
  return 'Daño de la rueda actual: sin datos'
}

function repairGates(health: HealthData | null | undefined): PostureGate[] {
  if (!health) return [gate('Datos de reparación disponibles', null, 'Salud sin datos')]
  const observedWindow = health.repair_window_days
  const cleanDays = health.repair_clean_days
  const requiredClean = health.repair_required_clean_days
  const severeDays = health.recent_severe_days
  const severeWindow = health.severe_lookback_days
  const fullWindow = finite(observedWindow) ? observedWindow === REPAIR_WINDOW_DAYS : null
  const cleanReady = finite(cleanDays) && finite(requiredClean) ? cleanDays >= requiredClean : null
  const noRecentSevere = finite(severeDays) && finite(severeWindow)
    ? severeDays === 0 && severeWindow >= SEVERE_LOOKBACK_DAYS
    : null
  return [
    gate('Ventana completa de reparación', fullWindow, `${count(observedWindow)} de ${REPAIR_WINDOW_DAYS} ruedas observadas`),
    gate('Ruedas limpias requeridas', cleanReady, `Limpias: ${count(cleanDays)} · requeridas: ${count(requiredClean)}`),
    gate('Sin daño severo reciente', noRecentSevere, `${count(severeDays)} severas · ventana ${count(severeWindow)} de ${SEVERE_LOOKBACK_DAYS} ruedas`),
  ]
}

function earlyRecoveryGates(health: HealthData | null | undefined, posture: PostureData): PostureGate[] {
  const policy = posture.policy
  const base = policy?.base_state
  const validBaseStates = ['FUERA', 'DEFENSIVO', 'SELECTIVO', 'NORMAL', 'AGRESIVO']
  const baseKnown = typeof base === 'string' && validBaseStates.includes(base)
    ? ['SELECTIVO', 'NORMAL', 'AGRESIVO'].includes(base)
    : null
  const recentSevere = health?.recent_severe_days
  const severeWindow = health?.severe_lookback_days
  const noRecentSevere = finite(recentSevere) && finite(severeWindow)
    ? recentSevere === 0 && severeWindow >= SEVERE_LOOKBACK_DAYS
    : null
  const streak = health?.recovery_confirmation_streak
  const required = health?.recovery_confirmation_required_days
  const streakMet = finite(streak) && finite(required) ? streak >= required : null
  const exceptional = health?.exceptional_recovery_session
  const retained = policy?.exceptional_retained
  const alternatives = [streakMet, exceptional === true ? true : exceptional === false ? false : null, retained === true ? true : retained === false ? false : null]
  const alternative: boolean | null = alternatives.includes(true) ? true : alternatives.every(value => value === false) ? false : null
  const alternativeEvidence = [
    `confirmaciones ${count(streak)}/${count(required)}`,
    `rueda excepcional ${exceptional == null ? UNKNOWN : exceptional ? 'sí' : 'no'}`,
    `excepción retenida ${retained == null ? UNKNOWN : retained ? 'sí' : 'no'}`,
  ].join(' · ')
  return [
    gate('Niveles base fuera de DEFENSIVO/FUERA', baseKnown, typeof base === 'string' ? `Base ${base}` : `Base ${UNKNOWN}`),
    gate('Cero severos recientes', noRecentSevere, `${count(recentSevere)} severas · ventana ${count(severeWindow)} de ${SEVERE_LOOKBACK_DAYS} ruedas`),
    gate('Alternativa de confirmación o excepción', alternative, alternativeEvidence),
  ]
}

export function explainMarketPosture(ctx: MarketContextData): PostureExplanationModel {
  const posture = ctx.posture
  const health = ctx.health
  const policy = posture?.policy
  const inputs = policy?.inputs
  const thresholds = policy?.thresholds
  const base = policy?.base_state
  const defensiveBands = policy?.defensive_active === true
    ? ` · salida defensiva: amplitud ${finite(thresholds?.defensive_breadth_exit) ? ratio(thresholds.defensive_breadth_exit) : UNKNOWN} / densidad ${finite(thresholds?.defensive_leader_density_exit) ? ratio(thresholds.defensive_leader_density_exit) : UNKNOWN}`
    : ''
  const levels = `Amplitud ${ratio(inputs?.breadth_ratio)}${finite(thresholds?.defensive_breadth_entry) ? ` · piso defensivo ${ratio(thresholds.defensive_breadth_entry)}` : ` · piso ${UNKNOWN}`} / densidad de líderes ${ratio(inputs?.leader_density)}${finite(thresholds?.defensive_leader_density_entry) ? ` · piso defensivo ${ratio(thresholds.defensive_leader_density_entry)}` : ` · piso ${UNKNOWN}`}${defensiveBands}`
  const direction = `Participación ${descriptor(ctx.participation?.descriptor)} (${delta(ctx.participation?.delta_5d, 'pp')} / 5 ruedas) / liderazgo ${descriptor(ctx.leadership?.descriptor)} (${delta(ctx.leadership?.delta_5d, '% relativo / 5 ruedas')})`
  const memory = `Salud ${health?.state ?? UNKNOWN} · ${count(health?.damaged_days)}/${count(health?.window_days)} ruedas dañadas`
  const rows: PostureEvidenceRow[] = [
    { label: `Nivel${base ? ` · base ${base}` : ''}`, value: levels },
    { label: 'Dirección', value: direction },
    { label: 'Memoria', value: memory },
  ]
  const follow = ctx.follow_through
  const continuity = follow?.descriptor === 'NOT_PAYING'
    ? `Continuidad insuficiente: limita la postura como máximo a SELECTIVO${finite(follow.delivery_rate) ? ` · entrega ${ratio(follow.delivery_rate)}` : ''}${finite(follow.baseline_rate) ? ` vs base ${ratio(follow.baseline_rate)}` : ''}.`
    : follow
      ? `Continuidad ${follow.descriptor === 'UNKNOWN' ? UNKNOWN : follow.descriptor}${finite(follow.delivery_rate) ? ` · entrega ${ratio(follow.delivery_rate)}` : ''}${finite(follow.baseline_rate) ? ` vs base ${ratio(follow.baseline_rate)}` : ''}.`
      : null
  const state = health?.state
  const isDamagedOrFragile = state === 'DAMAGED' || state === 'FRAGILE'
  const isDamaged = state === 'DAMAGED'
  return {
    summary: summaryFor(ctx, posture),
    rows,
    currentDamage: currentDamage(health, ctx.as_of),
    continuity,
    repairGates: isDamagedOrFragile ? repairGates(health) : [],
    earlyGates: isDamaged && posture ? earlyRecoveryGates(health, posture) : [],
    audit: posture ? {
      state: posture.state,
      instruction: posture.instruction,
      reasons: posture.reasons ?? [],
      unlock: posture.unlock ?? null,
      policy: posture.policy,
    } : null,
  }
}
