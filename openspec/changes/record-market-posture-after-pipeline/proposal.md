## Why

El historial de postura depende de visitas a current/overview: una sesión no consultada deja un hueco permanente e impide comparar transiciones y deterioro. Registrar la decisión calculada al terminar el procesamiento diario conserva evidencia interpretable sin depender de actividad del usuario.

## What Changes

- Capturar automáticamente la postura actual después del ciclo post-cierre de precios y métricas, sin peticiones HTTP.
- Exigir métricas suficientes y fecha exacta de la sesión procesada; calcular sin reutilizar la caché previa al procesamiento.
- Reutilizar el registro durable y su upsert atómico con hora UTC; mantener captura por consulta y contratos existentes.
- Hacer observables los fallos de captura y permitir reintentos acotados durante la ventana post-cierre.
- Extraer la coordinación post-cierre y/o captura a módulos pequeños: el scheduler y el motor actuales superan 400 líneas y sólo recibirán integración localizada.

## Capabilities

### New Capabilities

- `market-posture-pipeline-capture`: Captura autónoma de la postura de la sesión procesada, validación de frescura y recuperación ante fallos.

### Modified Capabilities

Ninguna especificación canónica cambia. Extiende el cambio completado `streamline-market-context-and-record-posture`, que deliberadamente limitaba la captura a consultas; su contrato de última observación por sesión se conserva.

## Impact

Backend: scheduler, cálculo actual de contexto y un coordinador acotado de captura/post-cierre, con pruebas aisladas. Sin nuevas dependencias, contratos API, cambios frontend ni migraciones adicionales; utiliza la tabla market_posture_records existente.

El 2026-10-27 el usuario autorizó explícitamente la activación en producción. Se añade el despliegue acotado de seis archivos de runtime, reconstrucción de API/scheduler y verificación operativa, sin migraciones ni cambios de datos históricos.

## Non-goals

No reconstruir fechas pasadas ni ejecutar backfills, aplicar migraciones, cambiar reglas de postura, certificar un cierre oficial, añadir recomendaciones de trading ni asegurar registros cuando el scheduler estuvo apagado toda la sesión. Se conserva el upsert por sesión del cambio anterior aunque la filosofía arquitectónica general menciona eventos inmutables; convertirlo en event store queda fuera del alcance.
