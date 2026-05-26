## ADDED Requirements

### Requirement: System SHALL Persist Every Non-STABLE Transition Detection

Cada vez que `TransitionEngine.calculate_operational_transition()` clasifica un símbolo en una `OperationalTransition` que NO es `STABLE`, el sistema SHALL persistir un registro `TransitionObservation` con context snapshot completo en el momento de detección.

Cada observation SHALL incluir: `symbol`, `transition_type`, `detected_at`, `date_detected`, `regime_at_detection`, `price_at_detection`, `ema9/21/50_at_detection`, `atr_at_detection`, `rs_spy_at_detection`, `adr_percent_at_detection`, `vcp_score_at_detection`, `relative_volume_at_detection`, `weekly_tightness_at_detection`.

Observations SHALL ser deduplicated por `(symbol, transition_type, date_detected)` — un solo registro por símbolo-transición-día.

#### Scenario: Sistema persiste observation cuando detecta ENTERING_PULLBACK

- **WHEN** `calculate_operational_transition` clasifica un símbolo como `ENTERING_PULLBACK`
- **THEN** SHALL insertar un row en `transition_observations` con `transition_type='entering_pullback'`
- **AND** SHALL llenar todos los context fields con valores actuales de `current_metrics` y `regime_at_detection` del momento

#### Scenario: Sistema NO persiste observation cuando transition es STABLE

- **WHEN** `calculate_operational_transition` clasifica un símbolo como `STABLE`
- **THEN** SHALL NOT insertar row en `transition_observations`

#### Scenario: Sistema dedup correctamente al mismo símbolo-transición-día

- **WHEN** un símbolo es clasificado como `VOLUME_DRY_UP` dos veces en el mismo `date_detected` (e.g. SLOW cycle corrió dos veces)
- **THEN** SHALL persistir exactamente 1 row en `transition_observations`
- **AND** SHALL NOT generar error de unique constraint visible al transition engine

### Requirement: System SHALL Evaluate Outcomes After Sufficient Time Elapsed

Un job `OutcomeTracker.evaluate_pending_outcomes(as_of_date)` SHALL correr después de cada SLOW cycle exitoso. Para cada observation con `outcome_status='PENDING'`:

- Si `date_detected + 1` <= `as_of_date`: SHALL fill `price_1d`, `pct_1d`.
- Si `date_detected + 5` <= `as_of_date`: SHALL fill `price_5d`, `pct_5d`.
- Si `date_detected + 10` <= `as_of_date`: SHALL fill outcome window fields (`max_gain_within_10d`, `max_drawdown_within_10d`, `max_gain_atr_within_10d`, `max_drawdown_atr_within_10d`, `reached_ema21_within_10d`, `broke_ema50_within_10d`) AND SHALL classify `outcome_status`.
- Si `date_detected + 20` <= `as_of_date`: SHALL fill `price_20d`, `pct_20d`.

Outcome computation usa `stock_prices` records entre `date_detected` y `date_detected + 20`.

#### Scenario: Observation de hace 12 días recibe outcome completo

- **WHEN** existe observation con `date_detected = '2026-05-10'` y `outcome_status = 'PENDING'`, y `as_of_date = '2026-05-22'`
- **THEN** SHALL llenar `price_1d`, `pct_1d`, `price_5d`, `pct_5d`, outcome window fields
- **AND** SHALL clasificar `outcome_status` (SUCCESS/FAILURE/NEUTRAL)
- **AND** SHALL setear `outcome_evaluated_at = NOW()`

#### Scenario: Observation de hace 3 días recibe solo +1d y +5d (parcial)

- **WHEN** existe observation con `date_detected = '2026-05-19'` y `as_of_date = '2026-05-22'`
- **THEN** SHALL llenar `price_1d`, `pct_1d` y posiblemente `price_5d`/`pct_5d` (si ya hay 5 trading days)
- **AND** SHALL NOT clasificar `outcome_status` (queda PENDING hasta +10d)

#### Scenario: Observation sin suficientes precios disponibles

- **WHEN** una observation requiere precio +5d pero `stock_prices` no tiene rows en ese rango (símbolo deslistado, gap de datos)
- **THEN** SHALL setear `outcome_status = 'INSUFFICIENT_DATA'`
- **AND** SHALL NOT volver a evaluar esta observation en ciclos futuros

### Requirement: Outcome Classification SHALL Follow Family-Specific Rules

`OutcomeTracker._classify_outcome` SHALL clasificar cada observation según la familia de la transition:

**Pre-reclaim** (ENTERING_PULLBACK, VOLUME_DRY_UP, COMPRESSING, FLUSH_AND_RECOVER, SUPPORT_HOLDING):
- SUCCESS: `reached_ema21_within_10d = TRUE` AND `max_drawdown_atr_within_10d > -2.5`
- FAILURE: `broke_ema50_within_10d = TRUE` OR `max_drawdown_atr_within_10d < -3.0`
- NEUTRAL: ninguna de las anteriores

**Reclaim/continuation** (RECLAIMING, CONTINUATION_HOLDING, STABILIZING):
- SUCCESS: `max_gain_atr_within_10d > 1.0` AND `max_drawdown_atr_within_10d > -1.5`
- FAILURE: `pct_5d < -3.0`
- NEUTRAL: ninguna de las anteriores

**Deterioration** (WEAKENING, DISTRIBUTION, FAILING) — inverted:
- SUCCESS (correctly avoided): `pct_10d < 0`  (cualquier baja confirma el aviso)
- FAILURE (false signal): `pct_5d > 3.0`  (recuperó fuerte tras el aviso)
- NEUTRAL: ninguna de las anteriores

#### Scenario: ENTERING_PULLBACK que alcanzó EMA21 con drawdown controlado → SUCCESS

- **WHEN** observation tipo `ENTERING_PULLBACK` tiene `reached_ema21_within_10d = TRUE` AND `max_drawdown_atr_within_10d = -1.2`
- **THEN** SHALL clasificar `outcome_status = 'SUCCESS'`

#### Scenario: ENTERING_PULLBACK que rompió EMA50 → FAILURE

- **WHEN** observation tipo `ENTERING_PULLBACK` tiene `broke_ema50_within_10d = TRUE`
- **THEN** SHALL clasificar `outcome_status = 'FAILURE'`

#### Scenario: DISTRIBUTION que fue seguida de baja → SUCCESS (correctly avoided)

- **WHEN** observation tipo `DISTRIBUTION` tiene `pct_10d = -4.5`
- **THEN** SHALL clasificar `outcome_status = 'SUCCESS'`

#### Scenario: DISTRIBUTION que fue seguida de rebote >3% → FAILURE (false signal)

- **WHEN** observation tipo `DISTRIBUTION` tiene `pct_5d = 4.2`
- **THEN** SHALL clasificar `outcome_status = 'FAILURE'`

### Requirement: API SHALL Expose Aggregated Track Record

`GET /api/v1/transitions/track-record` SHALL aceptar query params `transition_type` (required), `regime` (optional, default = all), `days` (optional, default = 90, max = 365) y SHALL devolver agregados sobre observations con outcome != PENDING en el rango.

Response SHALL incluir: `transition_type`, `regime`, `window_days`, `sample_size`, `success_rate`, `failure_rate`, `neutral_rate`, `avg_pct_5d`, `avg_max_gain_atr_10d`, `avg_max_drawdown_atr_10d`, `median_pct_5d`, `minimum_sample_warning` (string or null).

Si `sample_size < 30`, `minimum_sample_warning` SHALL ser `"Sample size below 30 — stats unreliable"`. Response no SHALL bloquearse — el caller decide.

#### Scenario: Endpoint devuelve agregados para ENTERING_PULLBACK en bull regime

- **WHEN** `GET /api/v1/transitions/track-record?transition_type=ENTERING_PULLBACK&regime=bull&days=90`
- **THEN** SHALL devolver `sample_size`, `success_rate`, `failure_rate`, `neutral_rate` y todos los avg/median fields
- **AND** los rates SHALL sumar ~1.0 (tolerancia 0.01)

#### Scenario: Endpoint advierte sample size insuficiente

- **WHEN** la query devuelve menos de 30 observations clasificadas
- **THEN** `minimum_sample_warning` SHALL ser `"Sample size below 30 — stats unreliable"`
- **AND** el response SHALL incluir igual los stats calculados (no devolver vacío)

#### Scenario: Endpoint sin observations devuelve sample_size = 0

- **WHEN** no hay observations clasificadas para el filtro
- **THEN** SHALL devolver `sample_size = 0`, todos los rates `null`, `minimum_sample_warning = "No data"`

### Requirement: API SHALL Expose Per-Symbol Observation History

`GET /api/v1/transitions/observations/{symbol}` SHALL devolver las últimas 50 observations del símbolo, ordenadas por `detected_at DESC`, con todos los context fields y outcome fields (cuando estén disponibles).

#### Scenario: Endpoint devuelve historial de un símbolo

- **WHEN** `GET /api/v1/transitions/observations/NVDA`
- **THEN** SHALL devolver array de observations ordenadas más recientes primero
- **AND** cada observation SHALL incluir `transition_type`, `date_detected`, context snapshot y outcome fields (con null si pending)

#### Scenario: Símbolo sin observations devuelve array vacío

- **WHEN** un símbolo no tiene observations en `transition_observations`
- **THEN** SHALL devolver `[]` (200 OK, no 404)
