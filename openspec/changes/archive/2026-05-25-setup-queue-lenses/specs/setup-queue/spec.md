## ADDED Requirements

### Requirement: System SHALL Expose U&R Queue Filtered by Strict Leader Criteria and "From Above" Rule

`GET /api/v1/queue/u-and-r` SHALL devolver candidatos para ejecución undercut & rally. Un candidato califica SI Y SOLO SI:

1. Pasa los 8 criterios Minervini (`is_quality_leader(current_metrics) == True`).
2. Existe al menos un row en `transition_observations` con `symbol == sym AND date_detected >= today - 2 days AND transition_type != 'stable'`.
3. **From above rule**: existe al menos un row en `stock_metrics` con `symbol == sym AND date BETWEEN today-10d AND today-5d AND distance_to_ema21_atr > 0.5`.
4. Actual `distance_to_ema21_atr` está en `[-0.5, +1.5]` (cerca de EMA21, permitiendo brief undercut).
5. No hay row en `stock_metrics` con `symbol == sym AND date >= today-20d AND distance_to_ema50_atr < 0` (no rompió EMA50).

El response SHALL incluir por candidato: `symbol`, `transition_type`, `event_age_days`, `distance_to_ema21_atr`, `rs_spy`, `volume_contraction`, `touches_last_30d`, `tradingview_url`.

El response SHALL ordenarse por: `event_age_days` ascendente, luego `abs(distance_to_ema21_atr)` ascendente, luego `rs_spy` descendente.

#### Scenario: Líder con touch fresco y "from above" válido aparece en queue

- **WHEN** `GET /api/v1/queue/u-and-r` y existe NVDA que pasa Minervini, tiene observation `entering_pullback` hace 1 día, tenía `distance_to_ema21_atr = 1.2` hace 7 días, actualmente `distance_to_ema21_atr = -0.2`, y nunca cruzó EMA50 los últimos 20 días
- **THEN** SHALL devolver NVDA en la queue con `event_age_days = 1` y `transition_type = "entering_pullback"`

#### Scenario: Stock con touch desde abajo es excluido

- **WHEN** existe stock que pasa Minervini, tiene observation `entering_pullback` hace 1 día, pero los últimos 10 días `distance_to_ema21_atr` estuvo siempre en `[-1.5, +0.2]` (nunca > 0.5)
- **THEN** SHALL NOT incluir ese stock en la queue (falla "from above" rule)

#### Scenario: Stock que rompió EMA50 es excluido

- **WHEN** un stock cumple Minervini, tiene observation reciente, cumple "from above", pero hace 8 días tuvo `distance_to_ema50_atr = -0.3`
- **THEN** SHALL NOT incluir ese stock en la queue

#### Scenario: Queue vacía cuando ningún candidato califica

- **WHEN** `GET /api/v1/queue/u-and-r` y ningún símbolo cumple los 5 filtros
- **THEN** SHALL devolver `[]` (200 OK, lista vacía — empty state válido por Principio 2)

### Requirement: System SHALL Expose Emerging Leaders with Explicit Qualification Breakdown

`GET /api/v1/queue/emerging-leaders` SHALL devolver stocks fuertes que NO califican Minervini full pero muestran características de líder emergente.

Un candidato califica SI Y SOLO SI:
1. `perf_6m > 20%`
2. `relative_strength_spy > 105`
3. `current_price > ema50`
4. `current_price > ema200`
5. `is_quality_leader(m) == False` (al menos un criterio Minervini falla)

El response por candidato SHALL incluir `symbol`, `perf_6m`, `rs_spy`, y un objeto `minervini_status` con cada uno de los 8 criterios marcado como `{passes: bool, value?, threshold?, detail?}`, además de un string `qualifies_as_emerging_because` explicando la razón principal.

#### Scenario: Stock con strong 6m perf pero sin 12m de historia aparece como emerging

- **WHEN** `GET /api/v1/queue/emerging-leaders` y PLTR tiene `perf_6m = 85`, `rs_spy = 118`, `price > ema50`, `price > ema200`, pero `perf_1y = 24` (falla criterio Minervini #1)
- **THEN** SHALL devolver PLTR con `minervini_status.perf_1y_gt_30.passes = false` y `qualifies_as_emerging_because` describiendo la razón

#### Scenario: Stock que pasa Minervini full NO aparece como emerging

- **WHEN** un stock cumple los 8 criterios Minervini completos
- **THEN** SHALL NOT aparecer en `/queue/emerging-leaders` (esos son leaders completos, no emerging)

### Requirement: System SHALL Expose Building Bases for Next-Cycle Leader Identification

`GET /api/v1/queue/building-bases` SHALL devolver líderes Minervini en consolidación VCP-style, respetando sus EMAs por al menos 4 semanas.

Un candidato califica SI Y SOLO SI:
1. Pasa `is_quality_leader(m)` (los 8 Minervini).
2. `vcp_score >= 70`.
3. `weeks_in_base >= 6`.
4. En los últimos 20 días de trading, `max(distance_to_ema21_atr) - min(distance_to_ema21_atr) <= 2.0` (oscilación contenida dentro de ±1 ATR).

El response por candidato SHALL incluir `symbol`, `vcp_score`, `weeks_in_base`, `atr_range_last_20d`, `current_distance_to_ema21_atr`, `volume_contraction_trend`.

#### Scenario: Líder Minervini con VCP score alto y oscilación contenida aparece

- **WHEN** `GET /api/v1/queue/building-bases` y AXON cumple Minervini, tiene `vcp_score = 78`, `weeks_in_base = 8`, y los últimos 20 días `distance_to_ema21_atr` osciló entre `-0.7` y `+0.7`
- **THEN** SHALL devolver AXON con `atr_range_last_20d = 1.4`

#### Scenario: Stock con oscilación amplia NO aparece

- **WHEN** un stock cumple Minervini + VCP score 75 + 8 weeks in base, pero los últimos 20 días `distance_to_ema21_atr` osciló entre `-2.5` y `+1.0` (rango 3.5 ATR)
- **THEN** SHALL NOT aparecer en building bases (no respeta EMA21 en consolidación estricta)

### Requirement: System SHALL Expose Per-Symbol Transition History for Drill-Down

`GET /api/v1/queue/symbol/{symbol}/history?days=30` SHALL devolver el arco completo de transitions del símbolo en el rango solicitado.

Response SHALL incluir:
- `symbol`
- `current_regime` (snapshot al momento del request)
- `observations`: array ordenado por `date_detected` ascendente, cada uno con `date_detected`, `transition_type`, `outcome_status`, `distance_to_ema21_atr_at_detection`, `pct_5d` (si disponible)
- `track_record`: objeto `{ <transition_type>_in_<regime>: { success_rate, sample_size } }` para los transition types presentes en las observations del símbolo, filtrado al régimen actual

El parámetro `days` SHALL aceptar valores entre 1 y 365, default 30.

#### Scenario: Drill-down de un símbolo con múltiples eventos

- **WHEN** `GET /api/v1/queue/symbol/NVDA/history?days=30` y NVDA tiene 4 observations en los últimos 30 días (varias `entering_pullback` y un `volume_dry_up`)
- **THEN** SHALL devolver las 4 observations ordenadas cronológicamente con sus outcomes si están clasificados
- **AND** SHALL incluir en `track_record` el success_rate de `entering_pullback_in_<current_regime>` y `volume_dry_up_in_<current_regime>`

#### Scenario: Símbolo sin observations devuelve historial vacío

- **WHEN** `GET /api/v1/queue/symbol/XYZ/history` y XYZ no tiene rows en `transition_observations`
- **THEN** SHALL devolver `{symbol: "XYZ", current_regime: "...", observations: [], track_record: {}}` (200 OK)

### Requirement: Quality Leader Gate SHALL Be Reusable Across Services

La función `is_quality_leader(metrics: StockMetrics) -> bool` SHALL existir en `app/services/quality_leader_gate.py` como función pura (sin estado, sin dependencias de instancia).

`TransitionEngine._is_quality_leader` SHALL delegar a esta función — el resultado SHALL ser idéntico al comportamiento previo a la extracción.

`SetupQueueService` SHALL importar y usar `is_quality_leader` para filtrar candidatos en U&R queue y Building Bases queue.

#### Scenario: Refactor preserva comportamiento idéntico

- **WHEN** se llama a `transition_engine._is_quality_leader(m)` para cualquier `StockMetrics m`
- **THEN** el resultado SHALL ser idéntico a `quality_leader_gate.is_quality_leader(m)`

#### Scenario: SetupQueueService usa el mismo gate sin instanciar TransitionEngine

- **WHEN** `setup_queue_service.list_u_and_r()` evalúa candidatos
- **THEN** SHALL usar `quality_leader_gate.is_quality_leader(m)` directamente, sin importar ni instanciar `TransitionEngine`
