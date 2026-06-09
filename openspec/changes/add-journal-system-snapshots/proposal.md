## Why

El journal actual depende de un campo `context` que el operador llena a mano con etiquetas inconsistentes ("Choppy", "Favorable", "RS agains market", vacío). Los engines del sistema (`market_context_engine`, `group_strength_service`, `leader_health_calculator`, `quality_leader_gate`+`setup_priority_engine`) ya saben la respuesta objetiva a cada una de esas dimensiones para el (símbolo, fecha) del trade. La consecuencia del gap:

- La matriz `Setup × Context` mezcla 3 lecturas distintas: Choppy de Enero (sub-juicio del operador), Favorable de Abril (otro sub-juicio), vacío de Mayo (no cargó). No se puede agregar honestamente.
- No se puede responder "¿qué setup falla en liderazgo deteriorándose?" porque no hay snapshot de `leader_health` al entry.
- No se puede responder "¿qué setup gana en grupos fuertes?" porque no hay snapshot de `group_strength`.
- No se puede medir si el operador entra en setups que el sistema considera de bajo score, porque `system_score_at_entry` no existe.

Este change defiende:
- Principio **#5 Regime affects everything** — el régimen del sistema debe gobernar la atribución, no el juicio post-hoc.
- Principio **#9 Institutional sponsorship is primary signal** — `group_strength` y `leader_health` deben quedar congelados al entry para correlacionar.
- Principio **#7 Interpretability** — usar outputs determinísticos de engines existentes, no inferir.

## What Changes

- **Modelo `JournalTrade`** ([backend/app/models/stock.py](../../../backend/app/models/stock.py)) gana 4 columnas:
  - `regime_at_entry: str | null` — output literal de `market_context_engine` (`expansive` / `neutral` / `choppy` / `adverse` o el vocabulario actual del engine)
  - `system_score_at_entry: float | null` — el `priority_score` del setup más cercano al símbolo; computado on-demand vía el mismo scoring que usa el queue
  - `group_strength_at_entry: str | null` — `weak` / `neutral` / `strong` desde `group_strength_service`
  - `leader_health_at_entry: float | null` — score 0-1 desde `leader_health_calculator`
- **Servicio nuevo** `backend/app/services/journal_snapshot_service.py` con función `async def take_entry_snapshot(db, symbol, entry_date) -> dict`. Encapsula las 4 llamadas a engines existentes; devuelve dict con valores `null` cuando algún input no está disponible (sin levantar).
- **Hook en `POST /journal/trades`** ([backend/app/api/v1/endpoints/journal.py](../../../backend/app/api/v1/endpoints/journal.py)): inmediatamente antes del `db.add(trade)`, invoca `take_entry_snapshot` y popula los 4 campos. Si el servicio falla, los campos quedan en null pero el trade se crea (no bloqueante).
- **`system_score_at_entry` con fallback on-demand**: cuando no hay `linked_observation_id`, el snapshot service consulta `setup_priority_engine` con el `setup` declarado del trade + las métricas del símbolo en la fecha de entry; produce un score comparable. Esto da score incluso para trades discrecionales.
- **Deprecación del `context` manual**: `NewTradeModal` y `EditTradeModal` dejan de mostrar el dropdown `context`. La columna se mantiene en DB para no romper histórico ni el importer CSV (que sí lo lee). Stats endpoint sigue exponiéndolo pero el dashboard cambia.
- **Performance Matrix nuevo**: en `/journal`, la matriz pasa de `Setup × context (manual)` a **`Setup × regime_at_entry`**. El context manual queda accesible solo en drill-in (vista detallada de cada trade).
- **CLI `scripts/backfill_journal_snapshots.py`**: corre sobre los 34 trades históricos. Para cada uno consulta `stock_metrics` por (símbolo, entry_date) y deriva los 4 snapshots best-effort; los que no tengan datos quedan null. Imprime resumen `{updated: N, missing: M}`.

## Non-goals

- **No** se incluye `days_since_first_signal` — requiere walk-back de observations y heurística para "primera detección" vs "re-trigger"; va en spec aparte cuando se prueben los primeros 4 snapshots.
- **No** se hace `DROP COLUMN context` — el importer CSV histórico todavía lo usa y los 34 trades viejos tienen valores. La deprecación es UI-only en este change.
- **No** se updatean los snapshots si el operador edita `entry_date` post-creación — los snapshots son congelados al primer save (igual que `linked_observation_id`).
- **No** se persisten histories de cómo el snapshot cambió día a día durante el trade abierto — solo el state al entry.
- **No** se construye Performance Matrix por `leader_health_bucket` o `group_strength` todavía — solo `regime_at_entry`. Las otras dimensiones se exponen vía drill-in y filtros futuros.

## Capabilities

### Modified Capabilities

- **`journal-tracking`** — extendida con 4 snapshots determinísticos al entry y reemplazo de la dimensión principal del Performance Matrix de `context` (subjetivo) a `regime_at_entry` (objetivo).

## Impact

- **Code**:
  - Backend: 4 columnas nuevas en `JournalTrade`, migración Alembic, nuevo `journal_snapshot_service.py` (~80 LOC), hook en `create_open_trade`, CLI script `scripts/backfill_journal_snapshots.py`
  - Frontend: matriz cambia su segundo eje a `regime_at_entry` en [frontend/app/journal/page.tsx](../../../frontend/app/journal/page.tsx); `NewTradeModal` elimina el dropdown `context`; `EditTradeModal` muestra los 4 snapshots como readonly
- **APIs**: `GET /journal/stats` agrega `by_regime_at_entry` y `by_setup_regime_matrix`; `GET /journal/trades` incluye los 4 campos. No breaking.
- **DB**: migración con 4 columnas. Backfill sobre 34 filas (best-effort, idempotente).
- **Dependencias**: ninguna nueva. Reusa engines existentes.
- **Performance**: `take_entry_snapshot` ejecuta 3-4 queries livianas a tablas indexadas. Latencia esperada < 50ms en POST /trades. Sin impacto perceptible.
