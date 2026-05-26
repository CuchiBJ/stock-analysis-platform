## MODIFIED Requirements

### Requirement: CONTINUATION_HOLDING SHALL Require Quality Leader Status, Above-EMA9 Position, and Non-Decreasing Distance

`CONTINUATION_HOLDING` SHALL fire only when a stock meets ALL Minervini SEPA quality gates (same as ENTERING_PULLBACK), is above both EMA9 and EMA21, and the distance to EMA21 is stable or increasing (not approaching EMA21).

**Quality gates — ALL must pass (via `_is_quality_leader()`):**

| Criterio | Condición |
|---|---|
| Rendimiento anual | `perf_1y > 30%` |
| Tendencia larga | `current_price > ema200` |
| Tendencia media | `distance_to_ema50_atr > 0` |
| Alineación cortos-medios | `sma50 > sma150` |
| Alineación medio-largo plazo | `sma150 > sma200 * 1.05` (5% separation) |
| Expansión de rango 52W | `(high_52w - low_52w) / low_52w >= 0.60` |
| Recuperación desde mínimos | `(current_price - low_52w) / low_52w >= 0.70` |
| Volatilidad tradeable | `adr_percent >= 3.0%` |

**Position trigger:**

| Variable | Condición |
|---|---|
| Distancia a EMA9 | `distance_to_ema9_atr >= 0` (no rompió EMA9) |
| Distancia a EMA21 | `0 <= distance_to_ema21_atr <= 1.5` (zona operable) |
| Dirección | `ema21_distance_change >= 0` (subiendo o lateral) |

**Implementación:** `backend/app/services/transition_engine.py`, block #10 en `_determine_operational_transition()`.

#### Scenario: Líder Stage 2 sostiéndose arriba de EMA21 aparece como continuation

- **WHEN** un stock cumple los 8 quality gates Y `distance_to_ema9_atr = 0.3` Y `distance_to_ema21_atr = 0.8` Y `ema21_distance_change = +0.05`
- **THEN** SHALL retornar `CONTINUATION_HOLDING`

#### Scenario: Stock arriba de EMA21 pero rompió EMA9 NO es continuation

- **WHEN** un stock cumple quality gates Y `distance_to_ema21_atr = 0.4` (arriba) PERO `distance_to_ema9_atr = -0.3` (debajo de EMA9)
- **THEN** SHALL NOT retornar `CONTINUATION_HOLDING`
- **AND** caerá a otra evaluación de la cascada (ENTERING_PULLBACK si está cayendo a EMA21, o fallback)

#### Scenario: Stock arriba de EMA21 pero cayendo hacia ella NO es continuation

- **WHEN** un stock cumple quality gates Y `0 < distance_to_ema21_atr <= 1.5` PERO `ema21_distance_change < 0` (cayendo a EMA21)
- **THEN** SHALL NOT retornar `CONTINUATION_HOLDING`
- **AND** SHALL retornar `ENTERING_PULLBACK` (transition más específica para esa situación)

#### Scenario: Stock sin quality gates NO es continuation aunque esté arriba de EMA21

- **WHEN** un stock tiene `0 < distance_to_ema21_atr <= 1.5` pero falla algún quality gate (ej: `perf_1y < 30%` o `sma150 < sma200 * 1.05`)
- **THEN** SHALL NOT retornar `CONTINUATION_HOLDING`
- **AND** caerá al fallback (STABLE u otro)

### Requirement: STABILIZING SHALL Detect Pre-Breakout Volatility Contraction In Quality Leaders Above EMA21

`STABILIZING` SHALL fire cuando un líder institucional (8 quality gates) está arriba de EMA21 con estructura semanal ajustándose (volatility contraction) y volumen contrayéndose — el patrón clásico pre-breakout de Minervini en uptrend.

Es el complemento alcista de `COMPRESSING` (que opera debajo de EMA21).

**Quality gates — ALL must pass (via `_is_quality_leader()`):** mismos 8 gates que CONTINUATION_HOLDING.

**Position + structure trigger:**

| Variable | Condición |
|---|---|
| Distancia a EMA21 | `0 <= distance_to_ema21_atr <= 2.0` (zona operable arriba) |
| Tightness semanal | `weekly_tightness >= 0.3` (rangos contrayéndose) |
| Cambio de volumen | `volume_change_pct < 0` (volumen también baja) |

**Implementación:** `backend/app/services/transition_engine.py`, block #11 (evaluado ANTES de CONTINUATION_HOLDING en la cascada para que tenga prioridad).

#### Scenario: Líder con tightness alta y volumen contrayéndose aparece como stabilizing

- **WHEN** un stock cumple los 8 quality gates Y `distance_to_ema21_atr = 1.2` Y `weekly_tightness = 0.45` Y `volume_change_pct = -22`
- **THEN** SHALL retornar `STABILIZING`

#### Scenario: Stock con tightness alta pero volumen subiendo NO es stabilizing

- **WHEN** un stock cumple gates Y tiene `weekly_tightness = 0.4` PERO `volume_change_pct = +15` (volumen subiendo)
- **THEN** SHALL NOT retornar `STABILIZING` (la contracción de rango con expansion de volumen no es pre-breakout, es alguna otra dinámica)
- **AND** caerá a CONTINUATION_HOLDING si cumple esos criterios

#### Scenario: Stock con weekly_tightness baja NO es stabilizing

- **WHEN** un stock cumple gates Y tiene `weekly_tightness = 0.15` (rango aún amplio)
- **THEN** SHALL NOT retornar `STABILIZING`
- **AND** caerá a CONTINUATION_HOLDING (sosteniéndose pero no contrayéndose)

#### Scenario: Stock sin quality gates NO es stabilizing aunque tenga tightness

- **WHEN** un stock no es quality_leader pero tiene `weekly_tightness = 0.5` y `volume_change_pct = -30`
- **THEN** SHALL NOT retornar `STABILIZING` (el patrón pre-breakout solo es operativo en líderes Stage 2 confirmados, en otros es noise)
