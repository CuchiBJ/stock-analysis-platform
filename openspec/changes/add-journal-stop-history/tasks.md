## 1. Backend — modelo + migración [journal-tracking]

- [x] 1.1 Agregar columna `initial_stop_price: Mapped[Optional[float]]` en `JournalTrade` ([backend/app/models/stock.py](../../../backend/app/models/stock.py)).
- [x] 1.2 Crear modelo `JournalStopEvent` en mismo archivo con: `id` (pk), `trade_id` (fk integer, indexed), `old_stop_price` (Float, nullable), `new_stop_price` (Float, nullable), `kind` (String(20)), `occurred_at` (DateTime tz=true, default utcnow), `auto_classified` (Boolean, default true).
- [x] 1.3 Migración Alembic `add_journal_stop_history.py` con `down_revision='e4f5a6b7c8d9'`. ADD COLUMN para `initial_stop_price`, CREATE TABLE para `journal_stop_events` con FK constraint + índice en `trade_id`.
- [x] 1.4 Aplicar local y verificar tabla creada + columna nueva.

## 2. Backend — auto-classify helper [journal-tracking]

- [x] 2.1 En [backend/app/api/v1/endpoints/journal.py](../../../backend/app/api/v1/endpoints/journal.py) agregar función `_classify_stop_change(old: Optional[float], new: Optional[float], entry_price: float) -> str`. Reglas: si old is None y new is not None → `initial`; si new is None y old is not None → `removed`; si new >= entry_price (con tolerancia 1e-6) → `moved_to_be`; si new > old → `trailed_up`; si new < old → `widened`; si new == old → None (no event).
- [x] 2.2 Función `_record_stop_event(db, trade_id, old, new, kind, auto=True)` que crea y agrega un `JournalStopEvent` al session.

## 3. Backend — POST hook [journal-tracking]

- [x] 3.1 En `create_open_trade`: si `payload.stop_price` is not None, setear `initial_stop_price=payload.stop_price` en el JournalTrade(). Después del commit (cuando trade.id existe), insertar evento `kind='initial'` con `old=None, new=payload.stop_price` y commit.

## 4. Backend — PATCH hook [journal-tracking]

- [x] 4.1 En `patch_trade`: capturar `old_stop = trade.stop_price` ANTES de aplicar updates. Después de los `setattr` pero antes del commit final, si `'stop_price' in updates`:
  - Si `trade.initial_stop_price is None and trade.stop_price is not None`: setear initial_stop_price = trade.stop_price.
  - Calcular `kind = _classify_stop_change(old_stop, trade.stop_price, trade.entry_price)`.
  - Si `kind is not None`: invocar `_record_stop_event(db, trade.id, old_stop, trade.stop_price, kind)`.
- [x] 4.2 Mantener la lógica existente de `needs_recompute` — pero ahora `_compute_outcomes` SIN cambios; lo que cambia es `_derive_r` (sección 5).

## 5. Backend — R-multiple honesto [journal-tracking]

- [x] 5.1 En `_derive_r(t)`: nueva prioridad — si `t.r_multiple is not None` devolver eso (persistido). Sino: usar `stop = t.initial_stop_price if t.initial_stop_price is not None else t.stop_price`. Si `t.exit_price`, `t.entry_price`, `stop` están y `entry_price > stop` → return `(exit - entry) / (entry - stop)`. Sino None.
- [x] 5.2 En `_compute_outcomes(trade)`: usar `initial_stop_price` cuando exista para escribir el cache `trade.r_multiple`. Mantener fallback a `stop_price` para back-compat con trades CSV-imported sin initial.

## 6. Backend — endpoint stop-history + response shape [journal-tracking]

- [x] 6.1 Nuevo endpoint `GET /journal/trades/{trade_id}/stop-history` que devuelve `{"events": [...]}` ordenado por `occurred_at` ascendente.
- [x] 6.2 En `_trade_to_dict` agregar 2 campos:
  - `initial_stop_price`: `t.initial_stop_price`
  - `is_risk_free`: derived bool — `True` cuando `t.stop_price is not None and t.entry_price is not None and t.stop_price >= t.entry_price`.

## 7. Frontend — Open Positions badge [journal-tracking]

- [x] 7.1 Extender `Trade` interface en [frontend/app/journal/TradeForms.tsx](../../../frontend/app/journal/TradeForms.tsx) con `initial_stop_price: number | null` y `is_risk_free: boolean`.
- [x] 7.2 En la columna "Stop" de Open Positions table en [frontend/app/journal/page.tsx](../../../frontend/app/journal/page.tsx), cuando `t.is_risk_free` es true, mostrar un badge chico verde **`🔒 BE`** junto al valor numérico.

## 8. Frontend — EditTradeModal stop history section [journal-tracking]

- [x] 8.1 En `EditTradeModal` ([frontend/app/journal/TradeForms.tsx](../../../frontend/app/journal/TradeForms.tsx)) agregar un `useEffect` que al montar fetchea `GET /journal/trades/{id}/stop-history` y guarda en estado `stopEvents`.
- [x] 8.2 Renderizar tabla read-only abajo de la sección de snapshots: "Historial de stop" con columnas Fecha · Tipo · Old → New. Si `stopEvents.length === 0` mostrar mensaje "sin cambios registrados".

## 9. Verificación [journal-tracking]

- [x] 9.1 Smoke API: `POST /journal/trades` con stop_price=95 → response trae `initial_stop_price=95`; `GET /stop-history` trae 1 evento `kind='initial'`.
- [x] 9.2 Smoke API: PATCH a stop_price=100 sobre un trade con entry=100 → evento `kind='moved_to_be'` registrado; `is_risk_free=true` en response.
- [x] 9.3 Smoke API: PATCH a stop_price=97 (entry=100, old=95) → evento `kind='trailed_up'`; `is_risk_free=false` (97 < 100).
- [x] 9.4 Smoke R-multiple: trade con `initial_stop=95, entry=100, exit=110` y `stop_price` actual = 100 (movido a BE) → r_multiple usa initial=95 → r = 10/5 = 2.0 (no infinity).
- [x] 9.5 Frontend smoke: crear posición abierta con stop_price=95 entry=100. PATCH stop a 100 vía EditModal. Open Positions row muestra `🔒 BE` junto al stop. EditModal muestra 2 eventos en historial.
- [x] 9.6 Histórico: trades viejos (sin initial_stop_price) siguen funcionando — `_derive_r` cae al fallback `stop_price`, `is_risk_free` se computa correctamente.
