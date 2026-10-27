## Context

Benchmark.date y metrics_date ya existen. VIX.status combina fecha anterior y fallo de fuente; no permite distinguirlos. El Dashboard y la política quedan intactos.

## Goals / Non-Goals

**Goals:** Hacer visible qué evidencia corresponde a la sesión del contexto y distinguir antigüedad de disponibilidad de fuente.

**Non-Goals:** Ingesta, backfills, cambios de reglas, narrativas nuevas, calendario bursátil, despliegue.

## Decisions

- Helpers puros en frontend/lib/market-context.ts comparan fechas ISO válidas con as_of, no con el reloj del navegador. Estados: misma sesión, anterior, posterior no comparable, sin datos/fecha válida. Un precio nulo/no finito nunca es vigente.
- Benchmark atrasado: etiqueta ámbar y precio menor, legible, variación neutra; conservar valor y fecha. Indicadores tienen vigencia propia y advertencia explícita si su fecha no coincide con contexto; no heredar vigencia del precio.
- Aviso compacto de comparación SPY/QQQ solo si ambos precios no son finitos o sus fechas no coinciden con as_of. Expresar que no son comparables para la sesión del contexto; no inferir divergencia.
- VIX anterior: etiqueta factual «Cierre anterior al contexto» y fecha, sin afirmar que está actualizado o en frecuencia esperada. No inferir sesión anterior a partir de días calendario ni inventar tolerancias. VIX posterior/fecha inválida: no comparable. Valor anterior conserva menor jerarquía.
- Añadir refresh_failed:boolean en cada VixQuote no nulo; mantener status existente por compatibilidad. Frontend declara campo opcional: si ausente y status stale, indicar actualización no confirmada; nunca asumir éxito. Si false, no mostrar alerta de fallo solo por fecha anterior. Si true o query error, avisar fallo aun con fecha actual. Fecha y falla son dimensiones independientes.
- No nuevas dependencias. Pruebas con datos sintéticos y transporte mock, nunca producción.

## Risks / Trade-offs

- Sin calendario ni hora de publicación no se puede certificar que un cierre anterior sea el esperado → presentar fecha y relación temporal, no un juicio de salud de ingesta.
- Backend previo no tiene refresh_failed → fallback conservador, compatible con despliegue gradual.

## Migration Plan

Sin migraciones. Validar localmente; despliegue en una etapa posterior. Reversión de archivos si fuera necesario.

## Open Questions

Ninguna para esta iteración. Reparación de ingesta QQQ queda como trabajo separado.
