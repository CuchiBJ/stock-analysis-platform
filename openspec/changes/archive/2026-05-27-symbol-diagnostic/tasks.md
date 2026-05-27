## 1. Backend: diagnostic service

- [ ] 1.1 Create `backend/app/services/symbol_diagnostic.py` with dataclasses `Criterion(name, actual, threshold, passes, kind)` and `ListCheck(key, name, passes, criteria)`
- [ ] 1.2 Implement helpers: `_ge(actual, threshold)`, `_in_range(actual, lo, hi)`, `_truthy(actual)` that produce `Criterion` objects with correct `passes`
- [ ] 1.3 Implement `diagnose_actionable(m)` — mirror `_INSTITUTIONAL_SETUP` + EMA trigger + pullback_quality/adr/vol thresholds from `/actionable` query
- [ ] 1.4 Implement `diagnose_live(m, has_recent_obs)` — institutional + EMA trigger + non-stable observation existence
- [ ] 1.5 Implement `diagnose_u_and_r(m, history_25d, recent_obs)` — quality_leader gate + d21_atr ∈ [-0.5, +1.5] + "from above" rule (d21_atr > 0.5 between day-10 and day-5) + "no broke EMA50" (d50_atr never negative last 20d)
- [ ] 1.6 Implement `diagnose_emerging_leaders(m, minervini_status)` — perf_13w > 20% + RS > 105 + price > EMA50/200 + NOT fully Minervini
- [ ] 1.7 Implement `diagnose_building_bases(m)` — Minervini leader + VCP score ≥ 70 + weeks_in_base ≥ 6 + ATR oscillation ≤ 2.0
- [ ] 1.8 Implement `build_symbol_diagnostic(db, symbol) -> dict` that loads all needed data once and assembles the response

## 2. Backend: endpoint

- [ ] 2.1 Add to `backend/app/api/v1/endpoints/stocks.py` (or new `stocks_diagnostic.py` if too large): `GET /{symbol}/diagnostic`
- [ ] 2.2 Resolve symbol case-insensitive (uppercase); 404 if not in `stocks`
- [ ] 2.3 Load latest stock_metrics; if missing, return 200 with `header.has_metrics=false`
- [ ] 2.4 Load 25-day metrics window for state-dependent diagnostics
- [ ] 2.5 Load recent transition_observations (last 30 days, limit 10)
- [ ] 2.6 Load group_strength + market_context (reuse existing services)
- [ ] 2.7 Call `build_symbol_diagnostic`, return as JSON

## 3. Backend: tests

- [ ] 3.1 Create `backend/tests/test_symbol_diagnostic.py`
- [ ] 3.2 Unit tests for `_ge`, `_in_range`, `_truthy` helpers
- [ ] 3.3 For each `diagnose_<list>` function: test with synthetic `StockMetrics` that should pass (all criteria green) and one that should fail (specific criteria red)
- [ ] 3.4 Run `pytest tests/test_symbol_diagnostic.py -v`

## 4. Frontend: symbol page

- [ ] 4.1 Create `frontend/app/stock/[symbol]/page.tsx` (Next.js dynamic route, 'use client')
- [ ] 4.2 Fetch `/api/v1/stocks/{symbol}/diagnostic` on mount
- [ ] 4.3 Render header card: symbol, name, current_price, group badge (reuse `GroupStrengthBadge`)
- [ ] 4.4 Render "Status across lists" table with one row per list; rows expandable
- [ ] 4.5 Inside expanded row: criteria table with name | actual | threshold | pass/fail icon
- [ ] 4.6 Render transition history card (vertical list with date + type + outcome badge)
- [ ] 4.7 Render market context applied card
- [ ] 4.8 Handle 404 → error state; handle has_metrics=false → info banner

## 5. Frontend: search

- [ ] 5.1 Create `frontend/components/layout/SymbolSearch.tsx`: input with `value`, onChange, onKeyDown; Enter → `router.push("/stock/" + value.trim().toUpperCase())`
- [ ] 5.2 Mount in `DashboardLayout.tsx` nav (right side, next to nav links)
- [ ] 5.3 Style: minimal, ~16ch width, placeholder "Symbol…"

## 6. Verification

- [ ] 6.1 `curl localhost:8000/api/v1/stocks/FN/diagnostic | jq` → verify shape, FN passes most, fails avg_volume_10d in actionable
- [ ] 6.2 Same for AAOI → passes actionable + live, fails u_and_r "from above"
- [ ] 6.3 Same for unknown symbol "ZZZZZ" → HTTP 404
- [ ] 6.4 Open `/stock/FN` and `/stock/AAOI` in browser, verify rendering
- [ ] 6.5 Type "MRAM" + Enter in search → navigates to `/stock/MRAM`
- [ ] 6.6 `npx tsc --noEmit` clean
- [ ] 6.7 `openspec validate symbol-diagnostic --type change --strict`

## 7. Archive

- [ ] 7.1 `openspec archive symbol-diagnostic --yes`
- [ ] 7.2 Memory entry + commit + push
