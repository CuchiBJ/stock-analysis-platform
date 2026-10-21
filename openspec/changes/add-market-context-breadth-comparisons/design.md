## Context

Market Context currently calculates participation from `StockMetrics` and returns a cached `MarketContext`. The new rows need daily OHLC, the exact `as_of` session, and the same filtered symbol universe. The drawer already groups participation details in one section.

## Goals / Non-Goals

**Goals:** Add three deterministic, inspectable counts; include per-measure coverage; keep historical analysis bounded by `as_of`; preserve the existing posture and descriptor inputs.

**Non-Goals:** Intraday feeds, new provider calls, persisted aggregates, regime/posture changes, or corporate-action history repair.

## Decisions

- Add a focused `market_context_breadth` service that receives an async SQLAlchemy session and `as_of`. It selects the `StockMetrics.symbol` universe at that exact date with `QUALITY_FILTERS`, then loads matching `StockPrice` rows in batched queries.
- Current-session OHLC must match `as_of` exactly. SPY price dates define market sessions: for annual extremes, select the preceding 252 distinct dates with SPY prices, strictly before `as_of`; each qualified symbol must have valid high and low for every selected date, with high ≥ low. For ±4%, use the latest SPY price date before `as_of` and require the symbol's valid close on that exact date. Do not fall back to dates from other symbols if SPY history is absent. All values used by a measure must be finite and positive. Threshold comparisons use decimal representations of stored prices to preserve exact ±4% boundaries.
- A symbol is eligible per measure only when that measure's inputs are valid. `excluded_symbols` is the filtered universe minus eligible count. High and low events may both count for one symbol; opening ties are neutral. Ratios are nullable and computed as positive / (positive + negative), never as a fabricated midpoint.
- Return a stable object with `date`, plus each measure's `up_count`, `down_count`, `eligible_symbols`, `excluded_symbols`, and nullable `up_ratio`. The endpoint adds this under `participation.breadth_comparisons`; old clients and absent fields remain compatible.
- Keep the result inside the existing `MarketContext` cache. `analyze_as_of` naturally calculates it for its resolved historical date and does not use future prices.
- Extend default Participation rows, and revise the existing presentation requirement's eight-element cap to explicitly include the three new compact breadth rows. Keep mobile labels whole and include accessible descriptions for definitions and coverage.

## Risks / Trade-offs

- [Historical OHLC can contain corporate-action adjustment discontinuities] → Document the limitation; do not silently infer corrected prices.
- [Fetching up to 252 rows for every quality symbol increases query result size] → Use batched SQL queries and one pass over grouped results; no query per symbol.
- [Partial price history makes symbols unavailable to a measure] → Return eligible and excluded counts and show coverage in the drawer.

## Migration Plan

No database migration or deployment sequencing is required. Endpoint fields are additive and optional to the frontend, allowing old cached or mocked payloads to continue rendering.

## Open Questions

None.
