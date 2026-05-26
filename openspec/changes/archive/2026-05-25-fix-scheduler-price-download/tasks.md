## 1. Agregar helper _is_downloadable() [universe-management]

- [ ] 1.1 En `backend/app/data/scheduler.py`, agregar a nivel de módulo antes de la clase `DataScheduler`:
  ```python
  _SKIP_SUFFIXES = frozenset({'W', 'U', 'R'})

  def _is_downloadable(symbol: str) -> bool:
      """Return False for warrants (XXXW), units (XXXU), rights (XXXR) and $ prefixes."""
      if symbol.startswith('$'):
          return False
      if len(symbol) == 5 and symbol[-1] in _SKIP_SUFFIXES:
          return False
      return True
  ```

## 2. Filtrar símbolos antes de armar batches [universe-management]

- [ ] 2.1 En `_bulk_download_prices_sync`, agregar filtro al inicio del método, antes del loop de batches:
  ```python
  excluded = [s for s in symbols if not _is_downloadable(s)]
  if excluded:
      logger.info(f"Price download: excluding {len(excluded)} non-downloadable symbols (warrants/units/rights)")
  symbols = [s for s in symbols if _is_downloadable(s)]
  ```

## 3. Fix TypeError en MultiIndex [universe-management]

- [ ] 3.1 En el loop interno del batch, reemplazar:
  ```python
  hist = data.xs(symbol, axis=1, level=1) if multi else data
  ```
  por:
  ```python
  if multi:
      if symbol not in data.columns.get_level_values(1):
          logger.debug(f"Symbol {symbol} not in yfinance response — skipping")
          continue
      hist = data.xs(symbol, axis=1, level=1)
  else:
      hist = data
  ```

## 4. Cambiar threads=True → threads=False [universe-management]

- [ ] 4.1 En la llamada a `yf.download`, cambiar:
  ```python
  data = yf.download(batch, period="5d", auto_adjust=True, progress=False, threads=True)
  ```
  por:
  ```python
  data = yf.download(batch, period="5d", auto_adjust=True, progress=False, threads=False)
  ```

## 5. Validación post-fix [universe-management]

- [ ] 5.1 Esperar el siguiente ciclo de price update (próximos 15 min durante mercado o trigger manual)
- [ ] 5.2 Revisar `/tmp/scheduler.log` — confirmar:
  - Aparece línea `"Price download: excluding N non-downloadable symbols"` con N ≈ 771
  - NO aparecen errores `TypeError: 'NoneType' object is not subscriptable`
  - NO aparecen errores `getaddrinfo() thread failed to start`
  - El número de "Failed downloads" por batch baja significativamente
- [ ] 5.3 Verificar que JPM, JNJ, UBER tienen precios actualizados:
  ```sql
  SELECT symbol, MAX(date) as last_price
  FROM stock_prices
  WHERE symbol IN ('JPM', 'JNJ', 'UBER', 'DELL', 'BA')
  GROUP BY symbol;
  ```
  El `last_price` debe ser la fecha del día o el último día hábil.
