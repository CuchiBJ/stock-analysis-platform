## Why

El operador (conversación 2026-06-03) tiene un patrón institucional consistente: cuando un trade alcanza +2R, mueve el stop a la entrada para volverlo risk-free. Hoy esa acción se ejecuta vía `PATCH /journal/trades/{id}` cambiando `stop_price` — el sistema no registra la transición, simplemente sobrescribe.

Eso rompe tres cosas críticas:

1. **R-multiple deja de ser honesto**: si el stop original era $5 de risk por share y se mueve a entrada (=0 risk), el cálculo `(exit - entry) / (entry - new_stop)` se vuelve divisor cero o un número absurdo cuando el trade cierra. El R reportado deja de comparar contra el risk **planeado**, que es la convención institucional.
2. **Trades risk-managed se confunden con trades sin sustancia**: un trade que llegó a +2R, se movió a BE, y cerró en BE figura como `pnl=$0, R=0` — visualmente idéntico a un trade que nunca se movió. Pero operacionalmente son fenómenos completamente distintos: uno es **risk management exitoso** (preservé capital después de dejar correr a +2R), el otro es **no-decisión** (nunca encontré edge).
3. **No hay audit trail**: el operador no puede revisar a posteriori cuándo movió cada stop, ni el sistema puede contar "% de winners donde alcancé BE antes del exit" — una métrica clave de disciplina.

Este change defiende:
- Principio **#1 Transitions dominate over static states** — el cambio de estado del riesgo (full-risk → risk-free) es un evento operacional, no una mutación silenciosa.
- Principio **#6 Operational clarity > feature richness** — los R-multiples y outcomes deben ser interpretables sin contexto perdido.

## What Changes

### Modelo

`JournalTrade` ([backend/app/models/stock.py](../../../backend/app/models/stock.py)) gana 1 columna:

- `initial_stop_price: float | null` — snapshot inmutable del primer stop registrado. Se setea en el `POST /journal/trades` (si payload trae stop_price) o en el primer PATCH que introduce un stop. Una vez no-null, **nunca** se modifica por endpoints futuros.

Nueva tabla `journal_stop_events`:

- `id` (pk auto)
- `trade_id` (fk → journal_trades.id, indexed)
- `old_stop_price` (float, nullable — primer evento puede tener null)
- `new_stop_price` (float, nullable — el stop puede borrarse a null)
- `kind` (str enum: `initial` / `moved_to_be` / `trailed_up` / `widened` / `removed`)
- `occurred_at` (datetime, default now)
- `auto_classified` (bool, default true — distingue auto-detection de operator-supplied)

### Endpoint behavior

- **`POST /journal/trades`**: si payload trae `stop_price`, persistir también `initial_stop_price = stop_price` e insertar evento `kind='initial'`.
- **`PATCH /journal/trades/{id}`**: cuando `stop_price` cambia (delta detectado comparando old vs new):
  - Si `initial_stop_price` aún es null y nuevo stop_price es no-null → setear `initial_stop_price` e insertar evento `kind='initial'`.
  - Si ambos no-null y new ≥ entry_price → evento `kind='moved_to_be'`.
  - Si ambos no-null y new > old (long convention) → evento `kind='trailed_up'`.
  - Si ambos no-null y new < old → evento `kind='widened'`.
  - Si new es null y old no-null → evento `kind='removed'`.
- **`POST /journal/trades/{id}/close`**: no registra evento, pero el R-multiple se computa con `initial_stop_price` (si existe), no con `stop_price` actual.

### R-multiple derivation

`_derive_r(t)` cambia su prioridad:
1. `t.r_multiple` persistido (si existe).
2. Sino: usar `initial_stop_price` cuando existe; fallback a `stop_price`.
3. Sino: null.

### Nuevo endpoint

- `GET /journal/trades/{id}/stop-history` — devuelve lista de eventos para el trade, ordenada cronológicamente.

### Frontend

- **Open positions table**: cuando `current stop_price >= entry_price` para una posición abierta (long), mostrar badge **`🔒 BE`** (verde) junto al stop. Comunica visualmente que es risk-free.
- **`EditTradeModal`**: nueva sección read-only "Historial de stop" debajo de la sección de snapshots del sistema. Tabla chica con columnas: timestamp, kind, old → new. Vacía si no hay eventos.
- **Open positions endpoint response**: incluye `is_risk_free: bool` derivado (`stop_price is not None and entry_price is not None and stop_price >= entry_price`) para que el frontend no tenga que recalcular.

## Non-goals

- **No** se agrega dropdown de "razón del cambio" — la auto-clasificación cubre los 5 casos relevantes.
- **No** se introduce categoría nueva `exit_reason='be_stop'` — operator-supplied o auto-infer pueden hacerse en spec aparte (con `add-journal-decision-provenance` ya cubrimos categorización general).
- **No** se hacen breakdowns de stats nuevos ("% reached BE", "avg time to BE", etc) — el data model habilita eso pero el dashboard cleanup es decisión separada.
- **No** se modifica el comportamiento del importer CSV histórico — los 39 trades quedan sin `initial_stop_price` ni stop events (solo lo nuevo registra historial).
- **No** se permite editar manualmente `initial_stop_price` desde la UI — es snapshot inmutable.
- **No** se trackean cambios de `entry_price`, `qty`, `target` ni otros campos — solo stop. Si en el futuro hace falta event log general, se generaliza.

## Capabilities

### Modified Capabilities

- **`journal-tracking`** — extendida con tracking inmutable del stop inicial, log de eventos de cambio de stop, y derivación honesta de R-multiple basada en el risk planeado.

## Impact

- **Code**:
  - Backend: 1 columna nueva en `JournalTrade`, 1 tabla nueva con FK, migración Alembic, modificación de `create_open_trade` / `close_trade` / `patch_trade` para auto-detectar y registrar eventos (~80 LOC), nuevo endpoint `/trades/{id}/stop-history` (~25 LOC), actualización de `_derive_r` (~10 LOC).
  - Frontend: badge condicional en Open Positions table (~15 LOC), sección "Historial de stop" en EditTradeModal (~40 LOC).
- **APIs**: 1 endpoint nuevo. `_trade_to_dict` gana 2 campos derivados (`initial_stop_price`, `is_risk_free`). No breaking.
- **DB**: 1 migración con 1 columna + 1 tabla. Sin backfill (históricos quedan con `initial_stop_price=null`).
- **Dependencias**: ninguna. Spec independiente — puede mergearse antes o después de `add-take-from-queue-workflow`.
