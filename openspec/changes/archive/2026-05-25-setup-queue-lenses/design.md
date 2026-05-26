## Context

El sistema detecta transitions y persiste observations (capacidad `outcome-tracking` recién implementada), pero el operador no tiene una vista de trabajo que filtre por su estrategia específica (undercut & rally en líderes Minervini). Hoy debe revisar `/transitions/live` (todas las transitions del día), copiar mentalmente al watchlist de TradingView y recordar contexto sin asistencia del sistema.

Tres datos críticos ya existen y se reutilizan sin nueva infraestructura:
- `transition_observations` — eventos por símbolo con timestamps y contexto snapshot
- `stock_metrics` — snapshots diarios indexados por `(symbol, date)`
- `_is_quality_leader` en `transition_engine.py:637` — los 8 gates Minervini

## Goals / Non-Goals

**Goals:**
- Reemplazar la curación manual TradingView por tres lentes dinámicas con propósito explícito.
- Aplicar regla "from above" en la lente U&R sin contaminar `transition_engine` (mantenerlo genérico).
- Mostrar contexto histórico por símbolo (arc de transitions últimos 30 días) al click de cualquier row.
- Performance < 300ms por lente para listas típicas de 5-20 candidatos.

**Non-Goals:**
- "Changes since last visit" (requiere persistencia de last-view-timestamp — v2).
- Anotaciones personales por símbolo (requiere modelo de notas — v2).
- Alertas / push notifications (no hay auth ni capa de notificaciones).
- Order management / ejecución automatizada.
- Charts embebidos (link out a TradingView para análisis de pivot 30-min).
- Mobile-first / responsive prioritario.
- Backfill histórico de observations para lente U&R — usa solo lo que se va capturando desde 2026-05-23.

## Decisions

### Decisión 1: Tres lentes separadas, no una sola con filtros

Una sola vista con dropdowns ("mostrar U&R" / "mostrar emerging") obliga al operador a configurar cada vez. Tres tabs explícitos comunican que son tres workflows distintos con criterios fundamentalmente distintos.

**Alternativa descartada:** Vista única con filtros toggleables. Rechazada porque mezcla horizontes temporales (acute vs development) y rompe el modelo mental del operador.

### Decisión 2: Regla "from above" a nivel de query, NO en transition_engine

`TransitionEngine.calculate_operational_transition` clasifica genéricamente para múltiples vistas (transitions/live, outcome tracking, futuras lentes). La regla "from above" es específica a la estrategia U&R — vive en el query de la lente U&R, no en el engine.

**Implementación:** Lookup adicional en `setup_queue_service.list_u_and_r()`:
```python
# Para cada candidato con observation últimos 2 días:
historical = await db.execute(
    select(StockMetrics.distance_to_ema21_atr)
    .where(
        StockMetrics.symbol == sym,
        StockMetrics.date.between(date_5d_ago, date_10d_ago)
    )
)
was_above = any(d > 0.5 for d in historical.scalars() if d is not None)
if not was_above:
    continue
```

**Alternativa descartada:** Modificar `_determine_operational_transition` para exigir contexto histórico. Rechazada porque cambia la semántica de las transitions para TODO el sistema y rompe outcome tracking (donde detectamos cada touch).

### Decisión 3: Extraer `_is_quality_leader` a helper compartido

Actualmente vive en `transition_engine.py:637-669` como método de instancia (`self._is_quality_leader`). Para reutilizarlo en `setup_queue_service` sin instanciar el engine, lo extraemos a `app/services/quality_leader_gate.py` como función pura.

```python
# Antes: transition_engine.py
def _is_quality_leader(self, m: StockMetrics) -> bool: ...

# Después: quality_leader_gate.py
def is_quality_leader(m: StockMetrics) -> bool: ...

# transition_engine.py
from app.services.quality_leader_gate import is_quality_leader
def _is_quality_leader(self, m: StockMetrics) -> bool:
    return is_quality_leader(m)
```

Backwards compat preservada (el método del engine sigue existiendo y delega). Esto es un primer paso de descomposición — `transition_engine.py` (~825 LOC) merece más extracción a futuro.

**Alternativa descartada:** Replicar la lógica en setup_queue_service. Rechazada — dos fuentes de verdad para los 8 criterios Minervini garantiza drift en 3 meses.

### Decisión 4: Lente 1 (U&R) — filtros y ranking exactos

**Filtros (en orden de evaluación):**
1. Pasa `is_quality_leader(m)` (los 8 Minervini)
2. Existe row en `transition_observations` con `symbol == sym AND date_detected >= today - 2 days AND transition_type != 'stable'`
3. Histórico `distance_to_ema21_atr` entre día-10 y día-5: al menos un valor `> 0.5`
4. Actual `distance_to_ema21_atr ∈ [-0.5, +1.5]`
5. Histórico `distance_to_ema50_atr` últimos 20 días: nunca `< 0` (no rompió EMA50)

**Ranking:**
1. Recencia del evento (1d ago > 2d ago)
2. Proximidad a EMA21 ascendente (|distance_to_ema21_atr| menor primero)
3. RS_spy descendente (desempate)

**Output por row:**
```json
{
  "symbol": "NVDA",
  "transition_type": "entering_pullback",
  "event_age_days": 1,
  "distance_to_ema21_atr": -0.2,
  "rs_spy": 112,
  "volume_contraction": 31,
  "touches_last_30d": 4,
  "tradingview_url": "https://www.tradingview.com/chart/?symbol=NVDA"
}
```

### Decisión 5: Lente 2 (Emerging Leaders) — qualification breakdown explícito

Cada candidato muestra qué criterios Minervini pasa y cuáles falla. Esto evita falsa autoridad: el sistema dice "esto es emerging y aquí está por qué" en vez de presentarlo como si fuera leader.

**Filtros:**
1. Pasa: `perf_6m > 20% AND RS_spy > 105 AND price > EMA50 AND price > EMA200`
2. NO pasa `is_quality_leader(m)` (al menos un criterio falla)

**Output incluye desglose:**
```json
{
  "symbol": "PLTR",
  "perf_6m": 85.2,
  "rs_spy": 118,
  "minervini_status": {
    "perf_1y_gt_30": {"passes": false, "value": 24.0, "threshold": 30.0},
    "price_above_ema200": {"passes": true},
    "price_above_ema50": {"passes": true},
    "sma_chain": {"passes": false, "detail": "SMA150 < SMA200 * 1.05"},
    ...
  },
  "qualifies_as_emerging_because": "Strong 6m perf + RS but lacks 12m history for Stage 2"
}
```

### Decisión 6: Lente 3 (Building Bases) — oscilación ATR como filtro core

"Respetando EMAs" se operacionaliza como: `distance_to_ema21_atr` en cada uno de los últimos 20 días de trading se mantuvo dentro de `±1 ATR`. No basta con tener una oscilación promedio — el rango max-min debe ser ≤ 2 ATR.

**Filtros:**
1. Pasa `is_quality_leader(m)`
2. `vcp_score >= 70`
3. `weeks_in_base >= 6`
4. `max(d21_atr últimos 20d) - min(d21_atr últimos 20d) <= 2.0`

**Output incluye:**
```json
{
  "symbol": "AXON",
  "vcp_score": 78,
  "weeks_in_base": 8,
  "atr_range_last_20d": 1.4,
  "current_distance_to_ema21_atr": 0.3,
  "volume_contraction_trend": "declining"
}
```

### Decisión 7: Endpoint de historial por símbolo

`GET /api/v1/queue/symbol/{symbol}/history?days=30` devuelve el arco completo: todas las observations + outcome status si está clasificado. Para el drawer/modal al click.

```json
{
  "symbol": "NVDA",
  "current_regime": "choppy",
  "observations": [
    {
      "date_detected": "2026-05-23",
      "transition_type": "entering_pullback",
      "outcome_status": "PENDING",
      "distance_to_ema21_atr_at_detection": -0.2
    },
    ...
  ],
  "track_record": {
    "entering_pullback_in_choppy": {"success_rate": 0.52, "sample_size": 47}
  }
}
```

### Decisión 8: Frontend — página dedicada, no panel

Esta es UN workflow primario, no un widget secundario. Vive en `/queue` como página propia con 3 tabs. El dashboard sigue siendo el panorama; `/queue` es la mesa de trabajo.

**Layout:**
- Top: 3 tabs (U&R / Emerging / Building Bases) + indicador de count por tab
- Row click → drawer lateral con `SymbolHistoryDrawer` mostrando arco completo
- Cada row: botón "TradingView →" para análisis 30-min
- Refresh automático cada 60s (transitions cambian con cada SLOW cycle)

## Risks / Trade-offs

**[Riesgo 1: Queue U&R puede estar vacía los primeros días post-deploy]**  
`transition_observations` empezó a poblar 2026-05-23. La lente U&R requiere observations de últimos 2 días. → Mitigación: Empty state honesto (`"No qualifying setups in the last 2 days. The system tracks forward — wait for the next SLOW cycle."`) + WebSocket subscribe a `metrics.updated` para refresh automático cuando entren nuevos.

**[Riesgo 2: Lookup histórico "from above" es N+1]**  
Por cada candidato, se hace un query a `stock_metrics` para 5-10 días atrás. Con 10-20 candidatos típicos: 10-20 queries adicionales. → Mitigación: bulk fetch — un solo query con `WHERE symbol IN (...) AND date BETWEEN ...` y join in-memory.

**[Riesgo 3: Lente 3 (Building Bases) puede mostrar el mismo símbolo durante semanas]**  
Una base bien formada permanece estable. El operador puede ignorar la lente. → Aceptado. Esta lente es para revisión semanal, no diaria. El operador NO mira las 3 lentes con la misma frecuencia — U&R diariamente, Emerging semanalmente, Building Bases ocasionalmente.

**[Riesgo 4: Empate frecuente en sort por recencia (mismo día)]**  
Múltiples candidatos con observation hoy compiten por orden. → Mitigación: tie-breaker es `|distance_to_ema21_atr|` ascendente, luego RS_spy descendente. Determinístico.

**[Riesgo 5: `vcp_score >= 70` puede ser muy alto y dejar lente 3 vacía]**  
Con datos reales puede que pocos stocks alcancen 70. → Aceptado para v1. Si después de 30 días la lente está consistentemente vacía, bajar a 60 con `ALTER` simple del threshold en el service.

## Migration Plan

1. Crear `quality_leader_gate.py` con función pura `is_quality_leader(m)`.
2. Refactorizar `transition_engine.py:_is_quality_leader` para delegar al helper.
3. Verificar que tests existentes (si hay) y `/transitions/live` siguen funcionando.
4. Crear `setup_queue_service.py` con tres métodos: `list_u_and_r()`, `list_emerging_leaders()`, `list_building_bases()`, `get_symbol_history(symbol, days)`.
5. Crear `endpoints/queue.py` con 4 rutas.
6. Registrar router en `api.py` con prefix `/queue`.
7. Crear frontend `/queue/page.tsx` + 3 componentes + drawer.
8. Validar end-to-end: golpear cada endpoint, verificar shapes, navegar UI.

**Rollback**: Revertir código. No hay migración de DB ni schema changes — todos los datos ya existen. Cero riesgo de pérdida.

## Open Questions

- **¿Cuánto historial mostrar en el drawer por símbolo?** Decisión actual: 30 días. Permite ver el arco completo de un setup en desarrollo sin sobrecargar con ruido de meses atrás. Si el operador pide más, agregar param `?days=N`.
- **¿Mostrar lente vacía o ocultar el tab?** Decisión: siempre mostrar los 3 tabs con count `(0)` cuando vacíos + empty state honesto explicando criterios. Ocultar tabs rompe la consistencia visual.
