## Why
QQQ aparece atrasado en Market context y deja comparaciones sin evidencia. Las rutas programadas incluyen SPY y ETF sectoriales explícitamente, pero QQQ depende del universo de acciones. Corregir esta omisión defiende contexto interpretable y detección de transiciones sin confundir falta de datos con neutralidad.

## What Changes
- Definir una lista compartida de referencias de Market context (SPY y QQQ).
- Incluir esas referencias en descarga programada y filtro EOD aunque no pertenezcan al universo de acciones.
- Verificar con datos sintéticos que QQQ llega a la selección SLOW de métricas y al overview con fechas reales.
- Tras autorización explícita del usuario el2026-10-26: recuperar una ventana coherente de260 sesiones QQQ, recalcular sus indicadores y activar la ingesta productiva con respaldo y validación.

## Capabilities
### New Capabilities
- `market-context-benchmark-refresh`: Inclusión independiente del universo de SPY y QQQ en ingesta programada.
### Modified Capabilities
Ninguna.

## Impact
Backend benchmarks, scheduler e ingestor Polygon EOD; pruebas de integración sintéticas. Sin cambios API, frontend, dependencias ni migraciones. El scheduler supera400 líneas: extraer la composición de referencias a helper pequeño y compartido, sin refactor amplio.

## Non-goals
No ejecutar recuperaciones automáticas ni masivas. El seguimiento operativo autorizado explícitamente el2026-10-26 permite recuperar sólo QQQ y desplegar esta corrección; la fase inicial fue local. No alterar Dashboard, postura, scoring ni extremos respecto de sesión anterior (confirmado por usuario). Las mejoras visuales e historial de postura quedan fuera de esta iteración.
