## Context

current/overview guardan la última postura observada por sesión mediante MarketPostureRecordService. DataScheduler ya ejecuta precios EOD y SLOW desde las 16:10 America/New_York en días laborables; marca el intento diario incluso si falla. SLOW puede omitir ejecución por concurrencia, devolver cero o cubrir sólo parte del universo. MarketContextEngine.analyze usa caché de 300 segundos. La especificación previa excluía expresamente captura sin visitas; este incremento elimina esa limitación para ciclos diarios exitosos.

## Goals / Non-Goals

**Goals:** Registrar una postura actual real sin visitas, tras métricas confirmadas, con fechas exactas, evidencia completa, fallos visibles y reintentos seguros.

**Non-Goals:** Backfill, reconstrucción histórica, cierre certificado, nuevos contratos de UI/API, cambio de política, garantizar sesiones durante apagados o cambiar ingesta y calendarios de mercado.

## Decisions

1. Integrar en el ciclo post-cierre existente; precios → métricas confirmadas → cálculo actual → persistencia. No crear tarea por reloj independiente que pueda adelantarse a la ingesta. La captura se espera con await; no fire-and-forget. El intento SLOW post-cierre exige métricas recalculadas después de la carga EOD: no reutiliza filas recientes anteriores a esa carga por la protección de cinco minutos. La protección habitual se conserva en los demás intentos SLOW. Extraer coordinación/captura a un módulo acotado y dejar sólo un punto de integración local en scheduler. No refactorizar los servicios grandes.
2. Una ejecución es apta si procesó más de cero símbolos y cubrió al menos el 95% del mismo snapshot de símbolos intentados, reutilizando el criterio operativo existente de SLOW. La ejecución privada devuelve un resultado estructurado por intento; el método público conserva su retorno entero. Una ejecución omitida por _slow_running no cuenta como éxito aunque haya contadores de un intento previo. El cálculo que devuelve None no cuenta como escrito y una fila reciente sólo cuenta como cubierta para la fecha exacta del snapshot, sin aceptar filas futuras. Confirmar que la fecha de métricas/contexto coincide exactamente con la fecha objetivo del ciclo; si son anteriores o futuras no guardar ni cambiarles la fecha. La observación requiere universo de calidad no vacío y postura válida.
3. Añadir una opción compatible al cálculo actual para omitir caché en captura post-pipeline; las llamadas existentes conservan su comportamiento. No usar analyze_as_of ni APIs HTTP ni importar endpoints desde el scheduler. Serializar el mismo payload completo de postura que usan las consultas (state/instruction/reasons/unlock/policy), preferiblemente con helper compartido pequeño.
4. Reutilizar observe y el upsert atómico existente: una fila por session_date, recorded_at UTC de la observación real y última escritura por timestamp. Sin migración nueva ni evento de trading; captura por consultas sigue funcionando y puede actualizar la observación. Los registros no se presentan como cierre oficial.
5. Un fallo de cálculo/validación/persistencia se aísla del resto del scheduler, registra log sin payload sensible y heartbeat post_close_cycle no exitoso con motivo. No revertir métricas ya confirmadas. Sólo marcar la fecha diaria como completada tras captura exitosa. Congelar la fecha objetivo al inicio y verificar que sigue siendo el día actual de Nueva York antes de persistir, evitando etiquetar capturas después de medianoche como si fueran emisiones previas. Reintentar el ciclo fallido como máximo una vez cada 300 segundos desde su finalización en la ventana post-cierre del mismo día de Nueva York; no hacer catch-up histórico. No reejecutar un ciclo diario exitoso. La guarda temporal y su resultado deben poder probarse sin esperar tiempo real.

## Risks / Trade-offs

- Datos parciales → exigir cobertura >=95% del snapshot y fecha exacta; no bajar filtros de calidad ni fabricar registros.
- Caché anterior al ciclo → bypass explícito para esta llamada, sin alterar consumidores actuales.
- Caída de DB/tabla ausente → rollback de observe, ciclo fallido observable y reintento acotado; no bloquear otras tareas.
- Reinicio del scheduler → se puede repetir la captura del día; upsert conserva una sola fila y el timestamp real. Sin garantía de exactamente una ejecución.
- Apagado durante una sesión, feriado o falta de datos del día → no prometer registro ni rellenar el día con datos anteriores. Se conserva el calendario operativo actual del scheduler.
- La filosofía general propone inmutabilidad, mientras el contrato activo implementado usa última observación mutable → conservar ese contrato explícito; event sourcing no forma parte de este cambio.

## Migration Plan

No hay migración nueva. El entorno debe tener aplicada la migración existente de market_posture_records antes de capturar. Activación al actualizar/reiniciar el proceso scheduler. Tras autorización explícita del usuario el 2026-10-27 se despliegan únicamente los seis archivos de backend afectados y se recrean API/scheduler, verificando primero esquema y hashes de fuentes anteriores. Producción ya está en f6a7b8c9d0e1, por lo que no se aplican migraciones. Se preservan fuentes e imágenes para rollback; frontend, PostgreSQL, Redis y Caddy conservan sus contenedores. Rollback del código devuelve la captura sólo por consulta sin borrar registros.

## Open Questions

Ninguna para el alcance actual.
