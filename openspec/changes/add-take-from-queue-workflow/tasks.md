## 1. Backend — trade-draft endpoint [journal-tracking]

- [x] 1.1 Definir Pydantic `TradeDraftOut` en [backend/app/api/v1/endpoints/journal.py](../../../backend/app/api/v1/endpoints/journal.py) con: `symbol`, `setup`, `entry_price` (last_close), `stop_price_suggested` (ema21), `from_queue=True`, `entry_reason="queue_signal"`, y los 4 snapshots previsualizados (`regime_at_entry`, `system_score_at_entry`, `group_strength_at_entry`, `leader_health_at_entry`).
- [x] 1.2 Implementar `GET /journal/trade-draft?symbol=<X>&setup=<Y>`. Valida que `setup` está en `SETUP_OPTIONS`. Valida que `symbol` existe en `stocks` (404 si no).
- [x] 1.3 Consultar última fila de `stock_metrics` para el símbolo; usar `close` como `entry_price` y `ema21` como `stop_price_suggested`. Si no hay metrics → 404 con detalle "no metrics for symbol".
- [x] 1.4 Invocar `take_entry_snapshot(db, symbol, date.today())` para los 4 snapshots de preview (no se persisten — solo para que la UI muestre al operador qué va a quedar guardado).

## 2. Backend — validar provenance_capture_rate en stats [journal-tracking]

- [x] 2.1 En `journal_stats` agregar campo `provenance_capture_rate`: float = `count(from_queue IS NOT NULL) / count(total)`. Para los 34 históricos será ~0; va a crecer con el workflow.
- [x] 2.2 Documentar en docstring que `null` significa "origen no marcado" y diferenciarlo de `false` ("operador marcó como discretional").

## 3. Frontend — TakeFromQueueButton component [journal-tracking]

- [x] 3.1 Crear `frontend/components/queue/TakeFromQueueButton.tsx`. Props: `{symbol: string, setup: string}`.
- [x] 3.2 Al click: fetch `/api/v1/journal/trade-draft?symbol=X&setup=Y`. Si OK, abre `NewTradeModal` con `prefill={...response}`. Si error, muestra toast.
- [x] 3.3 Loading state visible (botón disabled + spinner mini).

## 4. Frontend — NewTradeModal con prefill [journal-tracking]

- [x] 4.1 Extender prop signature de `NewTradeModal` en [frontend/app/journal/TradeForms.tsx](../../../frontend/app/journal/TradeForms.tsx) con `prefill?: TradeDraft`.
- [x] 4.2 Cuando `prefill` está presente: pre-llenar `symbol`, `setup`, `entryPrice`, `stopPrice`; setear estado interno `from_queue=true`, `entry_reason='queue_signal'`.
- [x] 4.3 Renderizar `symbol` y `setup` como readonly cuando `prefill` está. `entry_reason` se setea internamente, no se muestra dropdown.
- [x] 4.4 Mostrar un banner azul tipo "Tomando trade del queue · regime=expansive · system_score=0.74" usando los snapshots del prefill, para que el operador vea qué va a quedar guardado.
- [x] 4.5 En `submit()` enviar `from_queue=true`, `entry_reason="queue_signal"` al body cuando había prefill.

## 5. Frontend — integración en /queue [setup-card-presentation]

- [x] 5.1 Localizar el componente principal de cada card en `frontend/components/queue/` (likely `SetupCard.tsx` o similar). Identificar punto de inserción para CTA.
- [x] 5.2 Agregar `<TakeFromQueueButton symbol={row.symbol} setup={lensName} />` al final de cada card. El `lensName` se pasa desde el contexto del queue page (U&R / Emerging / Building Bases → `u_and_r` / `emerging` / `building_base`).
- [x] 5.3 Estilizar el botón consistente con el resto de CTAs del card (no dominante; el card sigue centrándose en el setup, no en el journal).

## 6. Frontend — integración en /stock/[symbol] [symbol-diagnostic]

- [x] 6.1 En `frontend/app/stock/[symbol]/page.tsx`, identificar el array de lentes en las cuales el símbolo aparece (data ya disponible en el endpoint `/stocks/{sym}/diagnostic`).
- [x] 6.2 Si el array es no vacío: mostrar un botón "Tomar trade" con un dropdown chico de las lentes activas. Si solo hay una lente activa → botón directo sin dropdown.
- [x] 6.3 Al click → mismo flujo: fetch draft → abre `NewTradeModal` con prefill.

## 7. Verificación [journal-tracking]

- [x] 7.1 Smoke API: `curl /journal/trade-draft?symbol=NBIS&setup=building_base` → response trae los 9 campos con valores razonables.
- [x] 7.2 Smoke API edge: `?symbol=ZZZZ` → 404. `?symbol=NBIS&setup=fake_setup` → 422 (validation).
- [x] 7.3 E2E manual: ir a `/queue/building-bases`, click "Tomar trade" en NBIS → modal abre prefilled → editar qty=5 → submit → trade aparece en `/journal` con `from_queue=true`, `entry_reason='queue_signal'`, snapshots populados.
- [x] 7.4 E2E manual: crear trade manual desde `/journal` (botón "Nuevo trade") → modal NO muestra banner azul, `from_queue` queda null (no false — el operador no lo marcó), `entry_reason` default `'discretionary'` editable.
- [x] 7.5 Stats: `journal_stats.provenance_capture_rate` > 0 después de capturar el primer trade desde queue.
