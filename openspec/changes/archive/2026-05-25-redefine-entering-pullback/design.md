## Context

La detección actual en `_determine_operational_transition()` (línea 663):

```python
# Actual — dispara cuando ya cruzó
if (prev_ema21_atr > 0 and ema21 < 0 and ema50 > -0.5):
    return ENTERING_PULLBACK
```

Problema doble: semántica incorrecta (cruce ya ocurrido, tarde para preparar entrada) y ausencia de quality gates (cualquier stock califica).

**Validación contra datos reales:**

| Stock | Resultado actual | Resultado esperado | Motivo |
|---|---|---|---|
| LUNR  | ✅ aparece | ✅ debe aparecer | d_ema9=0.011, disminuyendo, todos los gates OK |
| TER   | ✅ aparece | ❌ debe filtrarse | cruza EMA21 hacia arriba (dirección incorrecta) |
| FN    | ✅ aparece | ❌ debe filtrarse | ya rebotó, distancia aumentando |
| SGML  | ✅ aparece | ❌ debe filtrarse | debajo de EMA50 |
| CLS   | ✅ aparece | ❌ debe filtrarse | debajo de EMA50 |

## Goals / Non-Goals

**Goals:**
- Solo líderes Minervini aparecen como ENTERING_PULLBACK
- La señal llega antes del cruce (preparación de entrada, no reacción)
- El feed distingue testing EMA9 vs EMA21 en la narrativa

**Non-Goals:**
- No tocar otros transitions
- No agregar columnas a stock_metrics

## Decisions

### Decisión 1: Quality gates dentro de `_determine_operational_transition()`, no como pre-filtro separado

Los gates se evalúan inline dentro de la condición ENTERING_PULLBACK usando `current_metrics` que ya está disponible. No se necesita un servicio nuevo.

```python
def _is_quality_leader(self, m: StockMetrics) -> bool:
    """Minervini SEPA quality gates — todos deben cumplirse."""
    if not all([m.perf_1y, m.ema200, m.current_price, m.sma50,
                m.sma150, m.high_52w, m.low_52w, m.adr_percent]):
        return False
    range_52w_pct = (m.high_52w - m.low_52w) / m.low_52w
    price_above_low_pct = (m.current_price - m.low_52w) / m.low_52w
    return (
        m.perf_1y > 30.0 and
        m.current_price > m.ema200 and
        (m.distance_to_ema50_atr or 0) > 0 and
        m.sma50 > m.sma150 and
        range_52w_pct >= 0.60 and
        price_above_low_pct >= 0.70 and
        m.adr_percent >= 3.0
    )
```

**Alternativa descartada:** pre-filtrar el universo en el endpoint antes de llamar al engine. Más limpio arquitectónicamente pero rompe el principio de que el engine es quien determina el tipo de transición.

### Decisión 2: Proximidad ATR-normalizada con umbral diferenciado por EMA

```
EMA9:  0 < distance_to_ema9_atr  ≤ 0.5   (ventana chica — EMA9 se mueve rápido)
EMA21: 0 < distance_to_ema21_atr ≤ 1.0   (ventana más amplia — EMA21 es el soporte clásico)
```

Justificación empírica: de los stocks activos con perf_1y > 30% y adr > 3%, los que genuinamente testean su EMA están en el rango 0.0–0.03 ATR de EMA21. El umbral de 1.0 ATR da margen para detectar la aproximación un día antes del test real.

### Decisión 3: Filtro de dirección usando `ema21_distance_change` ya calculado

`ema21_distance_change` se calcula en líneas 187–190 de `transition_engine.py` y ya está disponible como argumento en `_determine_operational_transition()`. No se necesita cálculo adicional.

```python
# Approaching EMA21 from above, distance decreasing
approaching_ema21 = (
    0 < ema21 <= 1.0 and
    ema21_distance_change < 0          # acercándose, no alejándose
)

# Para EMA9: calcular ema9_distance_change igual que ema21_distance_change
approaching_ema9 = (
    0 < ema9_atr <= 0.5 and
    ema9_distance_change < 0
)
```

`ema9_distance_change` requiere agregar su cálculo junto al de EMA21 (actualmente solo se calcula EMA21). Cálculo idéntico pero usando `distance_to_ema9_atr`.

### Decisión 4: EMA9 tiene prioridad sobre EMA21 si ambas se cumplen

Un stock puede estar simultáneamente cerca de EMA9 Y de EMA21 (pullback profundo). En ese caso, EMA9 es más informativo operacionalmente — el stock está testeando el soporte más cercano primero.

### Decisión 5: Narrativa específica por EMA en `_generate_operational_narrative()`

El dict de narrativas actual devuelve una sola cadena por transition type. Se pasa el EMA target como contexto adicional vía el método `_generate_operational_narrative()`.

## Risks / Trade-offs

**[Riesgo 1: Con quality gates estrictos, ENTERING_PULLBACK puede aparecer 0 veces en días de mercado débil]**
→ Aceptado — Principio 2 (Scarcity is signal). "No hay setups hoy" es una respuesta válida.

**[Riesgo 2: `ema200` puede ser NULL para stocks sin suficiente historia]**
→ Mitigación: el helper `_is_quality_leader()` retorna `False` si cualquier campo requerido es None.

**[Riesgo 3: `ema9_distance_change` no existe actualmente — requiere calcular diferencia de `distance_to_ema9_atr` entre current y previous metrics]**
→ Mitigación: agregar el cálculo en `calculate_operational_transition()` junto a `ema21_distance_change`, mismo patrón, 2 líneas.

## Migration Plan

No hay migración de datos. El cambio es puramente lógico en el engine. El endpoint responde igual. Los stocks que antes disparaban ENTERING_PULLBACK incorrectamente pasarán a ser STABLE u otro tipo — no hay pérdida de datos.
