## 1. Backend — modelo + migración [journal-tracking]

- [x] 1.1 Agregar a `JournalTrade` ([backend/app/models/stock.py](../../../backend/app/models/stock.py)): `from_queue: Mapped[Optional[bool]]`, `entry_reason: Mapped[str]` (default `'other'`, nullable=False), `exit_reason: Mapped[str]` (default `'unknown'`, nullable=False)
- [x] 1.2 Crear migración Alembic `add_journal_decision_provenance.py` con `down_revision='b1c2d3e4f5a6'`. ADD COLUMN para las 3 con server_default seguros (`from_queue=NULL`, `entry_reason='other'`, `exit_reason='unknown'`); backfill UPDATE no necesario porque server_default cubre filas existentes.
- [x] 1.3 Aplicar migración local y verificar con `\d journal_trades` que las 3 columnas existen con sus defaults.

## 2. Backend — vocabularios y Pydantic [journal-tracking]

- [x] 2.1 En [backend/app/api/v1/endpoints/journal.py](../../../backend/app/api/v1/endpoints/journal.py) agregar constantes `ENTRY_REASON_OPTIONS = ["queue_signal","discretionary","continuation","news","other"]` y `EXIT_REASON_OPTIONS = ["stop_hit","target","trail","thesis_broken","discretionary","partial_take","unknown"]`.
- [x] 2.2 Extender `OpenTradeIn` con `from_queue: Optional[bool] = None` y `entry_reason: str = "other"` (validar contra ENTRY_REASON_OPTIONS).
- [x] 2.3 Extender `CloseTradeIn` con `exit_reason: Optional[str] = None` (validar contra EXIT_REASON_OPTIONS si no es None).
- [x] 2.4 Extender `PatchTradeIn` con los 3 campos opcionales.
- [x] 2.5 `GET /journal/vocab` agrega `entry_reason_options` y `exit_reason_options`.

## 3. Backend — auto-infer partial_take + close_trade [journal-tracking]

- [x] 3.1 En `close_trade` (rama parcial), si `payload.exit_reason is None` setear `exit_reason='partial_take'` en el child cerrado.
- [x] 3.2 En `close_trade` (rama completa), si `payload.exit_reason is None` mantener el `exit_reason` existente del trade (que será `'unknown'` por default).
- [x] 3.3 `_trade_to_dict` incluye los 3 campos nuevos.
- [x] 3.4 `create_open_trade` persiste `from_queue` y `entry_reason` del payload.

## 4. Backend — stats con discretionary_vs_systematic [journal-tracking]

- [x] 4.1 En `journal_stats`: construir `by_entry_reason` (lista de `{entry_reason, ...metrics}`) usando la misma agregación que `by_setup`.
- [x] 4.2 Construir `discretionary_vs_systematic`: dos buckets — `{ "systematic": _aggregate([t for t in rows if t.entry_reason == "queue_signal"]), "discretionary": _aggregate([t for t in rows if t.entry_reason != "queue_signal"]) }`.
- [x] 4.3 Respuesta de `journal_stats` incluye ambos nuevos campos.

## 5. Frontend — dropdowns en forms [journal-tracking]

- [x] 5.1 Extender `Vocab` type en [frontend/app/journal/TradeForms.tsx](../../../frontend/app/journal/TradeForms.tsx) con `entry_reason_options: string[]` y `exit_reason_options: string[]`.
- [x] 5.2 `NewTradeModal`: agregar dropdown `entry_reason` (default `discretionary` para creación manual, required). Cuando se construya via "Take from queue" (Spec 3) el prefill setea `queue_signal`.
- [x] 5.3 `CloseTradeModal`: agregar dropdown `exit_reason`. Cuando `isPartial`, default visible = `partial_take`. Cuando no parcial, default `unknown`. Required.
- [x] 5.4 `EditTradeModal`: agregar los 3 campos editables con dropdowns.

## 6. Frontend — widget discrecional vs sistémico [journal-tracking]

- [x] 6.1 Extender el type `StatsResponse` en [frontend/app/journal/page.tsx](../../../frontend/app/journal/page.tsx) con `by_entry_reason` y `discretionary_vs_systematic`.
- [x] 6.2 Renderizar Card "Discrecional vs Sistémico" arriba del Performance Matrix. Dos columnas (Sistémico / Discrecional), cada una con N, WR, expectancy, Avg R, total P&L.
- [x] 6.3 Cuando alguno de los buckets tiene `n < 5`, mostrar badge ámbar "insuficiente — n=X" en lugar de las métricas. Nunca pintar verde/rojo si ambos son insuficientes (evitar falsa señal).

## 7. Verificación [journal-tracking]

- [x] 7.1 Smoke API: `curl POST /journal/trades` con `entry_reason='queue_signal'` → response refleja el valor. Sin `entry_reason` → default `'other'`.
- [x] 7.2 Smoke parcial: cerrar 3/10 sin pasar exit_reason → child cerrado tiene `exit_reason='partial_take'`. Original sigue abierto con `exit_reason='unknown'`.
- [x] 7.3 Smoke stats: con un trade `queue_signal` cerrado +R y uno `discretionary` cerrado -R, `discretionary_vs_systematic` muestra ambos buckets correctos.
- [x] 7.4 Frontend: crear trade manual desde `/journal` → dropdown defaults visible, validation de required activa.
- [x] 7.5 Histórico: stats endpoint sigue funcionando sobre los 34 viejos (todos cuentan como `discretionary` por default). El widget muestra insuficiencia hasta que haya 5 sistémicos.
