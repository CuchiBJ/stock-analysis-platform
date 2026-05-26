## Context

`_bulk_download_prices_sync` en `scheduler.py` corre en un thread pool (`run_in_executor`) y descarga precios para todos los símbolos activos en batches de 200 con `yf.download(..., threads=True)`.

Código actual (problemático):
```python
data = yf.download(batch, period="5d", auto_adjust=True, progress=False, threads=True)
multi = isinstance(data.columns, pd.MultiIndex)
for symbol in batch:
    try:
        hist = data.xs(symbol, axis=1, level=1) if multi else data
        hist = hist.dropna(subset=["Close"])
        ...
    except Exception:
        continue   # ← silencia el TypeError, símbolo queda sin actualizar
```

Tres fallos en cascada:
1. Los 771 warrants/units en el batch fuerzan requests a Yahoo que siempre fallan → consumen cuota.
2. Cuando Yahoo omite un símbolo del MultiIndex resultado, `data.xs()` lanza TypeError → `continue` silencia el error, el símbolo queda sin precio.
3. `threads=True` en yf.download crea un thread por símbolo → 200 threads simultáneos → DNS thread pool exhaustion en macOS.

## Goals / Non-Goals

**Goals:**
- Eliminar los 771 warrants/units del download sin tocar la DB.
- Fix explícito del TypeError — loggear símbolo fallido, no silenciarlo.
- Reducir threads para evitar DNS exhaustion en el batch síncrono.

**Non-Goals:**
- Limpiar warrants/units de la DB (change separado).
- Cambiar batching strategy o frecuencia.
- Retry logic para rate limits.

## Decisions

### Decisión 1: Filtrar warrants en memoria antes del download

Patrón de exclusión:
```python
_SKIP_SUFFIXES = ('W', 'U', 'R')

def _is_downloadable(symbol: str) -> bool:
    if symbol.startswith('$'):
        return False
    # 5-char symbols ending in W/U/R are warrants, units, rights
    if len(symbol) == 5 and symbol[-1] in _SKIP_SUFFIXES:
        return False
    return True
```

Se aplica una vez al inicio de `_bulk_download_prices_sync`, antes de armar los batches. Los símbolos excluidos se loggean como INFO al arrancar (una vez).

**Alternativa descartada: filtrar en la query SQL que trae los símbolos**
- Pro: más limpio.
- Contra: requiere tocar `get_active_symbols()` que es shared con otras partes del scheduler. El filtro local es más cirúrgico y no afecta otras features.

### Decisión 2: Check explícito del MultiIndex antes de xs()

```python
if multi:
    if symbol not in data.columns.get_level_values(1):
        logger.debug(f"Symbol {symbol} not in yfinance response — skipping")
        continue
    hist = data.xs(symbol, axis=1, level=1)
else:
    hist = data
```

Evita el TypeError completamente. El símbolo se logea como DEBUG (no ERROR) porque es esperado que algunos tickers no estén en la respuesta (Yahoo silently drops them sometimes).

### Decisión 3: threads=False en yf.download

```python
data = yf.download(
    batch, period="5d", auto_adjust=True,
    progress=False, threads=False   # evita DNS exhaustion
)
```

El batch ya corre dentro de `run_in_executor` (thread pool del event loop), por lo que no bloquea el async event loop. El costo es ~2-3x más lento por batch, pero elimina los `getaddrinfo() thread failed` completamente.

**Alternativa considerada: reducir batch size de 200 a 50**
- Reduciría DNS pressure sin eliminar threads=True.
- Descartado: 7000 símbolos / 50 = 140 batches → 140 llamadas a Yahoo en 15 min → más rate limiting.

### Decisión 4: Log símbolos excluidos como INFO al inicio

```python
excluded = [s for s in symbols if not _is_downloadable(s)]
logger.info(f"Price download: excluding {len(excluded)} non-downloadable symbols (warrants/units/rights)")
symbols = [s for s in symbols if _is_downloadable(s)]
```

Un solo log al inicio de cada ciclo de 15 min, no por símbolo. Visibilidad sin ruido.

## Risks / Trade-offs

**[Riesgo 1: Símbolo válido con 5 chars terminando en W/U/R queda excluido]**
→ Ejemplos: `LENB` (no, 4 chars), `BRKB` (no, falla igual con Yahoo). Los symbols 5-char W/U/R son casi universalmente warrants. El riesgo es bajo: si algún legítimo se excluye, se detecta porque nunca tiene precio en DB.

**[Riesgo 2: threads=False hace el download 2-3x más lento]**
→ Aceptado. El download ya corre en background como asyncio task. El mercado no siente el delay de 5 min extra en el bulk sync.

**[Riesgo 3: yfinance silently drops symbols en batches grandes incluso con threads=False]**
→ El check de MultiIndex lo maneja. Los símbolos no presentes se loggean y se saltan limpiamente.

## Migration Plan

1. Agregar helper `_is_downloadable()` en `scheduler.py`.
2. Filtrar `symbols` antes de armar batches en `_bulk_download_prices_sync`.
3. Agregar check MultiIndex antes de `data.xs()`.
4. Cambiar `threads=True` → `threads=False`.
5. Verificar log del siguiente ciclo de price update — debe haber 0 TypeErrors y 0 DNS failures.
6. Confirmar que tickers como JPM, JNJ, UBER tienen `stock_prices` actualizados.

Rollback: revertir las 3 modificaciones en `_bulk_download_prices_sync`. Sin DB changes.

## Open Questions

*(ninguna)*
