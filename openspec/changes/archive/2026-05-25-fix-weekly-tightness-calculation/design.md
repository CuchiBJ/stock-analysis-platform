## Context

`weekly_tightness` se calcula en `MetricsCalculator._calculate_weekly_tightness()` con la fórmula:

```python
weekly['range_pct'] = (weekly['high'] - weekly['low']) / weekly['close'] * 100
recent_tightness = weekly['range_pct'].tail(4).mean()
return 1.0 / (1.0 + recent_tightness)
```

**Bug 1 — Sin filtro de volumen:**
Stocks inactivos tienen `high == low == close` en semanas sin trades → `range_pct = 0` → `tightness = 1/(1+0) = 1.0`. El stock más ilíquido parece el más "tight".

**Bug 2 — Normalización por precio en vez de ATR:**
Un stock de $900 (LITE) con rango semanal de $63 obtiene `range_pct = 7%` → `tightness = 0.125`. Pero ese mismo rango en unidades ATR puede ser 1.4 ATR — que es exactamente el rango de un stock en base sana. La fórmula es ciego a la volatilidad intrínseca del stock.

**Por qué los thresholds existentes son correctos para ATR-norm:**
Con la fórmula corregida, un stock en base muy tight tiene rango semanal ≈ 0.5 ATR → `tightness = 1/(1+0.5) = 0.67` → "good" por los thresholds del sistema. Un stock en base normal tiene rango ≈ 1.0 ATR → `tightness = 0.5`. Un stock suelto tiene ≈ 2.0 ATR → `tightness = 0.33`. Esto mapea exactamente a los cortes `>= 0.6`, `>= 0.4`, `>= 0.3` que ya existen en 10+ servicios.

## Goals / Non-Goals

**Goals:**
- Stocks inactivos (volumen cero) retornan `weekly_tightness = 0.0`
- Stocks institucionales en base tight obtienen scores en el rango 0.5–0.8
- El scanner con threshold `> 0.3` devuelve stocks reales

**Non-Goals:**
- No alterar thresholds en servicios consumidores
- No tocar el esquema de DB

## Decisions

### Decisión 1: ATR diario como denominador, no ATR semanal

Se calcula el ATR de 14 días desde el DataFrame diario ya disponible en `_calculate_weekly_tightness(df)`. El ATR semanal requeriría calcular true range sobre barras semanales, que tiene menos muestras y más ruido en el corto plazo.

```python
# ATR diario de los últimos 14 días
df['prev_close'] = df['close'].shift(1)
df['tr'] = (df['high'] - df['low']).combine(
    (df['high'] - df['prev_close']).abs(), max
).combine(
    (df['low'] - df['prev_close']).abs(), max
)
daily_atr = df['tr'].tail(14).mean()
```

Alternativa descartada: rango semanal / precio — ya demostrado que produce resultados invertidos.

### Decisión 2: Mínimo 3 semanas activas en las últimas 4

Si un stock tiene datos de precio pero pocas semanas con volumen real (posible en nombres ilíquidos que sí tienen precio de mercado), retornar `0.0` en lugar de un score artificialmente alto. El threshold de 3/4 semanas es conservador pero evita el caso borde.

### Decisión 3: Restaurar threshold del scanner a `> 0.3` post-recalculación

Con la nueva fórmula, `> 0.3` corresponde a stocks con rango semanal < 2.33 ATRs — rango razonable para bases institucionales. El parche de emergencia `> 0.02` se revierte.

## Risks / Trade-offs

**[Riesgo 1: ATR = 0 en stocks con datos de precio congelados]**
→ Mitigación: Si `daily_atr == 0`, retornar `0.0` directamente (mismo caso que volumen cero).

**[Riesgo 2: La recalculación cambia scores de 33k+ rows — downstream scoring puede cambiar notablemente]**
→ Mitigación: El cambio mejora la señal, es intencional. Los servicios consumidores ya están diseñados para el rango 0–1 que producirá la nueva fórmula.

**[Riesgo 3: Script de recalculación puede tardar varios minutos]**
→ Mitigación: El script existente `recalculate_metrics_with_atr.py` ya corre en batches. No requiere intervención nueva.

## Migration Plan

1. Aplicar el fix de código (sin cambio de schema)
2. Verificar localmente con un stock de prueba (LITE, NOK)
3. Correr `python scripts/recalculate_metrics_with_atr.py` para repopular
4. Confirmar con query DB que LITE obtiene `weekly_tightness` en rango 0.4–0.7
5. Verificar que el scanner con defaults devuelve resultados

Rollback: revertir el commit de `metrics_calculator.py` y volver a correr el script.

## Open Questions

*(ninguna)*
