## MODIFIED Requirements

### Requirement: Price Update SHALL Complete Before FAST Metrics Runs

Cuando el ciclo de precio dispara, el scheduler SHALL esperar que el price update complete antes de ejecutar FAST metrics. Esto garantiza que las métricas calculadas reflejen los precios más recientes disponibles.

**Implementación:** `backend/app/data/scheduler.py`, `_scheduler_loop()`

#### Scenario: FAST metrics usa precio actualizado tras price update

- **WHEN** el scheduler ejecuta un ciclo de precio (cada 15 min)
- **THEN** `_update_prices()` SHALL completar antes de que `trigger_fast_metrics_update()` ejecute
- **AND** las métricas calculadas SHALL usar el precio de `stock_prices` más reciente

#### Scenario: FAST metrics independiente entre actualizaciones de precio

- **WHEN** el scheduler ejecuta un ciclo de FAST metrics sin que haya disparado price update en el mismo tick
- **THEN** SHALL calcular métricas con los últimos precios disponibles (no esperar nuevo price update)

#### Scenario: Fallo de price update no bloquea FAST metrics

- **WHEN** `_update_prices()` lanza una excepción
- **THEN** el scheduler SHALL loggear el error Y continuar ejecutando FAST metrics con precios existentes
- **AND** SHALL NOT quedar en estado bloqueado

### Requirement: SLOW Metrics Cycle SHALL Cover All Symbols With Today's Price

El ciclo SLOW SHALL calcular métricas para todos los símbolos que tengan un registro en `stock_prices` con la fecha más reciente disponible, no un número fijo de símbolos.

**Implementación:** `backend/app/data/scheduler.py`, helper `_get_slow_symbols()` + `trigger_metrics_update()`

#### Scenario: SLOW cycle procesa todos los símbolos con precio de hoy

- **WHEN** `stock_prices` tiene registros del día para 4800 símbolos
- **THEN** el SLOW cycle SHALL calcular métricas para los 4800
- **AND** el log SHALL mostrar `"SLOW cycle: 4800 symbols with price for YYYY-MM-DD"`

#### Scenario: Brecha precio/métricas se elimina tras SLOW completo

- **WHEN** el SLOW cycle completa
- **THEN** todos los símbolos con `stock_prices.date = hoy` SHALL tener `stock_metrics.date = hoy`
- **AND** la brecha de "precios más frescos que métricas" SHALL ser 0

#### Scenario: SLOW no se solapa consigo mismo

- **WHEN** el SLOW cycle de las 10:00 todavía está corriendo a las 10:30
- **THEN** el scheduler SHALL NO iniciar un segundo SLOW cycle
- **AND** SHALL loggear `"SLOW cycle still running — skipping"`

### Requirement: Startup SHALL Fetch Fresh Prices Before Initial Metrics

Al arrancar el scheduler, SHALL descargar precios frescos antes de calcular el batch inicial de métricas.

**Implementación:** `backend/app/data/scheduler.py`, inicio de `_scheduler_loop()`

#### Scenario: Startup con precios frescos

- **WHEN** el scheduler arranca
- **THEN** SHALL ejecutar `_update_prices()` primero
- **AND** luego ejecutar el SLOW metrics inicial con los precios recién descargados
