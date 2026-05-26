## Why

`MarketContextDrawer` renderiza **19 métricas crudas** (9 participation + 10 leadership) más una sección "Coming in Phase 2-4" con **5 placeholders "pending"**. El operador decide con 4-6 números — el resto es instrumentar-todo theater.

La auditoría institucional (mayo 2026) lo identifica como uno de los 3 surfaces con drift más visible: existe detrás de un click (mitiga ruido en el dashboard principal), pero su contenido viola **Principio 3 (context compression mandatory)** y **Principio 6 (operational clarity > feature richness)** apenas se abre. Es honest pero saturante.

Mismo patrón que `simplify-compact-setup-card`: las métricas crudas son útiles para debug ocasional, no para decisión. Mover a un toggle "Raw metrics" mantiene la trazabilidad sin penalizar el caso de uso primario.

## What Changes

- **Reducir métricas visibles por defecto de 19 a 6**, divididas:
  - **Participation (3)**: `breadth_above_ema21`, `breadth_momentum_5d`, `highs_lows_ratio`
  - **Leadership (3)**: `leader_count`, `leader_count_delta_20d`, `leader_climactic_count`
  - Estas son las que el audit explícitamente lista como "las que cambian decisión" más el `highs_lows_ratio` (señal sintética de salud de extremos) y `climactic_count` (señal de agotamiento, primer riesgo a vigilar).
- **Las 13 métricas restantes** (`breadth_above_ema50`, `breadth_above_ema200`, `breadth_momentum_20d`, `near_highs_count`, `near_lows_count`, `participation_persistence`, `leader_count_delta_5d`, `leader_pullback_quality_avg`, `leader_tightness_avg`, `leader_vol_contraction_avg`, `leader_rs_persistence_10d`, `leader_extension_count`, `leadership_turnover_5d`) pasan detrás de un toggle "Raw metrics" colapsado por defecto.
- **Wait — incluir `leader_pullback_quality_avg` en el set primario** (es uno de los 6 que el audit lista explícitamente). Re-balanceo:
  - **Participation (3)**: `breadth_above_ema21`, `breadth_momentum_5d`, `highs_lows_ratio`
  - **Leadership (3)**: `leader_count`, `leader_count_delta_20d`, `leader_pullback_quality_avg`, `leader_climactic_count` → son 4, total 7, no 6
  - **Decisión final**: aceptar 7 (no 6) en el primer corte. Pullback quality es esencial para "qué tan sana es la pullback actual del liderazgo" — sacarlo penaliza decisión. El audit dice "3-4 que un trader usa", 7 está cerca y respeta los explícitamente nombrados.
- **Colapsar la sección "Coming in Phase 2-4"** de 5 cards individuales a una sola línea: `Phase 2–4 pending: persistence, forgiveness, rotation, volatility, follow-through`.
- **Eliminar la nota "20d sample size" del footer** — info de debug, no operacional. (Mantener `as_of` y `universe_size` que sí dan contexto temporal/cobertura.)

Resultado: 19 + 5 + sample-size nota = 25 elementos informacionales → 7 + 1 + 0 = 8 elementos por defecto (con toggle disponible para los 13 raw metrics). 68% de reducción.

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- (none) — Simplificación de presentación. No cambia la API `/api/v1/market-context/current` ni el shape de `MarketContextData`; todas las métricas siguen llegando del backend para preservar el toggle "Raw metrics" sin segundo fetch.

## Impact

- **Modificado**: `frontend/components/dashboard/MarketContextDrawer.tsx` — re-estructurar las secciones, agregar toggle controlado por estado local.
- **Sin cambios**: `MarketContextBar.tsx`, backend `market_context.py`, `MarketContextEngine`, ningún tipo `MarketContextData`.
- **Visualmente afecta solo el drawer** (panel lateral); el dashboard principal y el `MarketContextBar` no cambian.

## Non-goals

- No tocar el shape del backend `/market-context/current` ni los engines.
- No tocar `MarketContextBar`.
- No introducir librería de animación para el toggle — `useState` + render condicional simple.
- No persistir el estado del toggle en localStorage (re-colapsa al cerrar/reabrir el drawer; aceptable porque el drawer es modal efímero).
- No introducir tooltips por métrica explicando qué significa cada una (out-of-scope; el `/guide` puede cubrir documentación).
- No retirar el "Phase 2-4 pending" section por completo — colapsar pero mantener visibilidad de qué viene.
