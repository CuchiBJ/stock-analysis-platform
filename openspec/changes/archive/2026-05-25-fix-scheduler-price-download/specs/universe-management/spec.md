## MODIFIED Requirements

### Requirement: Price Download SHALL Exclude Non-Downloadable Symbols

El ciclo de price update (`_bulk_download_prices_sync`) SHALL excluir símbolos que por estructura son no-descargables de Yahoo Finance antes de construir los batches de descarga. Estos símbolos no deben generar requests a Yahoo ni aparecer en logs de error.

**Símbolos excluidos (patrón):**
- Símbolos con prefijo `$` (índices, listas internas)
- Símbolos de 5 caracteres terminados en `W`, `U`, o `R` (warrants, units, rights)

**Implementación:** `backend/app/data/scheduler.py`, método `_bulk_download_prices_sync`, helper `_is_downloadable(symbol: str) -> bool`

#### Scenario: Warrants excluidos del download

- **WHEN** el scheduler construye la lista de símbolos para el price download
- **THEN** símbolos como `AMPXW`, `PSQHW`, `KCACW` (5 chars, termina en W) SHALL ser excluidos
- **AND** el scheduler SHALL loggear una sola línea INFO con el conteo de excluidos: `"Price download: excluding N non-downloadable symbols"`
- **AND** NO SHALL generar requests a Yahoo Finance para esos símbolos

#### Scenario: Símbolos válidos de 4 chars terminados en W/U/R no se excluyen

- **WHEN** el scheduler evalúa un símbolo como `NVDA`, `BKSY`, `QUIK`
- **THEN** SHALL incluirlos en el download (no coinciden con el patrón de 5 chars)

### Requirement: Price Download SHALL Handle Missing Symbols in yfinance MultiIndex Response

Cuando `yf.download(batch, ...)` retorna un DataFrame con MultiIndex y un símbolo del batch no está presente en el resultado, el scheduler SHALL saltar ese símbolo limpiamente sin lanzar TypeError ni interrumpir el procesamiento del resto del batch.

**Implementación:** `backend/app/data/scheduler.py`, loop interno de `_bulk_download_prices_sync`

#### Scenario: Símbolo ausente del MultiIndex se saltea limpiamente

- **WHEN** `yf.download` retorna un MultiIndex que no contiene el símbolo `FOO`
- **THEN** el scheduler SHALL loggear `DEBUG: "Symbol FOO not in yfinance response — skipping"`
- **AND** SHALL continuar procesando los demás símbolos del batch sin error
- **AND** SHALL NOT lanzar `TypeError: 'NoneType' object is not subscriptable`

#### Scenario: Símbolo presente en MultiIndex se procesa normalmente

- **WHEN** `yf.download` retorna un MultiIndex que contiene el símbolo `JPM`
- **THEN** el scheduler SHALL procesar su precio normalmente con `data.xs('JPM', axis=1, level=1)`

### Requirement: Price Download SHALL Use threads=False to Prevent DNS Exhaustion

`yf.download` SHALL ser invocado con `threads=False` para evitar que el batch de 200 símbolos cree threads DNS simultáneos que agoten el pool del sistema operativo.

**Implementación:** `backend/app/data/scheduler.py`, `_bulk_download_prices_sync`

#### Scenario: Sin errores de DNS en logs después del fix

- **WHEN** el scheduler ejecuta un ciclo de price update completo
- **THEN** SHALL NOT aparecer errores `getaddrinfo() thread failed to start` en el log
- **AND** SHALL NOT aparecer errores `Could not resolve host: query2.finance.yahoo.com`
