## Why

El change `introduce-market-group-rotation` (shipped 2026-05-25) introdujo el heatmap de ~25 market groups y permite al operador leer rotación con resolución superior a GICS L1. Pero esa lectura queda **desconectada del ranking de setups**: un stock de `Electronic Technology` (grupo top este mes) y otro de `Consumer Staples` (grupo bottom) compiten con exactamente el mismo `priority_score` si sus señales por símbolo son equivalentes. El operador ve "🔥 grupo fuerte" en el heatmap pero el sistema le sigue ofreciendo setups equivalentes de grupos débiles arriba en la lista.

Esto contradice **Principio 9 (Institutional sponsorship is primary signal)**: el capital institucional rota por grupos, y un setup técnicamente válido en un grupo que está sangrando tiene menos probabilidad de continuación que el mismo setup en un grupo que está siendo acumulado. Hoy el sistema lo sabe (heatmap) pero no lo usa (scoring).

Esta change cierra el loop: la fuerza del grupo se traduce en un multiplier suave del priority_score en `/actionable`, y en un badge visual en queue lenses y cards. Espejo arquitectónico del `market-context-decision-wiring` (shipped 2026-05-24), que hizo lo mismo para contexto macro.

## What Changes

- **Nuevo módulo `backend/app/services/group_strength_service.py`**:
  - `compute_group_multiplier(market_group: str | None, group_perfs: dict[str, float]) -> GroupMultiplier`
  - Retorna `GroupMultiplier(score_multiplier: float, badge: str)` donde:
    - `badge ∈ {"leader", "neutral", "weak"}`
    - `score_multiplier ∈ {1.15, 1.00, 0.85}` (suave, sin suppression dura)
  - `fetch_current_group_strengths(db) -> dict[str, float]` — lee performance_monthly por grupo (reutiliza `SectorService.calculate_sector_performance`).
  - Cache in-memory 5 min TTL (idéntico al `context_decision_filter`).
- **Métrica de fuerza**: percentil de `performance_monthly` entre los ~25 grupos (top 20% → leader/1.15; bottom 20% → weak/0.85; resto → neutral/1.00).
- **Cobertura mínima**: grupos con menos de 5 stocks (post-quality-filter) reciben `1.0/neutral` automáticamente, para evitar ruido en grupos chicos (ej. Renewables, Insurance).
- **Edge cases**: `market_group IS NULL` (Shell Companies, sin industry mapeado) → `1.0/neutral`. Espejo del UNKNOWN macro.
- **Integración en `/actionable`** ([transitions.py](backend/app/api/v1/endpoints/transitions.py)):
  - Compose multiplicativo: `final = priority_score × ctx_multiplier × group_multiplier`
  - Cada setup gana un campo `group_strength: {"group": "Electronic Technology", "badge": "leader", "multiplier": 1.15}` en el response
- **Integración en queue (`/u-and-r`, `/emerging-leaders`, `/building-bases`)** ([queue.py](backend/app/api/v1/endpoints/queue.py)):
  - **Badge only — NO toca el sort key de cada lens.**
  - Cada item del response gana `group_strength: {group, badge}` (sin multiplier — no aplica al ordenamiento).
  - Building-bases incluido en badges pero sin afectar nada operacional, igual que ctx_multiplier nunca lo suprime.
- **Frontend — badge visual en cards** ([CompactSetupCard.tsx](frontend/components/dashboard/CompactSetupCard.tsx), [TopActionableSetups.tsx](frontend/components/dashboard/TopActionableSetups.tsx), filas de queue):
  - "🔥 Group leader" (text-cyan-400) cuando badge === "leader"
  - "⚠️ Weak group" (text-amber-400) cuando badge === "weak"
  - Sin badge cuando badge === "neutral" (no ensuciar lo común)
  - Hover/tooltip muestra el group name y su rank (ej. "Electronic Technology #2/25")

## Capabilities

### New Capabilities
- `group-strength-scoring`: aplica la fuerza relativa del market_group de cada stock como multiplier suave del priority_score en `/actionable` y como badge visual en queue lenses y cards, derivando la métrica del percentil de `performance_monthly` del grupo entre los ~25 grupos activos.

### Modified Capabilities
- (none) — `market-group-rotation` no cambia su contrato; este change consume su output (`performance_monthly` por grupo) sin modificarlo.

## Impact

- **Nuevo**: `backend/app/services/group_strength_service.py`, tests `backend/tests/test_group_strength_service.py`.
- **Modificado**:
  - `backend/app/api/v1/endpoints/transitions.py` — fetch group strengths una vez por request, aplicar multiplier al priority_score (después de ctx_multiplier), enriquecer cada setup con `group_strength`.
  - `backend/app/api/v1/endpoints/queue.py` — fetch group strengths una vez por request, enriquecer cada item con `group_strength` (badge only).
  - `backend/app/services/setup_queue_service.py` — incluir `market_group` en el response de cada lens (hoy no lo devuelve).
  - `frontend/components/dashboard/CompactSetupCard.tsx` — render badge.
  - `frontend/components/dashboard/TopActionableSetups.tsx` — pasar prop a CompactSetupCard.
  - `frontend/app/queue/u-and-r/page.tsx`, `emerging-leaders/page.tsx`, `building-bases/page.tsx` — render badge en filas.
- **Sin cambio**: paths de endpoints, shape principal del response (campo agregado, no breaking), `setup_priority_engine` (multiplier se aplica fuera), sort logic de queue lenses, `market_group_mapping`, scoring weights.
- **DB**: ninguna migración. Lee `stocks.market_group` y `performance_monthly` ya disponibles.
- **Performance**: una query extra por request (`sector_service.calculate_sector_performance`) que ya tiene cache `@cache_sectors`. Costo despreciable.

## Non-goals

- **No tocar el sort key de queue lenses** (U&R sigue ordenando por event_age, emerging por perf_13w, building-bases por atr_range). El group_strength acompaña visualmente pero no decide el orden — cada lens responde a su tesis propia.
- **No suppression dura por grupo débil**. Ningún setup desaparece por estar en grupo bottom. El multiplier suave (0.85) penaliza el ranking pero respeta la decisión del operador. Suppression dura queda reservada para contexto macro (`context_decision_filter`).
- **No métricas combinadas** (percentil × trend × rs_vs_spy del grupo). Phase 1 usa solo percentil de performance_monthly por simplicidad y robustez. Phase 2 puede combinar si recalibración demuestra valor.
- **No recalibración empírica** de los thresholds (top/bottom 20%, multiplier 0.85/1.15). Va al milestone de agosto 2026 junto con `context_decision_filter` y descriptors de market context.
- **No cambia el `setup_priority_engine`**. El multiplier se aplica fuera, igual que `ctx_multiplier`. El engine sigue siendo puro y por-símbolo.
- **No persistencia del multiplier ni snapshot histórico** del group_strength por stock. Es computado en cada request desde el estado actual del heatmap.
- **No badge en `/actionable` distinto al de queue** — mismo componente visual, misma semántica, para consistencia operativa.
