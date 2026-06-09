## Why

El modelo actual de `journal_trades` trata cada venta parcial como un trade independiente, pero institucionalmente **son la misma decisión**. Cuando el operador compra 17 BTU una vez y luego vende en 2 parciales, el sistema registra 2 filas cerradas y las contabiliza como 2 winners distintos. La consecuencia es brutalmente concreta para el operador (datos reales del journal, 2026-06-03):

- 8 ganadores a nivel-fila → **3 ganadores reales** a nivel-decisión (BTU 1, TSLA 1, NBIS 1)
- WR aparente 24.2% → **WR real 10.7%**
- BTU 12-12 cuenta como 2 wins; TSLA 12-01 cuenta como 2 wins; MRVL 04-29 cuenta como 2 wins → infla artificialmente cualquier breakdown por setup, contexto, regime, mes, etc.

El problema afecta TODO lo que el journal mide:
- WR / Profit factor / Avg R por setup → contaminado
- Performance Matrix → cohorts con tamaños incorrectos
- Discrecional vs Sistémico (cuando entry_reason esté cargado) → distorsionado igual
- Riesgo del flywheel: el `priority_score` recalibrado con outcomes a nivel-fila va a ponderar mal las cohorts

La causa raíz: ni el importer CSV (FIFO matching) ni el endpoint de cierre parcial mantienen un link entre legs que pertenecen a la misma decisión. Cada child se inserta como huérfano.

Este change defiende:
- Principio **#6 Operational clarity > feature richness** — la unidad operativa de análisis es la **decisión** (entrada-salida), no el evento de ejecución.
- Principio **#7 Interpretability** — el operador piensa en decisiones, no en chunks; el modelo de datos debe coincidir con el modelo mental.

## What Changes

### Modelo

`JournalTrade` ([backend/app/models/stock.py](../../../backend/app/models/stock.py)) gana 1 columna:

- `parent_trade_id: int | null` — apunta al trade representativo de la decisión. Convención:
  - `parent_trade_id IS NULL` → este trade ES el representante de la decisión (típicamente la primera fila creada para esa compra).
  - `parent_trade_id IS NOT NULL` → este es un child (parcial cerrado posterior) que pertenece a la decisión cuyo representante es el id apuntado.
  - El `decision_id` efectivo de cualquier fila es: `COALESCE(parent_trade_id, id)`.

### Importer (FIFO matching)

En [backend/app/services/journal_importer.py](../../../backend/app/services/journal_importer.py), al procesar legs de una Compra:

- Si la Compra se cierra **completamente** en N ventas (no queda qty open): la primera Venta procesada crea el child representativo (parent_trade_id=NULL). Las subsiguientes crean children con `parent_trade_id = first_child.id`.
- Si queda qty open al final del CSV: el OPEN leftover creado al cierre del importer es el representante (parent_trade_id=NULL). Los closed children asociados a esa Compra heredan `parent_trade_id = open_leftover.id`.

Implementación: el `_OpenLeg` interno del importer gana un campo `parent_trade_id: Optional[int]` que se va resolviendo a medida que se crean filas.

### Endpoint de cierre parcial

En `POST /journal/trades/{trade_id}/close` (rama partial), el `closed` child que se crea hereda:

- `parent_trade_id = trade.parent_trade_id` si `trade.parent_trade_id is not None` (el trade en sí ya era un child o un representante).
- `parent_trade_id = trade.id` si `trade.parent_trade_id is None` (el trade era el representante de la decisión).

### Stats endpoint — sección nueva `by_decision`

`journal_stats` agrega una sección nueva al response: `decision_overall` con métricas **a nivel decisión** (no a nivel fila):

- `n_decisions_total`: count de decisiones únicas (`COUNT(DISTINCT COALESCE(parent_trade_id, id))`).
- `n_fully_resolved`: decisiones donde **todas** las legs están cerradas.
- `n_partially_resolved`: alguna leg cerrada y alguna abierta.
- `n_fully_open`: ninguna leg cerrada.
- `decision_wins` / `decision_losses` / `decision_breakeven`: solo de fully_resolved, basado en NET pnl (sum across legs).
- `decision_win_rate`: `decision_wins / (decision_wins + decision_losses)` — solo sobre resolved.
- `decision_total_realized_pnl`: sum de pnl_dollars sobre todas las legs cerradas.
- `decision_total_r`: suma de R-multiples ponderada por qty `sum(r_multiple * qty) / sum(qty)` agregada a nivel decisión y sumada.

Las stats existentes (`overall`, `by_setup`, etc) **se mantienen** sin cambios — el cambio es **aditivo**.

### Frontend dashboard

En `/journal`, debajo del headline trade-level existente, agregar una segunda card **"Decisiones"** con 3 métricas: `Decisions · Decision WR · Total R weighted`. Tooltip explica que un grupo es lo mismo que "una compra y todas sus ventas parciales".

En la sección de "Trades cerrados" colapsable, agregar columna `Decision id` (mostrar `COALESCE(parent_trade_id, id)`) para que el operador pueda agrupar visualmente parciales que vienen juntos.

### Backfill CLI

`backend/scripts/backfill_journal_decisions.py`:

- Agrupa filas existentes por `(symbol, entry_date, entry_price)` (estos 3 campos identifican unívocamente la decisión original).
- Para cada grupo con más de 1 leg, identifica el "representante" así:
  - Si hay alguna leg OPEN → ese es el representante (`parent_trade_id` = NULL para ella).
  - Si todas están closed → el de `id` más bajo es representante.
- Actualiza los otros children con `parent_trade_id = representante.id`.
- `--dry-run` soportado. Imprime grupos detectados, conteos, y resumen final.

## Non-goals

- **No** se introduce una tabla nueva `journal_decisions` — el `parent_trade_id` self-referential es suficiente y mantiene queries simples.
- **No** se modifica la lógica del importer para evitar crear children huérfanos del open leftover — el orden actual (closed children durante walk, open leftover al final) se preserva; solo se enlazan después.
- **No** se cambia el cálculo de R-multiple a nivel fila — sigue siendo `(exit-entry) / (entry-initial_stop)`. El decision-level R es un agregado nuevo que SUMA los R individuales ponderados por qty.
- **No** se restructura la UI de tablas (agrupación visual con expanders, etc) — primero se exponen los datos honestos, después se discute layout. Cambios visuales fuertes corren riesgo de drift cosmético.
- **No** se eliminan las stats trade-level — el operador puede querer ambas vistas. El default headline trade-level se mantiene; las decision-level se agregan.
- **No** se persiste un campo derivado `decision_id` separado — `COALESCE(parent_trade_id, id)` se computa on-demand en SQL/Python según se necesite.

## Capabilities

### Modified Capabilities

- **`journal-tracking`** — extendida con representación de decisiones operativas (1 entrada = 1 decisión = N ejecuciones), agregaciones nuevas decision-level, y backfill CLI sobre datos existentes.

## Impact

- **Code**:
  - Backend: 1 columna nueva en `JournalTrade`, migración Alembic, modificación del importer para asignar parent_trade_id durante FIFO walk + post-walk open leftover linkage (~50 LOC), modificación del close endpoint (~5 LOC), nueva sección `decision_overall` en `journal_stats` (~30 LOC), CLI backfill (~60 LOC).
  - Frontend: card "Decisiones" en headline (~20 LOC), columna "Decision id" en Trades cerrados (~10 LOC).
- **APIs**: `journal_stats` gana sección `decision_overall`. `_trade_to_dict` gana `parent_trade_id`. No breaking.
- **DB**: 1 migración con 1 columna. Backfill afecta ~10 filas históricas (las que tienen parciales).
- **Dependencias**: ninguna. Independiente de specs pendientes (`add-take-from-queue-workflow`).
- **Riesgo**: bajo. Cambio aditivo en stats, no destruye nada. La columna es nullable; queries existentes siguen funcionando.
