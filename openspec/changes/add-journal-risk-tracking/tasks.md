## 1. Backend — modelo + migración [journal-tracking]

- [x] 1.1 Agregar a `JournalTrade` ([backend/app/models/stock.py](../../../backend/app/models/stock.py)): `planned_risk_dollars: Mapped[Optional[float]]`, `account_balance_at_entry: Mapped[Optional[float]]`. Ambos nullable.
- [x] 1.2 Crear migración Alembic `add_journal_risk_tracking.py` con `down_revision=<id de add-journal-decision-provenance>`. ADD COLUMN para las 2, ambos nullable, sin server_default (semánticamente "no data").
- [x] 1.3 Aplicar local y verificar con `\d journal_trades`.

## 2. Backend — Pydantic + endpoints [journal-tracking]

- [x] 2.1 Extender `OpenTradeIn` con `planned_risk_dollars: Optional[float] = Field(default=None, gt=0)` y `account_balance_at_entry: Optional[float] = Field(default=None, gt=0)`.
- [x] 2.2 Extender `PatchTradeIn` con los 2 campos opcionales.
- [x] 2.3 `create_open_trade` persiste los 2 campos desde el payload.
- [x] 2.4 En `_trade_to_dict`: computar `effective_risk_dollars` (prefer `planned_risk_dollars`, fallback `(entry - stop) * qty` si ambos presentes y stop < entry) y `risk_pct_of_account` (`effective_risk_dollars / account_balance_at_entry` cuando ambos disponibles). Agregar al dict response.

## 3. Backend — risk_evolution en stats [journal-tracking]

- [x] 3.1 En `journal_stats`: construir `risk_evolution` agrupando por `entry_date[:7]` (mes). Para cada bucket: `{month, n, avg_planned_risk_dollars, avg_risk_pct_of_account, total_r, total_pnl}`. Saltar trades con entry_date null.
- [x] 3.2 `avg_risk_pct_of_account` solo se computa cuando hay al menos 1 trade en el bucket con `account_balance_at_entry` cargado; si no, null.
- [x] 3.3 Respuesta de `journal_stats` incluye `risk_evolution` como array ordenado por mes ascendente.

## 4. Frontend — inputs en NewTradeModal [journal-tracking]

- [x] 4.1 Agregar useState `plannedRiskDollars` y `accountBalance` en `NewTradeModal` ([frontend/app/journal/TradeForms.tsx](../../../frontend/app/journal/TradeForms.tsx)).
- [x] 4.2 Al montar el modal, leer `localStorage.getItem('journal_account_balance')` y prefillear `accountBalance` si existe. Al submit exitoso, escribir el valor en localStorage (persiste entre trades).
- [x] 4.3 Agregar sección visual "Risk plan" con 2 inputs (planned risk $, account balance $) y un display computado de `Risk %`.
- [x] 4.4 Si Risk % > 1.5% mostrar badge ámbar `⚠ sobre-tamaño (>1.5%)`; si < 0.1% badge gris `insignificante (<0.1%)`; entre rango, color neutro.
- [x] 4.5 En submit, incluir los 2 campos en el body si tienen valor.

## 5. Frontend — inputs en EditTradeModal [journal-tracking]

- [x] 5.1 Igual que 4.1-4.4 pero en `EditTradeModal`. Inicializar desde `trade.planned_risk_dollars` y `trade.account_balance_at_entry`.
- [x] 5.2 PATCH incluye los 2 campos.

## 6. Frontend — R unit Trend Card [journal-tracking]

- [x] 6.1 Extender `Trade` interface y `StatsResponse` en [frontend/app/journal/page.tsx](../../../frontend/app/journal/page.tsx) con los nuevos campos (`planned_risk_dollars`, `account_balance_at_entry`, `effective_risk_dollars`, `risk_pct_of_account`, `risk_evolution`).
- [x] 6.2 Crear componente `RUnitTrendCard` que renderiza tabla por mes: Mes · N · Avg Risk $ · Avg Risk % · Total R · Total $. Coloreo total_r/total_pnl con `colorPnl`.
- [x] 6.3 Renderizar `RUnitTrendCard` dentro de un `<details>` collapsible (default cerrado) abajo del Performance Matrix.

## 7. Verificación [journal-tracking]

- [x] 7.1 Smoke API: `POST /journal/trades` con `planned_risk_dollars=15, account_balance_at_entry=5000` → response trae `effective_risk_dollars=15, risk_pct_of_account=0.003`.
- [x] 7.2 Smoke API: `POST /journal/trades` sin planned_risk pero con stop → `effective_risk_dollars` se infiere de `(entry-stop)*qty`.
- [x] 7.3 Smoke API: trade sin stop ni planned_risk → `effective_risk_dollars=null, risk_pct_of_account=null`.
- [x] 7.4 Smoke stats: `risk_evolution` muestra al menos 1 bucket por mes con trades, valores consistentes con cálculo manual.
- [x] 7.5 Frontend smoke: crear trade con planned_risk → Risk % se muestra en preview; cerrar y reabrir modal → account_balance precargado desde localStorage.
- [x] 7.6 Histórico: `risk_evolution` retorna data útil incluso si los 39 viejos no tienen `account_balance` cargado (avg_risk_pct queda null pero avg_planned_risk_dollars se infiere desde stop cuando hay).
