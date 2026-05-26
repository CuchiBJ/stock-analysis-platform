## Context

`TransitionEngine.calculate_operational_transition(symbol, curr_metrics, prev_metrics)` ya hace todo el trabajo: calcula la transition, computa strength, y persiste observación via `OutcomeTracker.record_observation` si transition ≠ STABLE. La función es idempotente por `(symbol, transition_type, date_detected)`.

El gap es **invocación**: solo se llama desde `/actionable` y `/transitions/symbol/*`. El scheduler corre SLOW (recalcular metrics) y luego dispara `_evaluate_pending_outcomes` — pero **no** dispara detección de nuevas transitions sobre el universo.

Resultado actual: 1 observación en 3+ días (la única vez que /actionable detectó algo non-STABLE en sus 6 setups tracking + idempotency consume el resto).

## Goals / Non-Goals

**Goals:**
- Acumular observaciones a tasa ≥10 obs/día para que las cohortes crucen N≥5 en ~1-2 semanas
- Cero side effects sobre el resto del stack — agregar volumen, no cambiar lógica
- Mantener determinismo: el batch scanner sobre el mismo (date, universe) debe producir el mismo set de observations

**Non-Goals:**
- Paralelizar el scan
- Optimizar las queries más allá del N+1 obvio
- Persistir snapshots/runs del scanner
- Permitir scope override desde el endpoint (siempre usa QUALITY_FILTERS)

## Decisions

### D1: Universe scope = QUALITY_FILTERS existentes

**Decisión**: scanner aplica `QUALITY_FILTERS` (avg_volume_10d ≥ 500k, current_price ≥ $5, adr_percent ≥ 2%) — el mismo set que usa breadth/leadership.

**Por qué**: coherencia con el resto del platform. Si la `EmpiricalProbabilityCalculator` luego sirve probabilities para setups, esos setups operacionalmente pasan estos filtros (vía quality_leader_gate). Calibrar sobre la misma población.

**Alternativa rechazada**: scanear ALL stocks con metrics → bias hacia outcomes de penny stocks que no son representativos del universo accionable.

### D2: Carga de previous_metrics — single window query

**Decisión**: para cargar `previous_metrics` por símbolo eficientemente, usar:

```sql
SELECT sm.* FROM stock_metrics sm
JOIN (
  SELECT symbol, MAX(date) AS prev_date
  FROM stock_metrics
  WHERE date < :latest_date
  GROUP BY symbol
) prev ON sm.symbol = prev.symbol AND sm.date = prev.prev_date
```

Resultado: 1 query carga los N previos, vs N queries individuales. Tiempo total: ~50-100ms para 1000 stocks.

**Alternativa rechazada**: iterar y queriear uno por uno (N+1) — funciona pero suma ~30s por la latencia de cada round-trip.

### D3: Cuándo dispara el scanner

**Decisión**: después del `trigger_metrics_update` (SLOW cycle), en el mismo `finally` block que dispara `_evaluate_pending_outcomes`, agregamos `asyncio.create_task(self._batch_scan_transitions())`. Fire-and-forget, no bloquea el SLOW cycle.

**Por qué**: la transition detection necesita metrics frescos. Los metrics son frescos justo después del SLOW. Acoplado a esa señal evita scheduling propio.

**Alternativa rechazada**: cron separado para el scanner — agrega complejidad de timing, posible drift con el ciclo SLOW.

### D4: Endpoint manual `POST /calibration/scan-now`

**Decisión**: agregar endpoint POST sin auth con tag `admin`. Acepta opcional `as_of_date` query param (default = max metrics date). Returns ScanStats.

**Por qué**: para testing y para forzar acumulación inicial mientras el SLOW cycle no se haya disparado. Es trivial de implementar (~10 líneas).

**Tradeoff**: sin auth. Aceptable porque el endpoint solo registra observations idempotentes — peor caso un atacante dispara N scans, pero cada uno es idempotente y read-mostly. Si en el futuro hay auth real, agregar middleware.

### D5: Error handling — log y continúa

**Decisión**: si `calculate_operational_transition` raise para un símbolo (data missing, NaN, etc), log WARN con el símbolo y continúa con el siguiente. No abortar el batch entero.

**Por qué**: 1 stock corrupto no debe matar el scan completo. Stats incluyen `errors` count para visibilidad.

### D6: Scan determinístico por (date, universe)

**Decisión**: el scanner ordena el universo por symbol asc antes de iterar. Si se ejecuta dos veces para la misma `as_of_date`, ambos crean exactamente el mismo set de observations (vía idempotency).

**Por qué**: facilita debugging y permite re-runs sin temor a duplicates.

### D7: Logging granularity

**Decisión**: una sola línea INFO al final del scan: `f"BatchTransitionScanner: scanned={N} non_stable={M} recorded={K} errors={E} duration={D}s"`. Sin per-symbol logs (ruido).

**Por qué**: el operador quiere ver "el sistema observó X cosas hoy", no 1000 líneas.

## Risks / Trade-offs

1. **El scanner puede crear observaciones de baja calidad** — stocks que pasan QUALITY_FILTERS pero no son setups accionables (ej. distribution en stocks débiles). Cuentan para la cohorte de `distribution` y pueden sesgar la success_rate observada. Mitigación: vivir con esto Phase 1. Si las success rates resultan inverosímiles, refinar el universe filter (ej. agregar `relative_strength_spy ≥ 80`).

2. **30s en el ciclo SLOW** — el create_task es fire-and-forget pero usa la misma DB connection pool. Si el scanner corre durante 30s, otras requests pueden encolarse. Mitigación: usar session aparte del scheduler context (ya está así en `_get_db()`).

3. **Observation explosion para signals comunes** — `weakening` o `distribution` pueden dispararse en muchos stocks simultáneamente bajo regime risk-off. Cohortes crecen rápido pero ruidosas. Mitigación: la cohorte clasifica per transition_type — si `distribution` acumula 200 obs/día, su success_rate converge rápido y muestra honesta info (probablemente FAILURE-dominado).

4. **Idempotency depende del unique constraint** — `(symbol, transition_type, date_detected)` con `on_conflict_do_nothing`. Si dos scans corren simultáneamente (ej. SLOW + manual endpoint), pueden generar deadlocks pequeños pero no duplicates. Mitigación: aceptable; el constraint es la fuente de verdad.

5. **Falla silenciosa si SLOW no corre** — si Fernando no tiene SLOW programado, el scanner nunca dispara. Mitigación: endpoint manual `POST /scan-now` permite trigger explícito.

6. **El scanner no detecta transitions retroactivamente** — si el SLOW corre tarde y nos saltamos un día, esa data queda sin observar. Aceptable Phase 1 — backfill manual via endpoint con `as_of_date` específica.
