## 1. Extraer `is_quality_leader` a helper compartido [setup-queue]

- [ ] 1.1 Crear `backend/app/services/quality_leader_gate.py`:
  ```python
  """Minervini SEPA quality gate — shared helper used by transition_engine
  and setup_queue_service. Single source of truth for the 8 criteria."""
  from app.models.stock import StockMetrics

  def is_quality_leader(m: StockMetrics) -> bool:
      """Eight Minervini SEPA criteria — all must pass."""
      if not all([
          m.perf_1y is not None, m.ema200 is not None,
          m.current_price is not None, m.sma50 is not None,
          m.sma150 is not None, m.sma200 is not None,
          m.low_52w is not None, m.adr_percent is not None,
      ]):
          return False
      if m.low_52w == 0:
          return False
      price_above_low_pct = (m.current_price - m.low_52w) / m.low_52w
      if m.high_52w is not None:
          range_52w_pct = (m.high_52w - m.low_52w) / m.low_52w
          if range_52w_pct < 0.60:
              return False
      return (
          m.perf_1y > 30.0 and
          m.current_price > m.ema200 and
          (m.distance_to_ema50_atr or 0.0) > 0 and
          m.sma50 > m.sma150 and
          m.sma150 > m.sma200 * 1.05 and
          price_above_low_pct >= 0.70 and
          m.adr_percent >= 3.0
      )
  ```
- [ ] 1.2 Reemplazar `transition_engine.py:_is_quality_leader` con delegación:
  ```python
  from app.services.quality_leader_gate import is_quality_leader as _is_quality_leader_fn

  def _is_quality_leader(self, m: StockMetrics) -> bool:
      return _is_quality_leader_fn(m)
  ```
- [ ] 1.3 Verificar `/transitions/live` sigue funcionando (smoke test manual: curl + check shape).

## 2. SetupQueueService [setup-queue]

- [ ] 2.1 Crear `backend/app/services/setup_queue_service.py` con la clase `SetupQueueService(db: AsyncSession)` y métodos:
  - `list_u_and_r() -> list[dict]`
  - `list_emerging_leaders() -> list[dict]`
  - `list_building_bases() -> list[dict]`
  - `get_symbol_history(symbol: str, days: int = 30) -> dict`
- [ ] 2.2 Implementar `list_u_and_r()`:
  - Query 1: candidatos con observation últimos 2 días en `transition_observations` (excluir `stable`)
  - Query 2: bulk fetch metrics actuales por símbolo, filtrar por `is_quality_leader`, `distance_to_ema21_atr ∈ [-0.5, +1.5]`
  - Query 3: bulk fetch históricos entre día-10 y día-5 + últimos 20 días — chequear "from above" y "no broke EMA50"
  - Query 4: bulk fetch count de observations últimos 30d por símbolo (touches_last_30d)
  - Ordenar por recency asc, |d21_atr| asc, rs_spy desc
  - Devolver shape con `tradingview_url = f"https://www.tradingview.com/chart/?symbol={sym}"`
- [ ] 2.3 Implementar `list_emerging_leaders()`:
  - Query: metrics actuales filtrados por `perf_6m > 20 AND rs_spy > 105 AND price > ema50 AND price > ema200`
  - Para cada uno, calcular `is_quality_leader(m)` — incluir solo si `False`
  - Construir `minervini_status` evaluando cada uno de los 8 gates individualmente
  - Determinar `qualifies_as_emerging_because` con la razón principal (primer criterio falla)
- [ ] 2.4 Implementar `list_building_bases()`:
  - Query: metrics actuales con `vcp_score >= 70 AND weeks_in_base >= 6` filtrado por `is_quality_leader`
  - Para cada uno: bulk fetch últimos 20 días de `distance_to_ema21_atr`, calcular `max - min <= 2.0`
- [ ] 2.5 Implementar `get_symbol_history(symbol, days)`:
  - Query observations últimos `days` días ordenadas asc
  - Query régimen actual via `MarketRegimeEngine.detect_regime()` (reutilizar cache si existe)
  - Para cada `transition_type` único en observations, calcular `success_rate` y `sample_size` filtrado al régimen actual desde `transition_observations` aggregate

## 3. Endpoints API [setup-queue]

- [ ] 3.1 Crear `backend/app/api/v1/endpoints/queue.py`:
  ```python
  from fastapi import APIRouter, Depends, Query
  from sqlalchemy.ext.asyncio import AsyncSession
  from app.core.deps import get_db
  from app.services.setup_queue_service import SetupQueueService

  router = APIRouter()

  @router.get("/u-and-r")
  async def u_and_r_queue(db: AsyncSession = Depends(get_db)):
      return await SetupQueueService(db).list_u_and_r()

  @router.get("/emerging-leaders")
  async def emerging_leaders_queue(db: AsyncSession = Depends(get_db)):
      return await SetupQueueService(db).list_emerging_leaders()

  @router.get("/building-bases")
  async def building_bases_queue(db: AsyncSession = Depends(get_db)):
      return await SetupQueueService(db).list_building_bases()

  @router.get("/symbol/{symbol}/history")
  async def symbol_history(
      symbol: str,
      days: int = Query(30, ge=1, le=365),
      db: AsyncSession = Depends(get_db),
  ):
      return await SetupQueueService(db).get_symbol_history(symbol.upper(), days)
  ```
- [ ] 3.2 Registrar router en `backend/app/api/v1/api.py`:
  ```python
  from app.api.v1.endpoints import ..., queue
  api_router.include_router(queue.router, prefix="/queue", tags=["queue"])
  ```

## 4. Frontend — página dedicada [setup-queue]

- [ ] 4.1 Crear `frontend/app/queue/page.tsx` con layout de 3 tabs (U&R / Emerging / Building Bases), state local del tab activo, count badges, refresh cada 60s (`setInterval` + invalidate query).
- [ ] 4.2 Crear `frontend/components/queue/UnderCutRallyQueue.tsx`:
  - Fetch `/api/v1/queue/u-and-r`
  - Render rows con: symbol, transition badge, event age, ATR distance, RS, volume contraction, touches_last_30d
  - Click en row → abrir `SymbolHistoryDrawer` con ese symbol
  - Botón "TradingView →" en cada row (link externo, target=_blank)
  - Empty state explícito: `"No qualifying setups in the last 2 days. The system tracks forward — wait for the next SLOW cycle."`
- [ ] 4.3 Crear `frontend/components/queue/EmergingLeadersQueue.tsx`:
  - Fetch `/api/v1/queue/emerging-leaders`
  - Render rows con: symbol, perf_6m, RS, expandable detail con `minervini_status` (chips verde/rojo por criterio)
  - `qualifies_as_emerging_because` como tooltip o subtitle
- [ ] 4.4 Crear `frontend/components/queue/BuildingBasesQueue.tsx`:
  - Fetch `/api/v1/queue/building-bases`
  - Render rows con: symbol, vcp_score, weeks_in_base, atr_range badge (color por tightness), current d21_atr
  - Click en row → drawer histórico
- [ ] 4.5 Crear `frontend/components/queue/SymbolHistoryDrawer.tsx`:
  - Drawer lateral (slide-in from right) o modal
  - Fetch `/api/v1/queue/symbol/{symbol}/history?days=30`
  - Header: symbol + current regime
  - Sección 1: timeline visual de observations (vertical, ordenado cronológicamente, cada uno con badge de transition + outcome)
  - Sección 2: track record table — filas por `transition_type_in_<regime>` con success_rate y sample_size
- [ ] 4.6 Agregar entry en navegación principal del frontend (`/queue` link en sidebar o topnav). Mantener `/dashboard` como vista principal.

## 5. Validación end-to-end [setup-queue]

- [ ] 5.1 Reiniciar backend, verificar logs sin errores de import.
- [ ] 5.2 `curl http://localhost:8000/api/v1/queue/u-and-r` — debe responder 200, shape correcto (puede ser `[]` si no hay candidatos).
- [ ] 5.3 `curl http://localhost:8000/api/v1/queue/emerging-leaders` — verificar `minervini_status` con los 8 criterios.
- [ ] 5.4 `curl http://localhost:8000/api/v1/queue/building-bases` — verificar shape.
- [ ] 5.5 `curl http://localhost:8000/api/v1/queue/symbol/NVDA/history?days=30` — verificar observations + track_record.
- [ ] 5.6 Levantar frontend, navegar a `/queue`, validar:
  - Los 3 tabs renderizan con counts correctos
  - Click en row abre drawer con historial
  - Empty states son honestos (no spinners infinitos)
  - Refresh automático cada 60s sin glitches visuales
- [ ] 5.7 Forzar caso "from above falla": elegir un símbolo en `/transitions/live` que esté abajo de EMA21 desde hace varios días, verificar que NO aparece en U&R queue.
- [ ] 5.8 Verificar performance: `/queue/u-and-r` responde en <300ms en steady state.

## 6. Documentación / memory [setup-queue]

- [ ] 6.1 Agregar memory entry `setup_queue_started.md` con: fecha de start, las 3 lentes y sus filtros exactos, decisión arquitectónica de "from above en query, no en engine", y nota de que `quality_leader_gate.py` es ahora source of truth.
- [ ] 6.2 Actualizar `AUDIT_INSTITUCIONAL_MAYO_2026.md` marcando como ✅ resuelto el item de "watchlist intelligence (P4)" con referencia a `/queue`.
