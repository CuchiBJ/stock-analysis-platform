## Context

Loop actual (cada 30 segundos):
```python
# tick 1: last_price_update is None → dispara ambos
asyncio.create_task(self._update_prices())   # background, ~3 min
await self.trigger_fast_metrics_update()      # inmediato, usa precios viejos ← BUG

# tick 2 (30s después): price update sigue corriendo en background
# fast metrics no dispara (300s no pasaron)

# tick 7 (~3.5 min): price update termina, nadie lo sabe
# tick 10 (~5 min): FAST metrics dispara, AHORA sí tiene precios nuevos
```

Hay tres ciclos independientes (precio, FAST, SLOW) sin coordinación, con dos problemas adicionales: el SLOW solo cubre 3125 símbolos y el SLOW puede correr concurrente con FAST sobreescribiendo métricas frescas con métricas calculadas con precios viejos.

## Goals / Non-Goals

**Goals:**
- Métricas siempre usan los precios más recientes disponibles.
- SLOW cycle nunca deja símbolos con precios frescos pero métricas viejas.
- Loop arranca rápido (≤5 min) sin esperar el SLOW inicial completo.
- SLOW no sobreescribe métricas más nuevas escritas por FAST mientras corría.

**Non-Goals:**
- No cambiar frecuencias (precios 15 min, FAST 5 min, SLOW 30 min).
- No tocar `_run_realtime_discovery()` — sigue como `create_task`. Justificación: no escribe métricas, solo detecta candidatos de discovery. Sus race conditions no afectan el feed operativo.
- No paralelizar el cálculo de métricas (sigue siendo serial async loop).

## Decisions

### Decisión 1: Price update pasa de `create_task` a `await`

```python
# ANTES
asyncio.create_task(self._update_prices())

# DESPUÉS
try:
    await self._update_prices()
except Exception as e:
    logger.error(f"Price update failed (continuing): {e}")
```

El loop se bloquea ~3 min durante el price update. Esto es aceptable porque:
- El loop solo hace time-checking cada 30s.
- `_update_prices` ya corre `_bulk_download_prices_sync` en `run_in_executor` (thread pool), por lo que no bloquea el event loop a nivel de asyncio.
- El FAST metrics inmediatamente después usa precios frescos.

### Decisión 2: FAST metrics encadenado inmediatamente tras price update

```python
if last_price_update is None or (now - last_price_update).total_seconds() >= 900:
    logger.info("Triggering price update")
    try:
        await self._update_prices()
    except Exception as e:
        logger.error(f"Price update failed (continuing): {e}")
    last_price_update = now
    # Forzar FAST metrics inmediatamente con precios frescos
    await self.trigger_fast_metrics_update()
    last_fast_metrics_update = now
    continue  # saltar resto del tick
```

### Decisión 3: SLOW cycle dinámico por precios de hoy + write-protection

```python
async def _get_slow_symbols_and_date(self, db) -> tuple[list[str], str | None]:
    """Returns (symbols_with_price_today, snapshot_date).
    Snapshot date is captured at start; SLOW only writes for symbols
    that don't already have a metrics row >= snapshot_date.
    """
    from sqlalchemy import select, func
    from app.models.stock import StockPrice
    today = (await db.execute(select(func.max(StockPrice.date)))).scalar()
    if not today:
        return [], None
    result = await db.execute(
        select(StockPrice.symbol).where(StockPrice.date == today).distinct()
    )
    symbols = [r[0] for r in result.fetchall()]
    logger.info(f"SLOW cycle: {len(symbols)} symbols with price for {today}")
    return symbols, str(today)
```

**Write-protection contra race condition**: en `trigger_metrics_update`, antes de procesar cada símbolo, verificar si ya existe una métrica para esa fecha snapshot. Si existe (porque FAST la actualizó después), saltar.

```python
async def trigger_metrics_update(self, limit=None, symbols=None):
    if self._slow_running:
        logger.info("SLOW cycle still running — skipping")
        return 0
    self._slow_running = True
    try:
        async with self._get_db() as db:
            if symbols is None:
                symbols, snapshot_date = await self._get_slow_symbols_and_date(db)
            else:
                snapshot_date = None
            if limit:  # backward compat con metrics.py endpoint
                symbols = symbols[:limit]
            
            calculator = MetricsCalculator(db)
            count = 0
            for sym in symbols:
                # Write protection: skip if a newer (FAST) metric already exists
                if snapshot_date:
                    existing = await db.execute(
                        select(StockMetrics.date).where(
                            StockMetrics.symbol == sym,
                            StockMetrics.date >= snapshot_date,
                        ).limit(1)
                    )
                    if existing.scalar():
                        continue
                try:
                    await calculator.calculate_metrics_for_symbol(sym)
                    count += 1
                except Exception:
                    continue
            logger.info(f"SLOW metrics calculated for {count} symbols")
        return count
    finally:
        self._slow_running = False
```

### Decisión 4: Backward-compatible API en `trigger_metrics_update`

Firma actual: `(self, limit=100)`. Caller externo en `metrics.py:15` usa `limit`. Nueva firma:

```python
async def trigger_metrics_update(self, limit=None, symbols=None):
```

- Si `symbols` provisto → ignora `limit`, procesa esa lista.
- Si solo `limit` → backward compat: trae top N símbolos.
- Si nada → usa `_get_slow_symbols_and_date()` (caso del loop).

### Decisión 5: Startup con loop arrancando rápido

**Problema**: con 6718 símbolos el SLOW inicial tarda 25-30 min. Si lo esperamos antes del loop, el FAST cycle no corre durante ese tiempo.

**Solución**: arrancar el SLOW inicial como `create_task` (sí, en background) y entrar al loop inmediatamente. El loop disparará price updates y FAST cycles mientras el SLOW inicial termina. El flag `_slow_running` previene que se solape con el primer SLOW programado.

```python
# Startup
logger.info("Startup: fetching fresh prices first")
try:
    await self._update_prices()
except Exception as e:
    logger.error(f"Startup price update failed: {e}")
last_price_update = datetime.now(et_tz)  # FIX: evita doble download en primer tick

logger.info("Startup: initial SLOW metrics calculation (background)")
asyncio.create_task(self.trigger_metrics_update())
last_metrics_update = datetime.now(et_tz)  # marca como recién iniciado

# Loop inicia aquí — FAST cycles arrancan en ≤5 min
```

El initial SLOW como `create_task` es la única excepción a "no usar create_task" porque es la única forma de no bloquear el arranque. El `_slow_running` flag garantiza que ningún otro SLOW se solape.

## Risks / Trade-offs

**[Riesgo 1: write-protection skip puede dejar métricas SLOW menos completas]**
→ Aceptado. Si FAST escribió métricas para un símbolo durante el SLOW, esas métricas son MÁS frescas que las que el SLOW iba a escribir (con precios del snapshot). Skipear es correcto.

**[Riesgo 2: SLOW puede tardar >30 min con 6718 símbolos]**
→ Aceptado. El flag previene solapamiento. Efectivamente corre cada 30-40 min en lugar de cada 30. Aceptable porque FAST cubre el universo operativo (300 símbolos) cada 5 min.

**[Riesgo 3: Initial SLOW como background contradice "encadenado"]**
→ Excepción justificada: si lo esperamos al startup, el loop tarda 30+ min en arrancar. La write-protection garantiza consistencia aunque corra en paralelo con el primer FAST.

**[Riesgo 4: realtime_discovery sigue con create_task — fuera del scope]**
→ Aceptado. No escribe métricas, solo detecta candidatos.

## Migration Plan

1. Agregar `_get_slow_symbols_and_date()` y `_slow_running = False` en `__init__`.
2. Modificar `trigger_metrics_update` con firma backward-compatible + write-protection.
3. Modificar `_scheduler_loop` con price await + FAST chained + continue.
4. Modificar startup: price first → `last_price_update = now` → SLOW como create_task.
5. Reiniciar scheduler y verificar log secuencia.
