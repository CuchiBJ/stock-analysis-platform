## Why

Auditoría del scheduler reveló tres bugs que producen métricas desactualizadas y datos inconsistentes en el feed operativo:

**Bug 1 — Race condition precio/métricas (crítico)**
El price update corre en background (`asyncio.create_task`) y el FAST metrics corre inmediatamente después (`await`) en el mismo tick del loop. Las métricas se calculan con los precios del ciclo anterior porque el download de yfinance todavía no terminó. MRAM mostró precio $32.15 en métricas cuando `stock_prices` ya tenía $34.26 — una diferencia de +5.6%.

**Bug 2 — SLOW cycle cubre solo 3125 de 6718 símbolos**
2757 símbolos tienen precios más frescos que sus métricas. El SLOW cycle con `limit=3125` nunca llega a calcular los restantes. Sus métricas quedan congeladas indefinidamente.

**Bug 3 — Price update corre en background pero no notifica cuándo terminó**
Sin notificación de fin del download, es imposible encadenar métricas correctamente. Cualquier lógica que asuma "el precio ya está actualizado" es una ilusión.

Viola Principio 1 (transitions dominate — una transición detectada con precio de hace 40 minutos no es una transición, es ruido) y Principio 7 (interpretabilidad — el precio mostrado en el feed debe ser el precio real actual).

## What Changes

**Encadenar precio → métricas**: cuando el ciclo de precio dispara, el loop lo espera (`await`) antes de correr FAST metrics. Garantía de que las métricas siempre usan el precio más reciente disponible.

**SLOW cycle cubre todos los símbolos con precios de hoy**: reemplazar `limit=3125` por una query que devuelve todos los símbolos que tienen `stock_prices` con fecha de hoy. Si hoy yfinance actualizó 4800 símbolos, el SLOW los procesa todos.

**Separar el ciclo de precios del ciclo de métricas con dependencia explícita**: el timer de FAST metrics no corre si el price update del mismo tick todavía está pendiente.

## Capabilities

### New Capabilities
*(ninguna)*

### Modified Capabilities
- `universe-management`: el comportamiento del scheduler cambia — el ciclo de actualización pasa de "independiente con race condition" a "encadenado con dependencia explícita".

## Non-goals

- No cambiar las frecuencias (precios cada 15 min, FAST cada 5 min, SLOW cada 30 min).
- No agregar persistencia del timestamp de último price update en DB.
- No cambiar qué datos descarga yfinance (period=5d sigue igual).
- No tocar el FAST cycle dinámico recién implementado.

## Impact

| Archivo | Cambio |
|---|---|
| `backend/app/data/scheduler.py` | `_scheduler_loop()`: price update cambia de `create_task` a `await`; FAST metrics corre inmediatamente después de price update; SLOW metrics query dinámica por símbolos con precio de hoy |
