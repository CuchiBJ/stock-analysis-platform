## Why

`add-journal-decision-provenance` introduce el campo `from_queue` y la categoría `entry_reason='queue_signal'`, pero sin un workflow que haga la captura sin fricción, esos campos quedarían inertes: el operador no va a marcar honestamente "sí, esto vino del queue" cada vez. La consecuencia es que el split `discretionary_vs_systematic` siempre mostraría "0% systematic" y el flywheel queue → trade → outcome → recalibración nunca arrancaría.

El producto necesita un workflow donde **un click desde el queue/stock detail** crea el trade con `from_queue=true`, `entry_reason='queue_signal'`, setup correcto y snapshots del sistema correctos, dejando al operador solo `qty` y eventualmente ajuste de stop/entry. Sin este atajo la captura honesta no escala.

Este change defiende:
- Principio **#10 Workflow > analytics** — el journal solo genera edge si el workflow de captura es el de menor fricción posible.
- Principio **#6 Operational clarity > feature richness** — un click vs siete campos a llenar.

## What Changes

- **Nuevo endpoint** `GET /api/v1/journal/trade-draft?symbol=<X>&setup=<Y>` que devuelve un objeto prefill con los campos derivables del estado actual del sistema:
  - `symbol`, `setup` (eco del input)
  - `entry_price`: `last_close` de la última fila de `stock_metrics` para el símbolo
  - `stop_price_suggested`: el `ema21` actual del símbolo (heurística simple; el operador edita si quiere)
  - `from_queue`: `true`
  - `entry_reason`: `"queue_signal"`
  - `context`: ignorado (deprecado por `add-journal-system-snapshots`)
  - Los 4 snapshots del sistema (`regime`, `system_score`, `group_strength`, `leader_health`) se **previsualizan** en el response pero **no** se persisten — los snapshots reales se toman en el save (ver Non-goals).
- **Nuevo componente** `TakeFromQueueButton` en frontend. Acepta `{symbol, setup}` y al click llama al draft endpoint, abre `NewTradeModal` con `prefill` poblado y campos `symbol`, `setup`, `from_queue`, `entry_reason` en modo lock (no editable).
- **Integración en `/queue`**: cada card de las 3 lentes (U&R, Emerging Leaders, Building Bases) gana el botón "Tomar trade" alineado al CTA principal. El `setup` que se pasa al botón corresponde al de la lente.
- **Integración en `/stock/[symbol]`**: cuando el símbolo aparece en al menos una lente activa, la página muestra un botón "Tomar trade" con un dropdown chico para elegir el setup (si está en múltiples lentes).
- **`NewTradeModal`** ([frontend/app/journal/TradeForms.tsx](../../../frontend/app/journal/TradeForms.tsx)) acepta una prop `prefill?: TradeDraft` que cuando está presente: bloquea symbol/setup/from_queue/entry_reason, pre-llena entry_price/stop_price, pre-selecciona Setup. El operador edita qty (y opcionalmente entry/stop si difiere) y confirma.
- **Snapshots en el save, no en el click**: el backend `POST /journal/trades` ya ejecuta `take_entry_snapshot` (de `add-journal-system-snapshots`). El draft endpoint también previsualiza snapshots pero el persistido es el del save — esto evita que un setup visto el lunes y comprado el miércoles guarde snapshots stale del lunes.
- **Telemetría liviana**: el backend log (info) registra cuántos trades se crearon con `from_queue=true` vs `from_queue=null/false` en el `journal_stats` response como `provenance_capture_rate`.

## Non-goals

- **No** se sugieren stops sofisticados (swing low, ATR-based, multi-timeframe). Solo `ema21`. Stops más inteligentes van en spec aparte.
- **No** se persisten los snapshots del **click** — el draft endpoint los previsualiza para UX pero los snapshots reales se toman en el save. Single source of truth: snapshot service de Spec 2.
- **No** se trackean "vistas sin tomar" (cards del queue que el operador miró pero no operó). Esa data es ruidosa y abre la puerta a vanity ("70% de tus ignorados ganaron").
- **No** se permite "Tomar trade" para símbolos que no están en ninguna lente — eso fuerza el operador al `NewTradeModal` manual y la transparencia de "esto fue discrecional" se preserva.
- **No** se hace pre-fill de qty basado en account size — el operador define tamaño activamente; el sistema no debe sugerir size sin un módulo de risk management (out of scope).
- **No** se redirige automáticamente al journal después del save — el operador se queda en el queue/stock para seguir reviewing otros setups.

## Capabilities

### Modified Capabilities

- **`journal-tracking`** — extendida con el endpoint draft y el flujo prefill.
- **`setup-card-presentation`** — extendida con el CTA "Tomar trade" en cada card de las lentes en `/queue`.
- **`symbol-diagnostic`** — extendida con el CTA "Tomar trade" condicional en `/stock/[symbol]` cuando el símbolo está activo en lentes.

## Impact

- **Code**:
  - Backend: nuevo handler `GET /journal/trade-draft` (~40 LOC en [backend/app/api/v1/endpoints/journal.py](../../../backend/app/api/v1/endpoints/journal.py)); nuevo Pydantic `TradeDraftOut`
  - Frontend: nuevo componente `TakeFromQueueButton` (~60 LOC); modificación de `NewTradeModal` para aceptar `prefill` prop (~30 LOC delta); integraciones en queue cards y stock detail (~20 LOC cada una)
- **APIs**: 1 endpoint nuevo. No breaking.
- **DB**: ninguna migración.
- **Dependencias**: este change asume mergeados `add-journal-decision-provenance` y `add-journal-system-snapshots` (los enums y snapshots tienen que existir).
- **UX**: reduce la fricción de captura de queue_signal de ~9 inputs a 2 (qty + confirm). Esperable elevación de `provenance_capture_rate` de 0% a 70-90% en los primeros 30 días post-deploy.
