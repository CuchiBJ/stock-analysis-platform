## ADDED Requirements

### Requirement: Live Transitions Response SHALL Include Price Context Fields

Los endpoints `GET /api/v1/transitions/live` y `GET /api/v1/transitions/actionable` SHALL incluir tres campos adicionales en cada item del response:

| Campo | Tipo | Descripción |
|---|---|---|
| `current_price` | `float \| null` | Precio actual (close más reciente de StockMetrics) |
| `change_pct` | `float \| null` | Cambio del día estimado en % (`perf_1w / 5`, proxy orientativo) |
| `dist_to_setup_pct` | `float \| null` | Distancia en % al EMA de referencia del setup. Negativo = setup debajo del precio, positivo = setup arriba |

**EMA de referencia para `dist_to_setup_pct`:**
- Si `transition == "entering_pullback"` Y `|distance_to_ema9_atr| <= 0.5`: usar EMA9
- En todos los demás casos: usar EMA21

**Implementación:** `backend/app/api/v1/endpoints/transitions.py`, helper `_dist_to_setup_pct()` + campos en `transitions.append({})`

#### Scenario: entering_pullback cerca de EMA9 reporta distancia a EMA9

- **WHEN** el response incluye un item con `transition = "entering_pullback"` y `distance_to_ema9_atr = -0.2`
- **THEN** `dist_to_setup_pct` SHALL ser la distancia porcentual entre el precio actual y el precio de EMA9
- **AND** el valor SHALL ser negativo (EMA9 está debajo del precio actual)

#### Scenario: Campos son null cuando faltan datos

- **WHEN** `current_price` o `atr` son NULL en StockMetrics
- **THEN** `current_price`, `change_pct` y `dist_to_setup_pct` SHALL ser `null`
- **AND** el endpoint SHALL NOT lanzar error

### Requirement: Live Transitions Feed SHALL Display Price Context Inline

`LiveTransitionFeed.tsx` SHALL mostrar `current_price`, `change_pct` y `dist_to_setup_pct` en la misma línea que el símbolo y el tipo de transition, en formato compacto.

**Formato visual:**
```
WULF  entering_pullback    $8.50  +2.1%  −0.8% EMA21
```

- `current_price`: formato `$XXX.XX`, color blanco/neutro
- `change_pct`: verde (`text-green-400`) si positivo, rojo (`text-red-400`) si negativo, prefijo `+`/`−`
- `dist_to_setup_pct`: gris suave (`text-muted-foreground`), sufijo `EMA9` o `EMA21` según corresponda

**Implementación:** `frontend/components/dashboard/LiveTransitionFeed.tsx`

#### Scenario: Precio visible en cada fila del feed

- **WHEN** el feed muestra un setup de `entering_pullback` para WULF a $8.50
- **THEN** SHALL verse `$8.50` en la misma línea que el símbolo, sin ocupar una fila extra

#### Scenario: Cambio positivo en verde, negativo en rojo

- **WHEN** `change_pct = 2.1`
- **THEN** SHALL renderizar `+2.1%` en `text-green-400`
- **WHEN** `change_pct = -1.2`
- **THEN** SHALL renderizar `−1.2%` en `text-red-400`

#### Scenario: Campos null se omiten silenciosamente

- **WHEN** `current_price` es `null`
- **THEN** el componente SHALL NOT renderizar nada en lugar del precio (sin "-" ni "N/A")

### Requirement: Top Actionable Setups SHALL Display Price Context Inline

`TopActionableSetups.tsx` SHALL mostrar los mismos tres campos con el mismo formato visual que `LiveTransitionFeed`.

**Implementación:** `frontend/components/dashboard/TopActionableSetups.tsx`

#### Scenario: Precio visible en cada card de setup

- **WHEN** Top Actionable muestra un setup para VRT a $334
- **THEN** SHALL verse `$334.02` con su `change_pct` y `dist_to_setup_pct` en la misma línea del símbolo
