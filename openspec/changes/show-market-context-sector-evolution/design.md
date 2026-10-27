## Context
Current sector breadth measures annual high/low events with strict 252 preceding stored SPY sessions and per-date QUALITY_FILTERS. Stock sector and market cap are current metadata, not historical snapshots. No annual-event history is persisted. Reconstruct from prices and dated metrics without writes.
## Goals / Non-Goals
Show up to five sessions of sector annual-event incidence and concentration. No prediction, trend persistence claims, policy/scoring changes or historical membership claims.
## Shared contract
GET /api/v1/market-context/sector-evolution?as_of=YYYY-MM-DD, under existing protected router. Response:
```
{ as_of: string, status: 'available' | 'no_reference_session', sessions: [
  { date: string, eligible_symbols: number, excluded_symbols: number,
    high_count: number, low_count: number,
    sectors: [{ sector: string, eligible_symbols: number, excluded_symbols: number,
                high_count: number, low_count: number }] }
] }
```
Sessions ascending, at most five; sectors alphabetic, include excluded-only and zero-event sectors within that date's quality universe. Missing sector label is `Sin sector`. No constituent lists. If no SPY row exactly at as_of, return no_reference_session with empty sessions. Missing metrics on a session returns an empty sectors list and zero coverage, not silently skipping it. Counts are nonnegative integers; eligible zero is unknown incidence, positive eligible and zero events is valid zero. A symbol may count on both sides.
## Backend decisions
- New separate market_context_sector_evolution.py service, bounded cache TTL 300 seconds/max4 dates with deepcopy returns (follow overview pattern). No repeated calls to full breadth service for each date.
- Bulk queries independent of symbol/session counts: fetch last 257 distinct SPY dates <= as_of; newest up to5 are targets. Query dated QUALITY_FILTERS symbols with current sector metadata for target dates; fetch prices for union symbols over fetched dates. Use in-memory date lookup, no per-symbol queries.
- For each target/symbol, validate current and every one of its preceding 252 reference high/low pairs (finite positive, high>=low). Incomplete window or price gap excludes the symbol. Strict > historical max and < historical min; ties not events. Future rows and orphan dates cannot affect eligibility.
- Extract a small pure annual-extreme helper shared with existing breadth calculation to prevent rule drift; preserve legacy/current response behavior and tests. No other large refactor.
- Reconcile session totals exactly to sector totals; current session must match calculate_breadth_comparisons(include_constituents=True) for the same database fixture.
## Frontend decisions
- Independent authenticated useQuery keyed by user and as_of, enabled only with overview and authenticated session; errors/loading do not hide overview. New component after SectorBreadth. Use apiJson and existing cleanup. Retry button, retained data warning, 404/legacy endpoint gracefully unavailable, no fabricated fallback.
- New lib/market-context-sector-evolution.ts includes API types and pure normalization/derivation. Validate response as_of/status, strict dates, max5, endpoint last date equals as_of, integers/constraints, aggregate reconciliation. Do not use invalid/duplicate conflicting data as zero. Missing sector on a given date creates a gap. Keep actual dates, no interpolation or older substitution.
- Compare first and last returned session only when both exist and are exact valid observations for that sector. Never skip missing endpoints; fewer than two => comparison unavailable. Report high and low rates separately (count / eligible) and delta pp at 1 decimal. Rate differences are descriptive; increasing lows or decreasing highs sorts first; mixed sides retain both deltas. Then improvements, unchanged, unavailable; alphabetical ties. Coverage changes flagged with before/after denominators; equal counts are not assumed identical populations.
- Sector rows show latest rates and endpoint deltas with both dates, small fixed 0–100% high/low sparklines across up to5 sessions (gaps not bridged), and native details containing dated counts/rates/eligible/excluded values. Labels, units, legend and accessible text prevent color-only meaning. Empty histories/zero coverage are explicit.
- Compact overview compares first/last counts of sectors with highs/lows over sectors with positive eligibility, and top-two sector concentration per side (sum two largest event counts / total events). No events => concentration unavailable, not 0% concentration. All totals must reconcile; different daily eligible sectors/coverage is visible. Names of top2 with evidence in details. These endpoint changes do not imply continuous widening or deterioration through the window.
- Explain stored-SPY sessions, rolling 252-session event definition, current sector/market-cap metadata attribution and variable daily eligibility. No new normalized score, market posture claim or trading recommendation.
## Risks / Trade-offs
Current metadata can revise apparent history → explicit methodology warning. Reconstruction cost → bulk query count bounded, five targets, cache, separate request. Missing coverage → gaps and unavailable comparisons. Different eligible sets → show denominators and descriptive language, never assert same-universe shifts.
## Migration Plan
Additive endpoint, no migrations/dependencies/deployment. Older backend returns unavailable only in this section.
## Open Questions
None.
