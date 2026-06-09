## 1. Frontend — recortar dashboard [journal-tracking]

- [x] 1.1 En [frontend/app/journal/page.tsx](../../../frontend/app/journal/page.tsx) reducir la grilla de headline metrics de 6 cards a 3: **Trades · Expectancy · Avg R**. Eliminar el JSX de Win rate, Profit factor, Total P&L de la sección headline.
- [x] 1.2 Eliminar la Card stand-alone "Por Contexto" entera (incluyendo su `BreakdownTable`). El componente `BreakdownTable` se mantiene — solo se elimina el render para context.
- [x] 1.3 Eliminar las columnas "PF" y "Avg R" / "Total P&L" / "Avg duration" según corresponda en `BreakdownTable` (mantener N, WR, Expect). Validar al modificar el componente que el render por `setup` siga funcionando.
- [x] 1.4 Eliminar la columna "Días" de la tabla "Trades cerrados".
- [x] 1.5 Envolver la sección "Trades cerrados" en un `<details>` con `<summary>Trades cerrados (N) ▸</summary>`. Cerrado por default.

## 2. Frontend — recortar forms [journal-tracking]

- [x] 2.1 En [frontend/app/journal/TradeForms.tsx](../../../frontend/app/journal/TradeForms.tsx), eliminar el campo `post_venta` del `NewTradeModal` (no es parte del create flow — el operador solo lo carga post-cierre si quiere, vía edit).
- [x] 2.2 En `CloseTradeModal`, quitar el `required` de `error_note` (mantenerlo como texto opcional con placeholder "nuance opcional").
- [x] 2.3 En `EditTradeModal`, asegurar que `post_venta` sigue siendo editable. Sin cambios funcionales adicionales acá.

## 3. Backend — dejar de persistir derivables [journal-tracking]

- [x] 3.1 En [backend/app/api/v1/endpoints/journal.py](../../../backend/app/api/v1/endpoints/journal.py), en `create_open_trade`: NO setear `cost_total` en el `JournalTrade(**)`. Dejar el campo a null en filas nuevas.
- [x] 3.2 En `_compute_outcomes`: dejar de asignar `trade.pnl_pct` y `trade.duration_days`. Solo asignar `trade.pnl_dollars` y `trade.r_multiple` (que son métricas operativas, no derivables triviales en una sola formula UI-amigable). Comentar la decisión en el código.
- [x] 3.3 En `_trade_to_dict`: agregar lógica de cómputo on-the-fly:
  ```
  cost_total = t.cost_total if t.cost_total is not None else (t.entry_price * t.qty if t.entry_price and t.qty else None)
  pnl_pct = t.pnl_pct if t.pnl_pct is not None else ((t.exit_price / t.entry_price - 1.0) if t.exit_price and t.entry_price else None)
  duration_days = t.duration_days if t.duration_days is not None else ((t.exit_date - t.entry_date).days if t.exit_date and t.entry_date else None)
  ```
  Esto preserva los valores de los 34 históricos (que sí los tienen) y computa para trades nuevos.
- [x] 3.4 En `patch_trade`: mantener la rama `if needs_recompute` igual pero NO setear `cost_total`, `pnl_pct`, `duration_days` en el row (van a quedar siempre como cache opcional, no como fuente de verdad).

## 4. Backend — documentar deprecation [journal-tracking]

- [x] 4.1 Agregar docstrings o comentarios en `JournalTrade` ([backend/app/models/stock.py](../../../backend/app/models/stock.py)) marcando `cost_total`, `pnl_pct`, `duration_days`, `post_venta`, `context` como **deprecated — no longer populated by new trades; preserved for historical compatibility. Computed on-demand in response.**
- [x] 4.2 No hacer migración. Las columnas siguen.

## 5. Verificación [journal-tracking]

- [x] 5.1 Frontend smoke: abrir `/journal` después del cambio. Confirmar 3 cards de headline. Confirmar que "Trades cerrados" aparece como `<details>` cerrado con conteo.
- [x] 5.2 Frontend smoke: crear trade nuevo via "Nuevo trade". Form NO muestra `post_venta`. Cerrar trade — `error_note` no es required.
- [x] 5.3 Backend smoke: `POST /journal/trades` → response trae `cost_total` computado (entry_price * qty) aunque la DB row tiene null. Verificar con `SELECT cost_total FROM journal_trades WHERE id=<nuevo>` que la columna está null.
- [x] 5.4 Backend smoke: `GET /journal/trades?closed_only=true` → trades históricos siguen mostrando `cost_total`, `pnl_pct`, `duration_days` no-null (cargados desde DB). Trades nuevos cerrados muestran los mismos campos no-null (computados on-the-fly).
- [x] 5.5 Backend smoke: `journal_stats` sigue retornando todas las métricas (profit_factor, total_pnl, avg_duration_days en el response) — solo no se muestran en headline frontend.
