## Why

La sección Journal entró en producción sin capturar **el origen de la decisión** detrás de cada trade. Hoy un trade que salió del queue del sistema y un trade discrecional fuera de cualquier lente son indistinguibles en la DB y en las stats. Sin esa distinción ninguna métrica del journal puede responder la pregunta central del producto: **¿el sistema le está ayudando al operador o no?**

La auditoría institucional de 2026-06-03 (ver conversación previa) marcó este gap como riesgo P0: el 80% del journal hoy es portfolio tracker genérico. Sin provenance, las decisiones que se infieren de las stats (qué setup tiene edge, qué contexto operar, qué lente desactivar) están contaminadas por la mezcla de trades dentro y fuera del sistema.

Este change defiende:
- Principio **#10 Workflow > analytics** — separar workflow OS (queue → trade) de análisis genérico de P&L
- Principio **#6 Operational clarity > feature richness** — el origen es la pieza de claridad que falta

## What Changes

- **Modelo `JournalTrade`** ([backend/app/models/stock.py](../../../backend/app/models/stock.py)) gana 3 columnas:
  - `from_queue: bool | null` — null por default; se setea cuando el trade entra desde el workflow take-from-queue (Spec 3) o cuando el operador lo marca explícitamente
  - `entry_reason: str` con vocabulario controlado `queue_signal | discretionary | continuation | news | other` (default `other`)
  - `exit_reason: str` con vocabulario controlado `stop_hit | target | trail | thesis_broken | discretionary | partial_take | unknown` (default `unknown`)
- **`POST /journal/trades`** y **`POST /trades/{id}/close`** aceptan los nuevos campos (entry_reason requerido en create, exit_reason requerido en close).
- **Auto-inferencia de `partial_take`**: cuando `qty < trade.qty` en el close, el backend pre-asigna `exit_reason='partial_take'` salvo que el operador especifique otro valor.
- **`GET /journal/vocab`** expone los enums.
- **`GET /journal/stats`** gana dos breakdowns: `by_entry_reason` y un agregado `discretionary_vs_systematic` (`queue_signal` vs todos los demás).
- **Frontend `NewTradeModal`** y **`CloseTradeModal`** ganan dropdowns required.
- **Frontend `/journal`** muestra un widget **"Discrecional vs Sistémico"** arriba del matrix con N + WR + expectancy de cada cohort, condicional a que ambos buckets tengan n ≥ 5 (data starvation honesta — si no hay data muestra placeholder).
- **Backfill histórico**: los 34 trades actuales se setean a `from_queue=null`, `entry_reason='other'`, `exit_reason='unknown'`. **No** se intenta inferir por regex sobre `error_note` — falsa data degrada la calibración.

## Non-goals

- **No** se introducen categorías `fomo` o `revenge` — el operador no se auto-categoriza honestamente en el momento; estos patrones se detectan después con análisis temporal (volumen de trades + pérdida previa) en un change separado.
- **No** se incluye captura automática de `from_queue=true` desde el `/queue` — eso lo hace `add-take-from-queue-workflow` (Spec 3). Este change deja el campo escribible pero no hay UI que lo setee automático todavía.
- **No** se cambia el comportamiento del importer CSV ni se re-importa nada — los históricos quedan con valores defaults.
- **No** se elimina la columna `error_note`. Se mantiene como texto libre opcional; el operador puede agregar nuance.
- **No** se snapshotean estados del sistema (regime, score) — eso es `add-journal-system-snapshots`.

## Capabilities

### New Capabilities

- **`journal-tracking`** — nueva capability que formaliza la sección Journal que entró en producción sin pasar por OpenSpec. Este change establece su **baseline de provenance**: cada trade registra el origen de la decisión y el motivo de salida.

### Modified Capabilities

(ninguna)

## Impact

- **Code**:
  - Backend: 3 columnas nuevas en `JournalTrade`, migración Alembic, ampliación de Pydantic models (`OpenTradeIn`, `CloseTradeIn`, `PatchTradeIn`), ampliación de `_aggregate` y `journal_stats` en [backend/app/api/v1/endpoints/journal.py](../../../backend/app/api/v1/endpoints/journal.py), lógica de auto-infer `partial_take` en `close_trade`
  - Frontend: dropdowns en `NewTradeModal` y `CloseTradeModal` ([frontend/app/journal/TradeForms.tsx](../../../frontend/app/journal/TradeForms.tsx)), widget "Discrecional vs Sistémico" en [frontend/app/journal/page.tsx](../../../frontend/app/journal/page.tsx)
- **APIs**: `/journal/vocab` extendido, `/journal/stats` con nuevos campos. No breaking — clients existentes ignoran campos extra.
- **DB**: 1 migración con 3 columnas; backfill UPDATE sobre 34 filas. Sin reescritura masiva.
- **Dependencias**: ninguna nueva.
