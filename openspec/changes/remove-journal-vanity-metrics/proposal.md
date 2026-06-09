## Why

La auditoría institucional del journal (2026-06-03) identificó que la sección quedó construida con mentalidad de portfolio tracker: headline de 6 métricas con Total P&L / Profit factor / Avg duration en grande, una card "Por Contexto" stand-alone que duplica al Performance Matrix, y campos persistidos en DB (`cost_total`, `pnl_pct`, `duration_days`) que son puramente derivables y solo agregan ruido. El veredicto fue: si pongo `/journal` al lado del journal de TradingView o Edgewonk, no se distinguen — y eso es mortal para un operating system que tiene que defenderse como producto institucional.

Este change corta el drift cosmético antes de que se fosilice. El criterio es brutal: si una métrica no afecta una decisión operativa (entrar, no entrar, salir, ajustar size), no merece headline.

Este change defiende:
- Principio **#6 Operational clarity > feature richness** — recortar la superficie visible obliga a que lo que queda decida.
- Principio **#10 Workflow > analytics** — Total P&L como headline es analytics; Trades / Expectancy / Avg R son señales que el operador puede usar mañana.

## What Changes

### Removed from primary view

- **Card "Por Contexto" stand-alone** en [frontend/app/journal/page.tsx](../../../frontend/app/journal/page.tsx) — la dimensión `context` queda completamente fuera del dashboard. El Performance Matrix (`add-journal-system-snapshots` lo migra a `Setup × regime_at_entry`) cubre la única vista de contexto que importa.
- **Headline metric "Profit factor"** — métrica de fondo de cobertura, no afecta una decisión swing.
- **Headline metric "Avg duration"** y columnas `avg_duration_days` en `by_setup` / `by_context` / `by_setup_context` — curiosity metric.
- **Headline metric "Total P&L"** — vanity número. Solo se preserva en drill-in / stats endpoint.
- **Headline metric "Win rate"** y **"Profit factor"** — los headlines pasan de 6 a **3 cards**: **Trades · Expectancy · Avg R**.

### Modified — visibility / persistence

- **Tabla "Trades cerrados"** en `/journal`: pasa de visible siempre a **collapsible** (`<details>` cerrado por default con contador `Trades cerrados (39) ▸`).
- **Campos `cost_total`, `pnl_pct`, `duration_days`** dejan de **persistirse** en `POST /journal/trades` y `POST /trades/{id}/close`. El backend los **computa on-the-fly** dentro de `_trade_to_dict` cuando el response los necesita. Las columnas no se eliminan de DB todavía (compat con histórico) — sí se documenta que están deprecated.
- **Campo `post_venta`** sale de `NewTradeModal` y de la tabla principal. **Permanece** editable solo en `EditTradeModal`. No se borra del modelo ni de la DB — los 39 ya cargados quedan accesibles en drill-in. Se reevalúa la eliminación en 6 meses según uso.
- **Campo `error_note`** deja de ser required en `CloseTradeModal` (ya no es la única forma de categorizar la salida — `exit_reason` de `add-journal-decision-provenance` ocupa ese rol). Queda como texto libre opcional ("nuance / contexto").

## Non-goals

- **No** se hace `DROP COLUMN` de `cost_total`, `pnl_pct`, `duration_days`, `post_venta` ni `context` — el modelo va a seguir cambiando con los otros 3 changes y un drop temprano fuerza migraciones complicadas. Las columnas quedan en DB sin escribirse desde este change.
- **No** se elimina el cálculo de profit_factor / total_pnl / avg_duration del response del endpoint `journal_stats` — siguen ahí para drill-in / API consumers. Solo dejan de tener tratamiento headline en el dashboard.
- **No** se redesigna el matrix ni los breakdowns por setup / context — esos cambios son responsabilidad de `add-journal-system-snapshots`. Este change solo recorta lo que sobra.
- **No** se introduce ninguna métrica nueva. Es exclusivamente un change de eliminación / reordenamiento.

## Capabilities

### Modified Capabilities

- **`journal-tracking`** — recortada la superficie visible y desacoplada la persistencia de campos derivables.

## Impact

- **Code**:
  - Backend: ~10 LOC eliminadas en [backend/app/api/v1/endpoints/journal.py](../../../backend/app/api/v1/endpoints/journal.py) (dejar de poblar 3 campos en `create_open_trade`, `close_trade`, `patch_trade`); `_compute_outcomes` ya no asigna `pnl_pct` ni `duration_days` a la fila (los computa el `_trade_to_dict`).
  - Frontend: ~80 LOC eliminadas en [frontend/app/journal/page.tsx](../../../frontend/app/journal/page.tsx) (3 metric cards, 1 Card stand-alone, columnas de tablas, wrapping de tabla cerrados); ~10 LOC eliminadas en [frontend/app/journal/TradeForms.tsx](../../../frontend/app/journal/TradeForms.tsx) (campo post_venta del create, required de error_note).
- **APIs**: No breaking. El endpoint sigue retornando todos los campos derivables (computados on-the-fly) y todas las stats. Solo cambia qué se persiste.
- **DB**: ninguna migración. Columnas siguen, dejan de poblarse en filas nuevas.
- **Histórico**: los 34 trades viejos ya tienen `cost_total`, `pnl_pct`, `duration_days`, `post_venta` populados desde el importer CSV. Quedan accesibles. Los nuevos trades creados via API quedan con esos campos null (response los completa en runtime desde entry/exit/qty).
- **Dependencias**: ninguna nueva. Independiente de los otros 3 changes (puede mergearse primero).
