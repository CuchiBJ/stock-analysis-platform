## MODIFIED Requirements

### Requirement: ENTERING_PULLBACK SHALL Detect Quality Leader Approaching EMA From Above

`ENTERING_PULLBACK` SHALL fire when a stock meets ALL Minervini SEPA quality gates AND is approaching (not crossed) its EMA9 or EMA21 from above, with the distance to the EMA decreasing vs the previous trading day.

**Quality gates — ALL must pass:**

| Criterio | Condición |
|---|---|
| Rendimiento anual | `perf_1y > 30%` |
| Tendencia larga | `current_price > ema200` |
| Tendencia media | `distance_to_ema50_atr > 0` |
| Alineación de medias | `sma50 > sma150` |
| Expansión de rango 52W | `(high_52w - low_52w) / low_52w >= 0.60` |
| Recuperación desde mínimos | `(current_price - low_52w) / low_52w >= 0.70` |
| Volatilidad tradeable | `adr_percent >= 3.0%` |

**Proximity trigger — EMA9 OR EMA21 (no ambas requeridas):**

| EMA | Distancia encima | Dirección |
|---|---|---|
| EMA9  | `0 < distance_to_ema9_atr ≤ 0.5`  | `ema9_distance_change < 0` |
| EMA21 | `0 < distance_to_ema21_atr ≤ 1.0` | `ema21_distance_change < 0` |

Si ambas condiciones se cumplen simultáneamente, EMA9 tiene prioridad (soporte más cercano).

**Implementación:** `backend/app/services/transition_engine.py`

#### Scenario: Líder Minervini approaching EMA9 aparece en feed

- **WHEN** un stock cumple los 7 quality gates Y tiene `0 < distance_to_ema9_atr ≤ 0.5` Y `ema9_distance_change < 0`
- **THEN** SHALL retornar `ENTERING_PULLBACK`
- **AND** la narrativa SHALL incluir "EMA9" e indicar soporte en zona de testing

#### Scenario: Líder Minervini approaching EMA21 aparece en feed

- **WHEN** un stock cumple los 7 quality gates Y tiene `0 < distance_to_ema21_atr ≤ 1.0` Y `ema21_distance_change < 0`
- **THEN** SHALL retornar `ENTERING_PULLBACK`
- **AND** la narrativa SHALL incluir "EMA21" e indicar soporte clave de swing

#### Scenario: Stock sin quality gates NO genera ENTERING_PULLBACK

- **WHEN** un stock cruza EMA21 hacia abajo pero NO cumple todos los quality gates (ej: `perf_1y < 30%` o `distance_to_ema50_atr <= 0`)
- **THEN** SHALL NOT retornar `ENTERING_PULLBACK`
- **AND** SHALL retornar el transition type que corresponda por sus otras características (STABLE, WEAKENING, etc.)

#### Scenario: Stock rebotando desde EMA NO genera ENTERING_PULLBACK

- **WHEN** un stock está dentro del rango de proximidad (ej: `distance_to_ema21_atr = 0.4`) pero su distancia está AUMENTANDO (`ema21_distance_change > 0`)
- **THEN** SHALL NOT retornar `ENTERING_PULLBACK` (el test ya ocurrió y el stock se alejó)

#### Scenario: Stock reclamando EMA21 desde abajo NO genera ENTERING_PULLBACK

- **WHEN** un stock está en `distance_to_ema21_atr = -0.1` (debajo) moviéndose hacia arriba
- **THEN** SHALL NOT retornar `ENTERING_PULLBACK` (está en zona de RECLAIMING)
