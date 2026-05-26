## Context

El response actual de `/live` tiene: `symbol`, `transition`, `direction`, `strength`, `observation_priority`, `is_pre_reclaim`, `timestamp`, `narrative`, `severity`, `rs_change`, `volume_change_pct`.

Los datos de precio están disponibles en `current` (`StockMetrics`): `current_price`, `perf_1w`, `ema9`, `ema21`, `distance_to_ema9_atr`, `distance_to_ema21_atr`, `atr`.

## Goals / Non-Goals

**Goals:** Precio, cambio del día, y distancia al setup en % disponibles en el response y visibles inline en el feed.

**Non-Goals:** No agregar EMAs en dólares, no agregar sparklines, no breaking changes en el response.

## Decisions

### Decisión 1: `change_pct` usa `perf_1w` / 5 como proxy del día

`StockMetrics` no tiene `perf_1d` directamente. Opciones:
- **`perf_1w / 5`** (elegida): proxy rápido del promedio diario de la semana. No es exacto pero es orientativo y no requiere queries adicionales.
- **Calcular desde precios anteriores**: requeriría un segundo query a `stock_prices`. Demasiado costoso por símbolo.
- **`perf_1w` directo**: confunde — es el cambio semanal, no diario.

Nota: en el futuro el scheduler puede calcular `perf_1d` y persistirlo. Por ahora el proxy es suficiente para contexto operativo.

### Decisión 2: `dist_to_setup_pct` — distancia al EMA relevante en %

Lógica de selección del EMA de referencia:
```python
def _dist_to_setup_pct(metrics: StockMetrics, transition: str) -> float | None:
    price = metrics.current_price
    if not price:
        return None
    # Para entering_pullback con EMA9 en zona: usar EMA9
    d9 = metrics.distance_to_ema9_atr
    d21 = metrics.distance_to_ema21_atr
    atr = metrics.atr or 0
    if transition == 'entering_pullback' and d9 is not None and -0.5 <= d9 <= 0.5:
        ema9_price = price - (d9 * atr)
        return round((ema9_price - price) / price * 100, 1)
    elif d21 is not None:
        ema21_price = price - (d21 * atr)
        return round((ema21_price - price) / price * 100, 1)
    return None
```

Un valor negativo = el setup está debajo del precio actual (stock sobre la EMA).
Un valor positivo = el setup está arriba (stock bajo la EMA, alejándose).

### Decisión 3: Visual — inline con símbolo, tres chips

```
WULF  entering_pullback    $8.50  +2.1%  −0.8% EMA21
```

- Precio: blanco/gris, monospace
- Change_pct: verde si positivo, rojo si negativo
- Dist_to_setup: gris suave — contexto, no señal

No agregar íconos ni labels verbosos — el trader sabe qué significa cada número en contexto.

## Risks / Trade-offs

**[Riesgo 1: `change_pct` = `perf_1w / 5` es impreciso]**
→ Aceptado. Es orientativo. Si el usuario necesita el dato exacto, lo ve en su broker. El propósito aquí es contexto, no precisión.

**[Riesgo 2: `dist_to_setup_pct` puede ser 0.0% si el stock está exactamente en la EMA]**
→ Mostrar "0.0% EMA" es informativo — el stock está testeando el nivel ahora mismo.

**[Riesgo 3: Para `continuation_holding` el EMA relevante es EMA21, no EMA9]**
→ Cubierto: la lógica de selección prioriza EMA9 solo para `entering_pullback`. El resto usa EMA21 por defecto.
