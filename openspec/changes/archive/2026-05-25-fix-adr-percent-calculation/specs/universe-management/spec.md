## MODIFIED Requirements

### Requirement: adr_percent SHALL Measure High-Low Range, Not Close-to-Close Change

The `adr_percent` metric stored in `stock_metrics` SHALL be calculated as the mean of
`(high - low) / close * 100` over the last 20 trading days. The close-to-close
percentage change formula (currently in use) SHALL be replaced — it does not measure
Average Daily Range as the name implies.

**Correct formula:**
```
ADR_% = mean( (high_i - low_i) / close_i * 100 )  for i in last 20 days
```

**Expected scale (post-recalculation):**

| Tipo de stock | adr_percent esperado |
|---|---|
| Bond ETFs, utilities | < 1% |
| Large-caps low-vol (e.g., JNJ) | 1-2% |
| Large-caps tech (MCHP, ON) | 3-5% |
| Mid-caps growth | 4-7% |
| Small-caps volatile (AXTI) | 7-15% |
| Micro-caps speculative | > 15% |

**Implementation:** `backend/app/data/processors/momentum.py`, function `calculate_adr_percent()`

#### Scenario: Large-cap institucional con rango diario real >= 4%

- **WHEN** un stock tiene high promedio 4% por encima del low diario (e.g., MCHP a $91 con rango diario típico de $4)
- **THEN** `adr_percent` SHALL ser >= 3.5 (no 2.26% como reporta la fórmula incorrecta)
- **AND** el stock SHALL pasar el filtro `adr_percent >= 4.0%` si su ADR real es >= 4%

#### Scenario: Stock inactivo o con datos faltantes

- **WHEN** un stock tiene menos de 5 días con high/low/close válidos en los últimos 20
- **THEN** `adr_percent` SHALL ser `0.0`
- **AND** el stock SHALL NOT pasar ningún filtro de calidad basado en `adr_percent`

#### Scenario: Movimiento direccional sin rango intradiario

- **WHEN** un stock sube 2% cada día con rango intradiario mínimo (e.g., abre y cierra cerca del high/low)
- **THEN** `adr_percent` SHALL reflejar el rango real (cercano a 2%), no el cambio close-to-close (que también sería ~2%)
- **AND** se evita el sesgo de la fórmula anterior que daba valores artificialmente diferentes a la realidad operacional

### Requirement: calculate_adr_percent SHALL Accept DataFrame With High/Low/Close

La función `calculate_adr_percent()` SHALL aceptar un DataFrame de pandas con las columnas
`high`, `low`, y `close` en lugar de solo una Serie de close prices. Esto permite calcular
el rango diario real, no solo el cambio close-to-close.

**Implementation:** `backend/app/data/processors/momentum.py`

#### Scenario: La función rechaza llamados con solo close prices

- **WHEN** un caller intenta pasar una `pd.Series` con solo precios close
- **THEN** la función SHALL lanzar un `TypeError` claro indicando que se requiere un DataFrame con high/low/close

#### Scenario: Caller en metrics_calculator.py actualizado

- **WHEN** `metrics_calculator.py` llama a `calculate_adr_percent()`
- **THEN** SHALL pasar el DataFrame completo (con high, low, close) en lugar de solo close_prices
