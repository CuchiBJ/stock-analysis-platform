## Why

El ciclo de price update del scheduler (`_bulk_download_prices_sync`) produce ~175-200 fallos por batch en cada corrida de 15 minutos. Tres causas raíz combinadas:

1. **771 warrants/units/rights** (`XXXW`, `XXXU`, `XXXR`) están en el universo activo y se incluyen en cada download. Yahoo Finance no tiene datos para estos símbolos — generan errores por diseño, consumen cuota de rate limit, y contribuyen al DNS thread exhaustion.

2. **TypeError silencioso en ~600 tickers válidos** (JPM, JNJ, UBER, DELL, BA, etc.): cuando `yf.download(batch, ...)` retorna un MultiIndex sin el símbolo (porque Yahoo no lo incluyó en esa respuesta), `data.xs(symbol, axis=1, level=1)` lanza `TypeError: 'NoneType' object is not subscriptable`. El `try/except` genérico captura el error pero **no actualiza el precio de ese símbolo**. Resultado: tickers institucionales con precios desactualizados.

3. **DNS thread exhaustion**: `yf.download(..., threads=True)` con batches de 200 crea demasiados threads simultáneos, agotando el pool de DNS resolution. La solución es reducir `threads=False` o usar batches más pequeños.

Viola Principio 7 (interpretabilidad — los datos de precio son el input básico de todas las métricas) y Principio 9 (señal institucional — stocks como JPM/JNJ/UBER con precios desactualizados distorsionan RS, ATR y transitions).

## What Changes

- **Filtrar símbolos no-descargables** antes del bulk download: excluir warrants (`*W`), units (`*U`), rights (`*R`) de 5+ chars, y símbolos con prefijo `$`.
- **Fix TypeError en multi-index**: reemplazar `data.xs(symbol, ...)` con un check explícito `if symbol not in data.columns.get_level_values(1): continue` antes del xs.
- **Reducir threads en yfinance**: pasar `threads=False` para evitar DNS exhaustion. El costo es velocidad, pero el download ya corre en un thread pool (`run_in_executor`), por lo que el event loop no se bloquea igual.
- **Loggear símbolos excluidos** (una vez, al arrancar) para tener visibilidad del universo limpio.

## Capabilities

### New Capabilities
*(ninguna)*

### Modified Capabilities

- `universe-management`: el Requirement de universe contamination (BUG #7 de auditoría) se mitiga parcialmente — los warrants/units siguen en la DB pero se excluyen del download. Un cleanup completo de la tabla es trabajo separado.

## Non-goals

- No eliminar warrants/units de la DB — eso requiere auditoria de foreign keys y es un change separado.
- No cambiar la frecuencia del price update (sigue siendo cada 15 min).
- No migrar de yfinance a Polygon para prices — decisión de data source separada.
- No agregar retry logic para rate limits — el scheduler ya tiene un ciclo de 15 min que actúa como retry natural.

## Impact

| Archivo | Cambio |
|---|---|
| `backend/app/data/scheduler.py` | Método `_bulk_download_prices_sync`: filtrar símbolos, fix TypeError, `threads=False` |

Sin migración, sin schema, sin frontend. El fix es puramente en la lógica del download loop.
