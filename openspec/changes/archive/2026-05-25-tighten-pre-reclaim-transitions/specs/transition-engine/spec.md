## MODIFIED Requirements

### Requirement: VOLUME_DRY_UP SHALL Require Quality Leader Status and Bounded Depth

`VOLUME_DRY_UP` SHALL fire solo cuando un stock que era líder Stage 2 (8 quality gates) está debajo de EMA21 dentro de un rango operable (-2.0 ATR), con volumen contrayéndose y RS sosteniéndose.

**Criterios:**
- `_is_quality_leader()` — todos los 8 gates
- `-2.0 <= distance_to_ema21_atr < -0.3` — debajo de EMA21 pero no roto estructuralmente
- `volume_change_pct < -25` — volumen seco real (no solo bajando)
- `rs_change >= -1` — RS holding

#### Scenario: Líder Stage 2 con volumen seco bajo EMA21 aparece

- **WHEN** un stock cumple los 8 quality gates Y `distance_to_ema21_atr = -0.8` Y `volume_change_pct = -35` Y `rs_change = 0`
- **THEN** SHALL retornar `VOLUME_DRY_UP`

#### Scenario: Stock a -3 ATR de EMA21 con vol seco NO aparece

- **WHEN** un stock cumple quality gates Y `distance_to_ema21_atr = -3.0` (demasiado profundo)
- **THEN** SHALL NOT retornar `VOLUME_DRY_UP` (riesgo estructural, no setup operable)

#### Scenario: Stock sin quality gates no genera VOLUME_DRY_UP

- **WHEN** un stock sin Stage 2 confirmado tiene volumen seco bajo EMA21
- **THEN** SHALL NOT retornar `VOLUME_DRY_UP`

### Requirement: COMPRESSING SHALL Require Quality Leader Status and Bounded Depth

`COMPRESSING` SHALL fire solo cuando un líder Stage 2 está debajo de EMA21 dentro de -2.0 ATR, con estructura semanal contrayéndose (tightness mejorando) y volumen bajando.

**Criterios:**
- `_is_quality_leader()` — todos los 8 gates
- `-2.0 <= distance_to_ema21_atr < -0.3`
- `structure_change > 0.08` — tightness aumentando (rangos semana a semana más estrechos)
- `volume_change_pct < 0`

#### Scenario: Líder comprimiendo bajo EMA21 aparece

- **WHEN** un stock cumple los 8 quality gates Y `distance_to_ema21_atr = -0.5` Y `structure_change = 0.12` Y `volume_change_pct = -18`
- **THEN** SHALL retornar `COMPRESSING`

#### Scenario: Stock a -2.5 ATR con estructura contrayéndose NO aparece

- **WHEN** `distance_to_ema21_atr = -2.5` (fuera del rango operable)
- **THEN** SHALL NOT retornar `COMPRESSING`

#### Scenario: Stock sin quality gates no genera COMPRESSING

- **WHEN** un stock sin Stage 2 confirmado tiene estructura contrayéndose bajo EMA21
- **THEN** SHALL NOT retornar `COMPRESSING`

### Requirement: SUPPORT_HOLDING SHALL Detect Quality Leader Bouncing at EMA50 Below EMA21

`SUPPORT_HOLDING` SHALL fire cuando un líder Stage 2 perdió EMA21 pero está en zona de EMA50 y rebotando — distancia a EMA21 negativa, EMA50 actuando como soporte.

**Criterios:**
- `_is_quality_leader()` — todos los 8 gates
- `distance_to_ema21_atr < 0` — debajo de EMA21
- `-0.5 <= distance_to_ema50_atr <= 0.2` — en zona de EMA50
- `ema21_distance_change > 0.1` — rebotando (distancia a EMA21 mejorando)

#### Scenario: Líder rebotando en EMA50 debajo de EMA21 aparece

- **WHEN** un stock cumple quality gates Y `distance_to_ema21_atr = -0.8` Y `distance_to_ema50_atr = -0.1` Y `ema21_distance_change = 0.25`
- **THEN** SHALL retornar `SUPPORT_HOLDING`

#### Scenario: Stock arriba de EMA21 cerca de EMA50 no es support_holding

- **WHEN** `distance_to_ema21_atr = 0.3` (arriba de EMA21)
- **THEN** SHALL NOT retornar `SUPPORT_HOLDING` (si rebota y está arriba de EMA21 es otro pattern)

#### Scenario: Stock sin quality gates no genera SUPPORT_HOLDING

- **WHEN** un stock sin Stage 2 confirmado bouncea en EMA50
- **THEN** SHALL NOT retornar `SUPPORT_HOLDING`

### Requirement: FLUSH_AND_RECOVER SHALL Require Quality Leader Status

`FLUSH_AND_RECOVER` SHALL fire cuando un líder Stage 2 tuvo un flush de volumen (sacudón) y está rebotando desde debajo de EMA21.

**Criterios:**
- `_is_quality_leader()` — todos los 8 gates
- `relative_volume > 1.5`
- `ema21_distance_change > 0.3`
- `-2.5 <= distance_to_ema21_atr <= -0.5`

#### Scenario: Líder con flush y rebote aparece

- **WHEN** un stock cumple quality gates Y `rvol = 2.1` Y `ema21_distance_change = 0.5` Y `distance_to_ema21_atr = -1.0`
- **THEN** SHALL retornar `FLUSH_AND_RECOVER`

#### Scenario: Stock sin quality gates con flush no genera señal

- **WHEN** un stock sin Stage 2 tiene rvol = 3.0 y rebota desde -1.5 ATR
- **THEN** SHALL NOT retornar `FLUSH_AND_RECOVER`
