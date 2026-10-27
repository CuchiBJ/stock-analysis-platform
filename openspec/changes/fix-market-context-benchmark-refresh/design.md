## Context
El overview consulta precios y métricas persistidos con fechas explícitas. El scheduler añade SPY y los ETF sectoriales a la descarga, mientras Polygon aplica el mismo filtro de referencias; ninguno añade QQQ explícitamente. SLOW procesa todos los símbolos con precio en la sesión más reciente y no necesita cambios en su selección.

## Goals / Non-Goals
**Goals:** Actualización programada de SPY/QQQ independiente de acciones activas y verificación sintética de su paso hacia métricas/overview.
**Non-Goals:** UI, nuevas fuentes o instrumentos, cambios de política/extremos, recuperaciones masivas y garantías sobre disponibilidad de proveedor. La recuperación productiva puntual de QQQ fue autorizada explícitamente el2026-10-26.

## Decisions
1. Declarar SPY/QQQ como benchmarks de Market context en benchmarks.py, preservando BENCHMARK_SYMBOLS y su semántica de identificación (incluye IWM/DIA). No ampliar esta ingesta a otros índices sin necesidad.
2. Extraer un helper pequeño de composición de símbolos de referencia; combina los símbolos recibidos, SPY/QQQ y SECTOR_ETFS, elimina duplicados, preserva orden de entrada y no muta la entrada. Ambos caminos de ingesta deben consumir esa única definición. No refactorizar el scheduler completo.
3. Mantener downloader, reintentos, validación y upsert existentes; sólo corregir selección. No agregar QQQ a stocks ni hacer candidato al screener por esa inclusión.
4. Reutilizar SLOW: prueba sintética confirma que precio actual QQQ sin fila Stock entra a su selección. Probar overview con fechas coincidentes y precio previo estricto, y conservar tests de datos ausentes/atrasados.
5. Pruebas offline con proveedor simulado y SQLite o doubles de SQLAlchemy. Verificar llamadas reales a _update_prices y PolygonEODIngestor.ingest_eod, no sólo el helper.

## Risks / Trade-offs
- La ventana actual de descarga es5 días: reanuda ingesta, pero no rellena el hueco histórico ya existente. MetricsCalculator usa las últimas260 filas sin validar continuidad: nuevas métricas podrían fecharse como actuales sobre una serie discontinua. Recuperar esa serie es REQUISITO previo para confiar en los indicadores productivos y exige una operación separada explícitamente autorizada. No basta con esperar una actualización de5 días.
- El proveedor puede omitir QQQ o fallar: las fechas y avisos de frescura existentes siguen siendo la evidencia; no fabricar cero ni copiar precio SPY.
- Grandes archivos: composición extraída evita duplicación y limita las ediciones a sus puntos de selección.

## Migration Plan
Sin migraciones. La fase inicial entregó código local y pruebas. El seguimiento operativo autorizado el2026-10-26 recuperó QQQ y activó el despliegue; consultar deployment.md.

## Open Questions
Ninguna para implementación. La restauración del historial productivo queda como seguimiento operativo.

## Authorized operational recovery —2026-10-26
User explicitly authorized historical recovery, QQQ metrics recalculation and production refresh activation. Operational read-only diagnosis found276 QQQ prices ending2026-08-17, no QQQ metrics, and49 missing observations against the latest260 stored SPY sessions ending2026-10-26.

- Add a narrowly scoped recover_qqq.py CLI with prepare/dry-run, backup and explicit execute modes. Prepare reads the last260 SPY dates and downloads a complete QQQ adjusted OHLCV window using yfinance auto_adjust=True, consistent with the scheduled fallback and original benchmark loader. Refresh the complete260-bar calculation window to avoid stitching differently adjusted histories across the missing months.
- Freeze candidate JSON with symbol, source, reference_dates, rows and prepared_at; validate exactly260 distinct dates matching SPY and finite/coherent/positive OHLC plus valid integer volumes. No writes until coverage passes.
- Export only existing QQQ price/metric rows to a recovery backup and preserve existing sources/images. Pause scheduler briefly during execution to avoid concurrent QQQ metric writes.
- Execute requires candidate SHA256 and backup; revalidates current SPY dates and candidate. Upsert only QQQ reference rows and recalculate only its latest metric record. Wrap calculator commit as flush so price repair and metrics commit atomically; rollback everything on validation/calculation failure. Set the metric high_52w from the repaired last252 closes because the legacy calculator does not assign that field.
- Confirm date, price, EMA50/EMA200/SMA150/SMA200 and coverage before commit. Activate the already-tested shared benchmark-selection code only after successful recovery. Restart API to clear dated evidence cache, verify authenticated page, and resume scheduler. No backfill of posture history or other stocks.
