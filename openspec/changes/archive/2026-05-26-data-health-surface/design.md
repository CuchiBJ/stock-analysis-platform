## Context

El scheduler (proceso `python -m app.data.scheduler`) tiene 8 entrypoints async invocados desde el loop principal vía `asyncio.create_task`. Si cualquiera raise, Python emite `Task exception was never retrieved` en stderr — el scheduler sigue corriendo pero esa tarea muere silenciosa.

Los 3 bugs de hoy son del mismo molde: cycle aborta a la mitad → siguiente cycle funciona o también falla → log se llena de tracebacks → operador no entera hasta abrir el log a mano. La distancia entre "algo falló" y "operador se entera" es lo que hay que cerrar.

## Goals / Non-Goals

**Goals:**
- Errores async del scheduler quedan persistidos en DB en lugar de volar al stderr
- La UI muestra de forma imposible-de-ignorar cuando el pipeline está roto o desactualizado
- Test/script standalone que valide el pipeline desde CLI

**Non-Goals:**
- Alerting externo (email/Slack)
- Auto-resolución / auto-retry de errores
- Liveness probe del proceso scheduler
- UI rica de visualización de errores históricos

## Decisions

### D1: `is_stale` se define como `metrics_lag_days > 0`

**Decisión**: `is_stale = max(stock_metrics.date) < max(stock_price.date)`. NO usar "metrics.date < today".

**Por qué**: tolerancia natural a weekends y holidays. Si hoy es sábado, `stock_price.date` también es viernes — comparar metrics vs prices da `0` (sano) en lugar de gritar "stale" todos los weekends. La invariante que importa es "SLOW catched up con el último día de trading", no "es exactamente hoy".

**Edge case**: si por algún motivo prices también está stale (price ingestor también falló), `is_stale` = false aunque ambos estén atrás. Mitigación: agregar `prices_lag_days = today - price.date` en weekdays solamente — separable, complementa.

### D2: Persistir solo errores, no successes

**Decisión**: `scheduler_errors` tabla guarda excepciones; no se loguea cada run exitoso.

**Por qué**: 100s de runs/día. No vale el ruido. La señal de "está corriendo OK" la da `metrics.date` avanzando.

**Alternativa rechazada**: tabla `scheduler_runs(task_name, started_at, completed_at, status)`. Útil para SLA pero overkill Phase 1.

### D3: Decorator wraps coroutines, no class methods directamente

**Decisión**: `@track_task_errors(task_name="...")` recibe un task_name explícito como argumento. No se infiere de `func.__name__` para evitar nombres como `_evaluate_pending_outcomes` que cambian si refactoreás.

```python
@track_task_errors(task_name="evaluate_outcomes")
async def _evaluate_pending_outcomes(self):
    ...
```

**Por qué**: explícito > implícito. task_name persiste a la tabla y se usa en filtros/queries; conviene que sea estable.

### D4: Banner polling cada 60s

**Decisión**: el banner llama `/health/data-freshness` cada 60 segundos vía `setInterval`.

**Por qué**: balance entre frescura (operador ve el error rápido) y carga (no requests-spam). 60s es coherente con el FAST cycle (5 min) — el banner detecta nuevos errores antes que cualquier otro update.

### D5: Banner siempre visible cuando hay problema, NO dismissible

**Decisión**: cero botón de "X" para cerrar. El banner desaparece solo cuando el health vuelve a verde.

**Por qué**: el problema actual es exactamente "operador ignora warnings y se olvida". Si lo hago dismissible, mañana se olvida que cerró el banner y vuelve a confiar. Stale data = trabajo desperdiciado entrando setups en data vieja.

**Tradeoff**: si el banner aparece muchas veces sin causa real (false positives), molesta. Mitigación: `is_stale` (D1) está calibrado para minimizar falsos positivos.

### D6: Retención de errores — 7 días, hard cap

**Decisión**: `scheduler_errors` retiene 7 días. Más viejos se borran (cron o cleanup en startup).

**Por qué**: la tabla es operacional, no histórica. Después de 7 días un error específico es irrelevante; lo que importa es el patrón actual.

**Implementación Phase 1**: cleanup en startup del FastAPI (`DELETE WHERE occurred_at < NOW() - INTERVAL '7 days'`). No cron formal.

### D7: Health endpoint retorna últimos 5 errores como muestra

**Decisión**: `recent_errors` array con últimos 5, ordenados por `occurred_at DESC`. Más count total en `recent_errors_24h`.

**Por qué**: 5 son suficientes para que el banner muestre el último + el frontend puede listar los 5 si hace falta. Más sería paginación que no necesitamos Phase 1.

## Risks / Trade-offs

1. **Decorator overhead** — un try/except + posible DB INSERT por task. Insignificante vs el costo del task mismo (segundos para SLOW).

2. **DB write durante un error** — si la excepción es por DB down, el INSERT del error también falla. Mitigación: el decorator captura la falla del INSERT y solo loguea a stderr (último recurso). No crashea el wrapper.

3. **Falsos negativos en is_stale** — si el cambio de horario / mercado cerrado por evento extraordinario hace que prices ALSO se atrase, el banner queda silencio. Aceptable Phase 1; agregar `prices_lag_days` después si vemos casos.

4. **Banner overhead frontend** — un fetch cada 60s a un endpoint barato (3 queries SELECT). Marginal.

5. **El operador puede ignorar el banner anyway** — la UI no puede forzar atención. Pero al menos no puede decir "no sabía" — la información está visible.

6. **task_error_tracker depende del DB session estar disponible** — si el decorator se invoca en un contexto sin DB (raro pero posible), el INSERT falla. Mitigación: el decorator abre su propia sesión via `AsyncSessionLocal`.
