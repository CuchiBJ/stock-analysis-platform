## Why

El Live Transitions Feed y Top Actionable Setups muestran el símbolo y el tipo de setup, pero no el precio actual ni la distancia al nivel de entrada. Para operar, el trader necesita saber en qué momento del precio está apareciendo el setup: ¿WULF está testeando EMA9 a $8.50 o a $12? ¿Cuánto falta para llegar al soporte? ¿Cómo viene el día?

Sin esta información, el feed es una lista de nombres — no un panel operativo. Viola Principio 3 (context compression — la narrativa debe incluir lo que el trader necesita para actuar) y Principio 10 (workflow > analytics — el dato de precio es el primero que un trader mira).

## What Changes

**Backend** — `GET /api/v1/transitions/live` y `GET /api/v1/transitions/actionable`: agregar tres campos al response:
- `current_price`: precio actual (close más reciente)
- `change_pct`: cambio del día en % (perf_1w proxy o calculado desde precio anterior)
- `dist_to_setup_pct`: distancia en % al nivel de setup relevante (EMA9 si es entering_pullback con d9 > 0, EMA21 en otros casos)

**Frontend** — `LiveTransitionFeed.tsx` y `TopActionableSetups.tsx`: mostrar los tres campos inline con el símbolo en formato compacto:

```
WULF  entering_pullback          $8.50  +2.1%  −0.8% a EMA21
LITE  entering_pullback          $52.30 −1.2%  −1.5% a EMA9
```

## Capabilities

### New Capabilities
*(ninguna)*

### Modified Capabilities
- `transition-engine`: los endpoints live y actionable exponen precio y distancia al setup.

## Non-goals

- No agregar EMA9/EMA21 en dólares (agregaría demasiado ruido visual — la distancia en % es suficiente).
- No agregar vela o sparkline de precio — ya fue auditado y eliminado por datos falsos.
- No tocar el Quality Swing Scanner (tiene su propia columna de precio).
- No cambiar la estructura del response — solo se agregan campos, sin breaking changes.

## Impact

| Archivo | Cambio |
|---|---|
| `backend/app/api/v1/endpoints/transitions.py` | Agregar `current_price`, `change_pct`, `dist_to_setup_pct` al dict del response en `/live` y `/actionable` |
| `frontend/components/dashboard/LiveTransitionFeed.tsx` | Agregar los 3 campos al type + renderizar inline |
| `frontend/components/dashboard/TopActionableSetups.tsx` | Idem |
