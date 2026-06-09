## Why

El usuario reveló (conversación 2026-06-03) que viene bajando deliberadamente su R unit a lo largo del tiempo como protección de capital mientras encontraba edge: de ~$50 por trade en Diciembre 2025 a ~$10 en Mayo 2026 (5x menos). La data lo confirma con precisión casi exacta: R unit avg cae de $50.20 (Ene) → $30.09 (Feb) → $20.72 (Abr) → $8.87 (May).

El dashboard actual muestra **`Total P&L = -$316`** como headline implícito de performance. Pero el **`Total R = +10.04`** está ahí también — y son dos verdades contradictorias. Lo que el usuario hizo (bajar exposición defensivamente) es comportamiento institucional correcto, pero el sistema **no captura su intención de risk** — la infiere indirectamente desde `(entry_price − stop_price) * qty`, lo cual:

1. Solo funciona cuando hay stop cargado (un tercio de los históricos no lo tienen).
2. No captura el caso en que el operador piensa en risk como **% de cuenta** (ej "0.5% de $5k = $25"), no como dólares absolutos.
3. No permite computar **`risk_pct_of_account`** ni **`expectancy_pct_of_account`** — las únicas métricas que realmente normalizan performance a través del tiempo cuando el capital y el R unit cambian.

Sin estos dos campos, no se puede responder operacionalmente:
- ¿Estoy disciplinado en mi sizing? (debería estar ~0.5-1% de cuenta por trade)
- ¿Cuándo cambió mi R unit en términos de % cuenta? (no en $ absolutos — un $25 risk en cuenta de $2k vs $5k son cosas distintas)
- ¿Cuál es mi edge en R-multiple por cohorte cuando normalizo capital deployed?

Este change defiende:
- Principio **#6 Operational clarity > feature richness** — explícito > inferido cuando la inferencia puede mentir.
- Principio **#10 Workflow > analytics** — el operador planea el risk *antes* de entrar; capturar esa intención es workflow, no analytics post-hoc.

## What Changes

### Modelo

`JournalTrade` ([backend/app/models/stock.py](../../../backend/app/models/stock.py)) gana 2 columnas nullable:

- `planned_risk_dollars: float | null` — el monto **intencional** de risk al abrir la posición. Si null, el sistema infiere `(entry_price − stop_price) * qty` como hoy. Esta es la verdad del operador sobre cuánto pensaba arriesgar; la inferencia desde stop es la verdad del mercado.
- `account_balance_at_entry: float | null` — balance de la cuenta al momento de entry. Permite computar `risk_pct_of_account` y normalizar performance histórico.

### Endpoints

- `POST /journal/trades` acepta los 2 campos opcionales.
- `_trade_to_dict` agrega 2 derivados al response (nunca persistidos):
  - `effective_risk_dollars`: prioriza `planned_risk_dollars`, fallback a `(entry−stop)*qty`. Null si ninguno disponible.
  - `risk_pct_of_account`: `effective_risk_dollars / account_balance_at_entry` cuando ambos disponibles. Null caso contrario.
- `GET /journal/stats` gana sección `risk_evolution` con array `[{month, n, avg_planned_risk_dollars, avg_risk_pct_of_account, total_r}]` ordenado cronológicamente.

### Frontend

- `NewTradeModal` y `EditTradeModal` ganan 2 inputs (sección "Risk plan"):
  - Input `planned_risk_dollars` (número, default vacío)
  - Input `account_balance_at_entry` (número, default vacío). Para fricción cero: si se cargó previamente, **persistir el último valor en localStorage** y prefillear (el balance no cambia trade a trade típicamente — un balance carga al mes alcanza).
  - Preview en vivo: muestra `Risk %` calculado, con badge ámbar si >1.5% (sobre-tamaño institucional) o si <0.1% (insignificante).
- `/journal` gana **R unit Trend Card** (collapsible, abajo del matrix) con tabla por mes mostrando: N · avg planned risk $ · avg risk % · total R · total $ PnL. Permite ver visualmente que el R unit bajó pero el R cumulativo subió.

## Non-goals

- **No** se integra con el broker para fetch automático del balance — operador lo carga manualmente. Auto-sync es un spec aparte que requiere autenticación con IBKR API.
- **No** se hace backfill histórico de `account_balance_at_entry` — el operador no se acuerda exacto. Los 39 históricos quedan null y solo participan del strip de headline P&L, no del análisis %.
- **No** se introduce un "position size calculator" (sugerir qty dado risk $ y stop) — eso es feature, no captura de data. Va en spec posterior si vale el costo.
- **No** se modifica la lógica de cálculo de `r_multiple` — sigue siendo `(exit − entry) / (entry − stop)`. R-multiple es invariante al sizing del operador; no necesita planned_risk para computarse correctamente.
- **No** se persisten los derivados (`effective_risk_dollars`, `risk_pct_of_account`) en DB — solo en response.

## Capabilities

### Modified Capabilities

- **`journal-tracking`** — extendida con captura explícita de intención de risk y balance, más derivados que normalizan performance histórico a % de cuenta.

## Impact

- **Code**:
  - Backend: 2 columnas en `JournalTrade`, migración Alembic, ampliación de `OpenTradeIn` / `PatchTradeIn`, derivados en `_trade_to_dict`, agregación nueva `risk_evolution` en `journal_stats` (~30 LOC).
  - Frontend: 2 inputs en `NewTradeModal` y `EditTradeModal` (~40 LOC), localStorage para account_balance prefill, nueva `RUnitTrendCard` collapsible (~80 LOC).
- **APIs**: 2 campos nuevos en payloads y 3 campos en responses. No breaking.
- **DB**: 1 migración con 2 columnas nullable. Sin backfill.
- **Dependencias**: ninguna nueva. Independiente de los otros 3 specs de la cola (puede mergearse en paralelo a `add-journal-system-snapshots` y `add-take-from-queue-workflow`).
- **Riesgo de drift**: bajo. Los campos son operativos (decisión activa del operador), no analytics retrospectivos.
