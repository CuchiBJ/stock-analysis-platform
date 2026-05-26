## Why

El operador actualmente cura su watchlist manualmente en TradingView: revisa `/transitions/live`, decide cuáles agregar, y los monitorea sin contexto sistémico. Esto rompe el Principio 10 (Workflow > analytics) — el sistema muestra señales pero no soporta el workflow real de ejecución, dejando al operador re-escanear y recordar contexto.

La estrategia primaria es **undercut & rally en líderes Minervini-grade en corrección**, complementada por dos vistas auxiliares: emerging leaders (futuros líderes) y building bases (líderes de próximo ciclo). Cada estrategia tiene horizonte temporal y criterios distintos — mezclarlas en una sola vista contamina la decisión. Necesitamos tres lentes separadas, cada una con su propósito explícito.

Esto extiende Principio 2 (Scarcity is signal) — cada lente filtra a un puñado de candidatos accionables, no a una lista de 50; y Principio 10 (Workflow > analytics) — el sistema cura, el operador ejecuta.

## What Changes

- Nueva capacidad `setup-queue` que expone tres lentes dinámicas, cada una con criterios estrictos y propósito declarado.
- **Lens 1 — U&R Queue**: Líderes Minervini con evento pre-reclaim últimos 2 días + regla "from above" (estaba claramente arriba de EMA21 hace 5-10 días + actualmente cerca + no rompió EMA50 últimos 20 días).
- **Lens 2 — Emerging Leaders**: Stocks con `perf_6m > 20%` y `RS_spy > 105` que NO califican Minervini full, con desglose explícito de qué criterios cumple/falla.
- **Lens 3 — Building Bases**: Líderes Minervini con `vcp_score >= 70`, `weeks_in_base >= 6`, y `distance_to_ema21_atr` oscilando dentro de ±1 ATR las últimas 4 semanas.
- Nuevos endpoints: `GET /api/v1/queue/u-and-r`, `GET /api/v1/queue/emerging-leaders`, `GET /api/v1/queue/building-bases`, `GET /api/v1/queue/symbol/{symbol}/history`.
- Nueva página frontend dedicada (`/queue`) con layout de 3 tabs, no panel del dashboard. Workflow primario.
- Cada row enlaza out a TradingView para análisis de pivot 30-min (siguiente paso del workflow).

## Capabilities

### New Capabilities
- `setup-queue`: Orquesta las tres lentes (U&R, emerging leaders, building bases), aplica los filtros específicos de cada estrategia sobre datos ya existentes (`transition_observations`, `stock_metrics`), y expone el historial por símbolo para ver el arco completo de transiciones.

### Modified Capabilities
- Ninguna. La regla "from above" se aplica a nivel de query en el nuevo servicio, NO modifica `transition-engine` (decisión arquitectónica explícita — el engine sigue clasificando genéricamente para múltiples vistas).

## Impact

| Archivo | Cambio |
|---|---|
| `backend/app/api/v1/endpoints/queue.py` | Nuevo — 4 endpoints (`u-and-r`, `emerging-leaders`, `building-bases`, `symbol/{symbol}/history`) |
| `backend/app/api/v1/api.py` | Registrar router `/queue` |
| `backend/app/services/setup_queue_service.py` | Nuevo — lógica de cada lente, regla "from above", historial por símbolo |
| `backend/app/services/quality_leader_gate.py` | Nuevo — extraer `_is_quality_leader` de `transition_engine.py` (líneas 637-669) a helper compartido para reuso en setup_queue_service |
| `frontend/app/queue/page.tsx` | Nuevo — página con 3 tabs |
| `frontend/components/queue/UnderCutRallyQueue.tsx` | Nuevo — Lens 1 |
| `frontend/components/queue/EmergingLeadersQueue.tsx` | Nuevo — Lens 2 con qualification breakdown |
| `frontend/components/queue/BuildingBasesQueue.tsx` | Nuevo — Lens 3 |
| `frontend/components/queue/SymbolHistoryDrawer.tsx` | Nuevo — drawer/modal al click de cualquier row |

**Non-goals (explícito en design.md):**
- Sin "changes since last visit" — v2
- Sin anotaciones personales por símbolo — v2
- Sin alertas/push (no hay auth)
- Sin order management
- Sin charts integrados (link out a TradingView)
- Sin diseño mobile-first

**Performance:** Todos los queries usan índices existentes (`ix_obs_symbol_type_date`, `ix_stock_metrics_symbol_date`). La lente U&R requiere 1 query principal + lookups históricos por símbolo en queue (bulk fetch, sin N+1). Estimado <300ms para queues típicas de 5-15 candidatos.

**Decomposition note:** `transition_engine.py` está en ~825 LOC. Extraer `_is_quality_leader` a `quality_leader_gate.py` reduce ese archivo en ~30 LOC y crea un helper reutilizable. No es una refactorización completa pero es un primer paso alineado con la regla de auditar archivos > 400 LOC.
