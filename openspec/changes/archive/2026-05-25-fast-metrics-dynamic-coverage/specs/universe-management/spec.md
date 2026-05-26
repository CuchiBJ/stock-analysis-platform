## MODIFIED Requirements

### Requirement: FAST Metrics Cycle SHALL Cover Institutional Quality Stocks in Addition to TIER 1

El ciclo FAST de métricas (cada 5 minutos) SHALL calcular métricas para todos los stocks que pasan los quality gates institucionales (`avg_volume_10d >= 800k`, `adr_percent >= 3%`, `perf_1y > 25%`, `price > EMA50`, `price > SMA150`, `SMA150 > SMA200`) además de los símbolos de TIER 1, hasta un máximo de 300 símbolos por ciclo.

**Implementación:** `backend/app/data/scheduler.py`, método `trigger_fast_metrics_update()` + helper `_get_fast_symbols()`

#### Scenario: Stock en live feed recibe métricas frescas cada 5 minutos

- **WHEN** un stock como WULF o LITE pasa los quality gates institucionales pero no está en TIER 1
- **THEN** SHALL ser incluido en el FAST cycle y recibir métricas actualizadas cada 5 minutos
- **AND** sus métricas SHALL tener como máximo 5 minutos de latencia durante el horario de mercado

#### Scenario: TIER 1 sigue siendo el baseline garantizado

- **WHEN** ningún stock pasa los quality gates institucionales (mercado bear extremo)
- **THEN** el FAST cycle SHALL continuar ejecutando para los símbolos de TIER 1
- **AND** el ciclo SHALL NOT fallar ni quedar vacío

#### Scenario: Log refleja la cobertura dinámica

- **WHEN** el FAST cycle ejecuta
- **THEN** SHALL loggear `"FAST cycle: X TIER 1 + Y institutional = Z unique symbols"` donde Z <= 300

#### Scenario: Límite de 300 símbolos se respeta

- **WHEN** la unión de TIER 1 e institucionales supera 300 símbolos
- **THEN** el ciclo SHALL procesar los primeros 300 y loggear el total disponible
