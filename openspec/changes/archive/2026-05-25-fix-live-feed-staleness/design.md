## Context

El endpoint actual usa esta lógica:

```python
cutoff_date = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")

result = await db.execute(
    select(StockMetrics)
    .where(and_(
        StockMetrics.date >= cutoff_date,
        _ACTIONABLE_FILTER,          # EMA trigger zone
    ))
    .order_by(StockMetrics.date.desc())
    .limit(500)
)
```

Esto devuelve hasta 500 rows de los últimos 7 días que pasaron el EMA trigger. Al agrupar por símbolo, `metrics_list[0]` es la row más reciente **de ese símbolo que alguna vez estuvo en zona**, no necesariamente la row de hoy. Un stock que estuvo en zona ayer y hoy rebotó sigue apareciendo.

**Ejemplo concreto (NBIS):**

```
Rows devueltas por la query actual el 21/5:
  20/5  d_ema9=-0.186  ← más reciente con EMA trigger ← "current"
  19/5  d_ema9=0.058
  18/5  d_ema9=0.184

Row de hoy (21/5) NO devuelta porque d_ema9=0.899 > 0.5 (fuera de zona)
→ El feed del 21/5 muestra el estado del 20/5 como si fuera hoy
```

## Goals / Non-Goals

**Goals:**
- El feed solo muestra stocks cuya row MÁS RECIENTE en DB está en zona de trigger
- La dirección (approaching) se sigue calculando comparando current vs el día anterior

**Non-Goals:**
- No cambiar qué stocks califican, solo cuándo aparecen
- No tocar el transition engine

## Decisions

### Decisión 1: Anclar a `MAX(date)` en lugar de `NOW() - N días`

`MAX(date)` es el último día para el que hay métricas calculadas en la DB. Puede ser hoy, o el último día de trading si el scheduler todavía no corrió. Esto es más robusto que `NOW()` porque:
- `NOW()` asume que los datos del día ya están cargados
- `MAX(date)` usa lo que realmente existe, sin asumir

```python
# Step 1: obtener el último día con datos
latest_date_result = await db.execute(
    select(func.max(StockMetrics.date))
)
latest_date = latest_date_result.scalar()
```

### Decisión 2: Ventana de 2 días para retener "previous" metrics

Para calcular `ema9_distance_change` y `ema21_distance_change` se necesita el día anterior. La query debe incluir `latest_date` Y el día anterior.

```python
# Ventana: latest_date y el día previo
result = await db.execute(
    select(StockMetrics)
    .where(and_(
        StockMetrics.date >= prev_date,   # ayer (aprox)
        StockMetrics.date <= latest_date, # hoy
        _INSTITUTIONAL_SETUP,             # quality gates
    ))
    .order_by(StockMetrics.date.desc())
    .limit(1000)
)
```

Luego, al agrupar por símbolo, solo se incluye el símbolo si `metrics_list[0].date == latest_date` Y `metrics_list[0]` pasa el EMA trigger filter. Esto garantiza:
1. "current" siempre es de `latest_date`
2. "previous" es el día anterior (si existe)
3. Stocks sin datos de hoy no aparecen

**Alternativa descartada:** mantener la query de 7 días pero agregar un post-filtro que descarte stocks donde `metrics_list[0].date != latest_date`. Más simple de implementar pero ineficiente — trae 7 días de datos para luego descartar 5.

### Decisión 3: El EMA trigger se evalúa en Python, no en SQL

En lugar de incluir `_ACTIONABLE_FILTER` (que incluye el EMA trigger) en la query SQL, se aplica el EMA trigger en Python al momento de clasificar. Esto permite:
- Query SQL más simple: solo `_INSTITUTIONAL_SETUP` + ventana de fechas
- El EMA trigger se evalúa sobre `metrics_list[0]` (el "current" del día)
- Se mantiene flexibilidad para ajustar thresholds sin tocar la query

```python
def _passes_ema_trigger(metrics: StockMetrics) -> bool:
    ema9 = metrics.distance_to_ema9_atr or 999.0
    ema21 = metrics.distance_to_ema21_atr or 999.0
    return (
        (-1.0 <= ema9 <= 0.5) or
        (-1.0 <= ema21 <= 0.5)
    )
```

## Risks / Trade-offs

**[Riesgo 1: El scheduler no corrió hoy — `MAX(date)` es de ayer]**
→ Aceptado. Si no hay datos de hoy, el feed mostrará el estado de ayer. Es mejor que mostrar datos de 7 días atrás. El usuario sabe que los datos son EOD.

**[Riesgo 2: Ventana de 2 días puede omitir el "previous" si hay un gap de 3+ días (fin de semana)]**
→ Mitigación: calcular `prev_date` como `latest_date - 3 días` (cubre fins de semana y feriados). Si no hay previous, la dirección queda en 0 (default actual).

**[Riesgo 3: Si ningún stock tiene datos del `latest_date` que pasen el trigger, el feed queda vacío]**
→ Aceptado — "No hay setups hoy" es una respuesta válida (Principio 2: Scarcity is signal).
