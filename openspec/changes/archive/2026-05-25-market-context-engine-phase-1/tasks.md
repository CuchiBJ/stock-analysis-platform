## 1. Backend — Engine skeleton

- [ ] 1.1 Create `backend/app/services/market_context_engine.py` with imports, module docstring referencing this change, and the three dataclasses (`ParticipationAnalysis`, `LeadershipAnalysis`, `MarketContext`) per spec API contract
- [ ] 1.2 Define module-level constants `_PARTICIPATION_THRESHOLDS` and `_LEADERSHIP_THRESHOLDS` per Decision 4 with inline comments explaining each cutoff
- [ ] 1.3 Implement `MarketContextEngine.__init__(db)` and `analyze()` async method that returns `Optional[MarketContext]` (returns None on empty DB)
- [ ] 1.4 Implement shared helpers: `_latest_date()`, `_universe_size(as_of)`, `_count_where(as_of, *extra)`, `_breadth_above_ema21(as_of)` returning `(ratio, universe_size)`

## 2. Backend — Participation engine

- [ ] 2.1 Implement `_participation(as_of)` returning `ParticipationAnalysis` with all 9 metrics from spec table
- [ ] 2.2 Use historical-date QUALITY_FILTERS (Decision 6) — apply filters to rows at that date, not today's filtered set
- [ ] 2.3 Implement `_participation_persistence(as_of, days=20)` computing stddev of breadth_above_ema21 across last 20 calendar days (single grouped query)
- [ ] 2.4 Implement `_participation_descriptor(momentum_pp)` mapping to EXPANDING/STABLE/NARROWING/COLLAPSING
- [ ] 2.5 Cover near-low proxy with comment: `distance_to_high_52w_atr <= -6.0` and link to design Non-Goals for follow-up upgrade

## 3. Backend — Leadership quality engine

- [ ] 3.1 Implement `_fetch_leaders(as_of)` — fetches rows at `as_of` passing `QUALITY_FILTERS`, then filters in Python via `is_quality_leader`
- [ ] 3.2 Implement `_leadership(as_of)` returning `LeadershipAnalysis` with all 10 metrics
- [ ] 3.3 Implement `_rs_persistence(today, past)` computing % overlap of RS-strong leaders between two sets
- [ ] 3.4 Implement `_climactic_count(leaders, as_of)` with single GROUP BY query for 20-day avg ADR per symbol, then Python comparison
- [ ] 3.5 Implement `leadership_turnover_5d` as `len(symbols_today.symmetric_difference(symbols_5d))`
- [ ] 3.6 Implement `_leadership_descriptor(delta_pct, climactic_ratio, extension_ratio)` with exhaustion override (Decision 8)
- [ ] 3.7 Handle empty leader set gracefully (spec scenario: averages = 0.0, descriptor = COLLAPSING, no raise)

## 4. Backend — In-memory cache

- [ ] 4.1 Add module-level cache dict `_cache: dict[date, tuple[MarketContext, datetime]]` (keyed by as_of date; value is context + cached_at timestamp)
- [ ] 4.2 Wire cache lookup into `analyze()`: hit if entry exists AND `now - cached_at < 5min`
- [ ] 4.3 On miss or new `as_of` date, recompute and write to cache; remove stale entries for older `as_of` dates
- [ ] 4.4 Add cache `clear()` classmethod for testability

## 5. Backend — Endpoint + router

- [ ] 5.1 Create `backend/app/api/v1/endpoints/market_context.py` with `GET /current` returning the structured response per spec
- [ ] 5.2 Endpoint serializes `MarketContext` → JSON (dataclass to dict, dates to ISO string)
- [ ] 5.3 Empty DB → HTTP 404 with clear message (spec scenario)
- [ ] 5.4 Register router in `backend/app/api/v1/api.py` with prefix `/market-context` and tag `market-context`
- [ ] 5.5 Verify `from app.api.v1.api import api_router` loads cleanly: route count = 70 (was 69)

## 6. Backend — Validation

- [ ] 6.1 Curl `GET /api/v1/market-context/current` returns 200 with all spec keys present
- [ ] 6.2 Verify `engines_pending` is exactly the 5 strings in deterministic order
- [ ] 6.3 Verify `participation.metrics` has all 9 keys with correct types
- [ ] 6.4 Verify `leadership.metrics` has all 10 keys
- [ ] 6.5 Verify legacy `/market-regime/current` still returns 200 unchanged (coexistence)
- [ ] 6.6 Verify descriptor logic by inspecting today's response and computing expected descriptor by hand

## 7. Frontend — MarketContextBar (compact)

- [ ] 7.1 Create `frontend/components/dashboard/MarketContextBar.tsx` (client component)
- [ ] 7.2 Type definitions for response shape mirroring spec API contract
- [ ] 7.3 Fetch from `${API_URL}/api/v1/market-context/current` on mount + every 60s via setInterval
- [ ] 7.4 Compact two-line layout per design:
  - Line 1: `PARTICIPATION <descriptor> <Δ5d>  ·  LEADERSHIP <descriptor> <Δ5d>`
  - Line 2: key raw metrics (`breadth 47%  momentum -6%  leaders 399 (-34/20d)`)
- [ ] 7.5 Color descriptors semantically: EXPANDING/HEALTHY/EXPANDING = green, STABLE = neutral, NARROWING/THINNING = amber, COLLAPSING/EXHAUSTED = red
- [ ] 7.6 Click handler opens drawer (state lifted to parent or local state with drawer rendered inline)
- [ ] 7.7 Unknown descriptor → neutral styling (defensive default per Risk 7)

## 8. Frontend — MarketContextDrawer (full tablero)

- [ ] 8.1 Create `frontend/components/dashboard/MarketContextDrawer.tsx`
- [ ] 8.2 Slide-in drawer pattern matching existing `SymbolHistoryDrawer.tsx`
- [ ] 8.3 Section 1: Participation — descriptor banner + table of 9 raw metrics with labels
- [ ] 8.4 Section 2: Leadership — same structure, 10 metrics
- [ ] 8.5 Section 3: `engines_pending` — placeholder cards (one per pending engine name) labeled "Coming in Phase 2/3/4" — operator sees that the framework reserves these slots
- [ ] 8.6 Footer: `as_of` date + `universe_size` + `delta_sample_size_20d` for transparency

## 9. Frontend — Atomic swap

- [ ] 9.1 In `frontend/app/dashboard/page.tsx`, change `MarketStatusBar` import to `MarketContextBar` (one line)
- [ ] 9.2 Keep `frontend/components/dashboard/MarketStatusBar.tsx` file on disk (do NOT delete) per Decision 11
- [ ] 9.3 Verify dashboard renders without errors in browser
- [ ] 9.4 Visual smoke test: compact bar shows current descriptor; click opens drawer; both engines render; pending engines visible as placeholders

## 10. Documentation + handoff

- [ ] 10.1 Add module docstring to `market_context_engine.py` linking to this change directory
- [ ] 10.2 Update `MEMORY.md` index with entry pointing to a new `market_context_started.md` memory file noting Phase 1 shipped + what's deferred
- [ ] 10.3 Create the memory file `market_context_started.md` (project type) with the 5 deferred engines, current descriptor thresholds, and August 2026 recalibration milestone

## 11. Spec archival

- [ ] 11.1 After all above tasks pass operator validation (2-3 day soft window of using the new bar), run `openspec apply market-context-engine-phase-1` to archive the change and promote the spec to `openspec/specs/market-context/spec.md`
- [ ] 11.2 Confirm no leftover scaffolding in the change directory after archival
