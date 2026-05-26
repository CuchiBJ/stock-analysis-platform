## Context

`trigger_fast_metrics_update()` actual:
```python
tier_query = select(UniverseTierModel).where(UniverseTierModel.tier == "tier_1")
tier_result = await db.execute(tier_query)
tier1_symbols = [r.instrument_id for r in tier_result.scalars().all()]
# → calcula métricas para tier1_symbols[:200]
```

Esto hardcodea el universo del FAST cycle a TIER 1. Si WULF, LITE, HUT están en TIER 2 o sin tier, sus métricas se actualizan solo en el SLOW cycle (30 min). El feed puede mostrar setups de hace 40-60 minutos.

## Goals / Non-Goals

**Goals:**
- Stocks en el feed operativo siempre tienen métricas con <= 5 min de latencia.
- La lista dinámica se recalcula en cada ciclo — si un stock sale del feed, deja de recibir FAST updates automáticamente.

**Non-Goals:**
- No tocar SLOW cycle.
- No cambiar el límite de 200 símbolos por ciclo FAST (subirlo levemente a ~300 para absorber los adicionales sin degradar performance).

## Decisions

### Decisión 1: Query de institutional stocks en el FAST cycle

```python
async def _get_fast_symbols(self, db: AsyncSession) -> list[str]:
    """TIER 1 + stocks passing institutional quality gates (live transitions candidates)."""
    from sqlalchemy import select, and_
    from app.models.stock import StockMetrics
    from app.models.universe import UniverseTier as UniverseTierModel
    from sqlalchemy import func

    # TIER 1 base
    tier_result = await db.execute(
        select(UniverseTierModel).where(UniverseTierModel.tier == "tier_1")
    )
    tier1_ids = {r.instrument_id for r in tier_result.scalars().all()}

    # Institutional quality stocks (same gates as live transitions endpoint)
    latest_date = (await db.execute(select(func.max(StockMetrics.date)))).scalar()
    inst_result = await db.execute(
        select(StockMetrics.symbol)
        .where(and_(
            StockMetrics.date == latest_date,
            StockMetrics.avg_volume_10d >= 800_000,
            StockMetrics.adr_percent >= 3.0,           # slightly relaxed vs feed (4%)
            StockMetrics.current_price >= 5.0,
            StockMetrics.perf_1y > 25,                 # slightly relaxed vs feed (30%)
            StockMetrics.current_price > StockMetrics.ema50,
            StockMetrics.current_price > StockMetrics.sma150,
            StockMetrics.sma150 > StockMetrics.sma200,
        ))
        .limit(200)
    )
    inst_symbols = {r[0] for r in inst_result.fetchall()}

    # Union: TIER 1 instrument_ids resolved to symbols + institutional symbols
    # For simplicity, resolve TIER 1 via stock_metrics (latest date)
    tier1_result = await db.execute(
        select(StockMetrics.symbol)
        .where(and_(
            StockMetrics.date == latest_date,
            StockMetrics.symbol.in_(
                select(UniverseTierModel.instrument_id)
                .where(UniverseTierModel.tier == "tier_1")
            )
        ))
        .limit(200)
    )
    tier1_symbols = {r[0] for r in tier1_result.fetchall()}

    combined = list(tier1_symbols | inst_symbols)
    logger.info(f"FAST cycle: {len(tier1_symbols)} TIER 1 + {len(inst_symbols)} institutional = {len(combined)} unique symbols")
    return combined
```

**Thresholds ligeramente relajados** (adr >= 3% en vez de 4%, perf > 25% en vez de 30%) para capturar stocks que están en proceso de calificarse pero aún no pasan todos los gates del feed — así el FAST los prepara para cuando sí califiquen.

### Decisión 2: Límite de 300 símbolos en vez de 200

El FAST cycle actual limita a `tier1_symbols[:200]`. Con la expansión dinámica, el combined puede llegar a ~300-350. Se sube el límite a 300 para absorberlo sin degradar el ciclo de 5 minutos significativamente.

A ~0.1-0.3s por símbolo en el FAST (solo 10 días de datos), 300 símbolos ≈ 30-90s por ciclo. Dentro del margen de 5 min.

### Decisión 3: No usar la query exacta de live transitions

La query de `transitions/live` tiene múltiples pasos (freshness gate, EMA trigger en Python, etc.) y es cara. En su lugar usamos la query SQL de `_INSTITUTIONAL_SETUP` como proxy — es más simple y captura el universo correcto.

## Risks / Trade-offs

**[Riesgo 1: El FAST cycle tarda más de 5 min con 300 símbolos]**
→ Si ocurre, bajar el límite a 250 o reducir `days=10` a `days=5` para el FAST.

**[Riesgo 2: latest_date puede no tener datos de institutional stocks (parcial del día)]**
→ Fallback: si la query institutional devuelve < 10 resultados, usar solo TIER 1.

**[Riesgo 3: UniverseTierModel.instrument_id no es el símbolo directamente]**
→ La query de TIER 1 ya maneja esto via join con StockMetrics.

## Migration Plan

1. Extraer lógica de symbols en `_get_fast_symbols()` helper.
2. Reemplazar el bloque de tier_query en `trigger_fast_metrics_update()` por llamada al helper.
3. Subir límite de `[:200]` a `[:300]`.
4. Verificar log: debe mostrar "FAST cycle: X TIER 1 + Y institutional = Z unique symbols".
5. Verificar que stocks del feed tienen métricas con timestamp < 5 min.

Rollback: revertir `trigger_fast_metrics_update()` al código original.
