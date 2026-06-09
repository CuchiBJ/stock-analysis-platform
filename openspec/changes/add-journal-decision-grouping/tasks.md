## 1. Backend — modelo + migración [journal-tracking]

- [x] 1.1 Agregar columna `parent_trade_id: Mapped[Optional[int]]` a `JournalTrade` con índice ([backend/app/models/stock.py](../../../backend/app/models/stock.py)).
- [x] 1.2 Migración Alembic `add_journal_decision_grouping.py` con `down_revision='f5a6b7c8d9e0'`: ADD COLUMN nullable + CREATE INDEX `ix_journal_parent_trade_id`.
- [x] 1.3 Aplicar local y verificar.

## 2. Backend — endpoint cierre parcial [journal-tracking]

- [x] 2.1 En `close_trade` rama parcial ([backend/app/api/v1/endpoints/journal.py](../../../backend/app/api/v1/endpoints/journal.py)): al crear el `closed = JournalTrade(...)` child, setear `parent_trade_id = trade.parent_trade_id if trade.parent_trade_id is not None else trade.id`.

## 3. Backend — importer FIFO [journal-tracking]

- [x] 3.1 En `_OpenLeg` ([backend/app/services/journal_importer.py](../../../backend/app/services/journal_importer.py)) agregar campo `parent_trade_id: Optional[int] = None` y `first_child_was_open: bool = False`.
- [x] 3.2 Modificar `import_csv` para que al crear cada child cerrado de una leg, si `leg.parent_trade_id is None`: este child será el representante temporal — guardar referencia para asignar a siblings posteriores. Si `leg.parent_trade_id is not None`: el child hereda directamente. **Importante**: los IDs se asignan en `db.flush()` no antes; necesitamos persistir en orden y enlazar.
- [x] 3.3 Estrategia simple: durante el walk de Ventas, en lugar de hacer `parsed.append(...)`, mantener una lista por (symbol, compra_source_row) con sus ParsedTrade children. Después del walk, antes de persistir:
  - Si la Compra tiene leftover open → el open va primero (parent=NULL), todos los closed children apuntan a él.
  - Si la Compra se cerró completa → el primer closed (cronológico) va primero (parent=NULL), los demás apuntan a él.
- [x] 3.4 Persistir las filas en el orden correcto (representante primero), llamar `db.flush()` para obtener IDs, después asignar `parent_trade_id` en siblings, commit.

## 4. Backend — stats decision_overall [journal-tracking]

- [x] 4.1 En `journal_stats`: nueva sección `decision_overall`. Primero construir mapping `decision_id_for(t) = t.parent_trade_id or t.id`.
- [x] 4.2 Agrupar `rows` por decision_id en Python. Para cada grupo computar:
  - `n_legs`, `n_closed`, `n_open`
  - `net_pnl = sum(_derive_pnl(t) for t in group)` (solo legs con pnl no-None)
  - `weighted_r = sum(_derive_r(t) * t.qty for t in group si R y qty) / sum(t.qty si R)`
  - estado: `fully_resolved` si n_open=0 y n_closed>0; `partially_resolved` si ambos >0; `fully_open` si n_closed=0.
- [x] 4.3 Agregar metric: `n_decisions_total`, `n_fully_resolved`, `n_partially_resolved`, `n_fully_open`, `decision_wins/losses/breakeven` (solo fully_resolved por net_pnl), `decision_win_rate = wins/(wins+losses)`, `decision_total_realized_pnl = sum(net_pnl)`, `decision_total_r = sum(weighted_r)`.
- [x] 4.4 Incluir `decision_overall` en el response final de `journal_stats`.

## 5. Backend — `_trade_to_dict` y endpoints auxiliares [journal-tracking]

- [x] 5.1 En `_trade_to_dict` agregar key `parent_trade_id`: `t.parent_trade_id`.
- [x] 5.2 Agregar `decision_id`: `t.parent_trade_id if t.parent_trade_id is not None else t.id`.

## 6. Backend — CLI backfill [journal-tracking]

- [x] 6.1 Crear `backend/scripts/backfill_journal_decisions.py`. Lista todas las filas, agrupa por `(symbol, entry_date, entry_price)`. Para grupos con >1 leg:
  - Si hay alguno OPEN: ese es representante (parent_trade_id=NULL — ya lo está).
  - Si todos closed: el de menor id es representante.
  - Setear `parent_trade_id = representante.id` en los demás.
- [x] 6.2 Soportar `--dry-run`. Log por grupo: `[symbol entry_date] N legs → representante=id, children=[ids]`.
- [x] 6.3 Resumen final: grupos procesados, filas updated.

## 7. Frontend — headline Decisiones card [journal-tracking]

- [x] 7.1 Extender `StatsResponse` en [frontend/app/journal/page.tsx](../../../frontend/app/journal/page.tsx) con `decision_overall: { n_decisions_total, n_fully_resolved, decision_wins, decision_losses, decision_win_rate, decision_total_realized_pnl, decision_total_r, ... }`.
- [x] 7.2 Renderizar card adicional debajo del headline trade-level con 3 métricas: Decisiones (N), Decision WR, Decision Total R. Tooltip explica "una compra y todas sus ventas parciales".

## 8. Frontend — columna decision_id en Trades cerrados [journal-tracking]

- [x] 8.1 Extender `Trade` interface en [frontend/app/journal/TradeForms.tsx](../../../frontend/app/journal/TradeForms.tsx) con `parent_trade_id: number | null` y `decision_id: number`.
- [x] 8.2 En la tabla "Trades cerrados", agregar columna chica `Decision id` mostrando `t.decision_id`. Filas que comparten decision_id quedan visualmente identificables sin restructurar el render.

## 9. Verificación [journal-tracking]

- [x] 9.1 Smoke API: `POST /journal/trades` → response trae `parent_trade_id=null` y `decision_id=id`.
- [x] 9.2 Smoke parcial: crear trade qty=10, partial-close 3 → response.closed tiene `parent_trade_id = trade.id`; trade original sigue con `parent_trade_id=null`.
- [x] 9.3 Backfill dry-run: ejecutar sobre histórico, verificar que detecta BTU, TSLA, MRVL, NBIS, VECO como grupos. Imprime preview.
- [x] 9.4 Backfill real: ejecutar, verificar con SQL `SELECT decision_id, COUNT(*) FROM (SELECT COALESCE(parent_trade_id, id) AS decision_id FROM journal_trades) x GROUP BY 1 HAVING COUNT(*) > 1` que los grupos están bien.
- [x] 9.5 Stats: `journal_stats.decision_overall.n_decisions_total < n_total` (porque hay grupos); `decision_win_rate` distinto de `overall.win_rate`.
- [x] 9.6 Frontend: card "Decisiones" visible con números reales (decisiones < trades, WR menor); columna decision_id en cerrados muestra IDs agrupados.
