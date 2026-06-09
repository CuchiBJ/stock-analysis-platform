## 1. Backend — modelo + migración [journal-tracking]

- [x] 1.1 Agregar a `JournalTrade` ([backend/app/models/stock.py](../../../backend/app/models/stock.py)): `regime_at_entry: Mapped[Optional[str]]` (String(20)), `system_score_at_entry: Mapped[Optional[float]]`, `group_strength_at_entry: Mapped[Optional[str]]` (String(16)), `leader_health_at_entry: Mapped[Optional[float]]`. Todos nullable.
- [x] 1.2 Crear migración Alembic `add_journal_system_snapshots.py` con `down_revision='<id de add-journal-decision-provenance>'`. ADD COLUMN para las 4, todas nullable, sin server_default (semánticamente "no data yet").
- [x] 1.3 Aplicar local y verificar con `\d journal_trades`.

## 2. Backend — snapshot service [journal-tracking]

- [x] 2.1 Crear `backend/app/services/journal_snapshot_service.py` con función pública `async def take_entry_snapshot(db: AsyncSession, symbol: str, entry_date: date) -> dict`. Devuelve `{"regime_at_entry", "system_score_at_entry", "group_strength_at_entry", "leader_health_at_entry"}`.
- [x] 2.2 Implementar `_regime(db, entry_date)`: consulta `market_context_engine.get_regime_for_date(entry_date)` (o el método actual que devuelve el regime del día). Si no hay data, retorna None.
- [x] 2.3 Implementar `_group_strength(db, symbol, entry_date)`: consulta `group_strength_service` para el grupo del símbolo en esa fecha. None si no hay.
- [x] 2.4 Implementar `_leader_health(db, symbol, entry_date)`: consulta `leader_health_calculator` con métricas de ese día. None si no hay `stock_metrics` para esa fecha.
- [x] 2.5 Implementar `_system_score(db, symbol, entry_date, setup)`: si existe `TransitionObservation` para (symbol, entry_date ±3d), devuelve el score derivado. Si no, consulta `setup_priority_engine.score_setup(setup, metrics)` con las métricas del día. None si no hay métricas.
- [x] 2.6 `take_entry_snapshot` envuelve las 4 llamadas en try/except — cualquier fallo individual deja ese campo en None y loggea warning; nunca propaga.

## 3. Backend — hook en POST /trades [journal-tracking]

- [x] 3.1 En `create_open_trade` ([backend/app/api/v1/endpoints/journal.py](../../../backend/app/api/v1/endpoints/journal.py)), inmediatamente después de `obs_id = await _find_linked_observation(...)`, llamar `snapshot = await take_entry_snapshot(db, symbol, payload.entry_date)`.
- [x] 3.2 Asignar los 4 campos del `JournalTrade(**)` con `regime_at_entry=snapshot["regime_at_entry"]`, etc.
- [x] 3.3 Extender `_trade_to_dict` para incluir los 4 campos en el response.
- [x] 3.4 Importer CSV (`backend/app/services/journal_importer.py`) NO toma snapshots automáticamente — los históricos van por CLI backfill (sección 4).

## 4. Backend — CLI backfill [journal-tracking]

- [x] 4.1 Crear `backend/scripts/backfill_journal_snapshots.py`. CLI que abre `AsyncSessionLocal`, itera todos los `JournalTrade` donde los 4 snapshots son null, llama `take_entry_snapshot` por cada uno, hace UPDATE.
- [x] 4.2 Logging: por trade, una línea `[symbol] [entry_date] regime=X score=Y group=Z health=W` o `MISSING (no metrics)` si todo es None.
- [x] 4.3 Resumen final: `Updated N trades · M missing all snapshots`.
- [x] 4.4 Flag `--dry-run` que no hace commit.

## 5. Backend — stats con regime breakdown [journal-tracking]

- [x] 5.1 En `journal_stats`: agregar `by_regime_at_entry` (lista de `{regime, ...metrics}`, excluyendo trades con `regime_at_entry IS NULL`).
- [x] 5.2 Agregar `by_setup_regime_matrix` análogo al actual `by_setup_context` pero con la dimensión regime. Mantener `by_setup_context` por compatibilidad un release más.

## 6. Frontend — matriz cambia eje [journal-tracking]

- [x] 6.1 Extender `StatsResponse` en [frontend/app/journal/page.tsx](../../../frontend/app/journal/page.tsx) con `by_setup_regime_matrix` y `by_regime_at_entry`.
- [x] 6.2 Card "Setup × Contexto" se renombra a **"Setup × Regime (sistema)"** y usa `by_setup_regime_matrix`. El componente `MatrixTable` queda igual.
- [x] 6.3 Card "Por Contexto" se elimina del dashboard (covered by Spec 4 cleanup; este change la deja igual y Spec 4 la borra).
- [x] 6.4 En `EditTradeModal` agregar sección readonly "Snapshots del sistema al entry" con los 4 valores y un tooltip explicando que son inmutables.

## 7. Frontend — eliminar context del NewTradeModal [journal-tracking]

- [x] 7.1 Quitar el dropdown `context` de `NewTradeModal` ([frontend/app/journal/TradeForms.tsx](../../../frontend/app/journal/TradeForms.tsx)). El backend sigue aceptándolo (campo opcional con default `'unknown'`) — la deprecación es UI-only.
- [x] 7.2 Quitar el campo `context` del payload del POST en `submit()`. El backend recibe `context` implícito como `'unknown'`.

## 8. Verificación [journal-tracking]

- [x] 8.1 Smoke service: crear un test que llame `take_entry_snapshot` para un símbolo conocido (NBIS, fecha con metrics) y verifique que devuelve los 4 valores no-None.
- [x] 8.2 Smoke service edge: misma función con `symbol='ZZZZ'` (no existe) — devuelve dict con 4 None y no levanta.
- [x] 8.3 Smoke API: `POST /journal/trades` con symbol/fecha válidos → response incluye los 4 snapshots populados.
- [x] 8.4 CLI backfill: correr `python scripts/backfill_journal_snapshots.py --dry-run` sobre los 34 históricos; revisar log que al menos los de fechas recientes (con `stock_metrics` disponible) populan.
- [x] 8.5 CLI backfill real: correr sin `--dry-run`, verificar con SQL `SELECT COUNT(*) FROM journal_trades WHERE regime_at_entry IS NOT NULL` que el conteo es > 0.
- [x] 8.6 Frontend: matriz Setup × Regime muestra data correcta para los trades con snapshot; los sin snapshot caen en un bucket "—" / "sin data" visible pero diferenciado.
