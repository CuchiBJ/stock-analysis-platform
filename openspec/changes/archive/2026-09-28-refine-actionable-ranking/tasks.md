## 1. Eligibility and diagnostics

- [x] 1.1 [priority-engine] Split the institutional structural filter so Top Actionable can grade 52-week-high distance without loosening Live Transitions.
- [x] 1.2 [priority-engine] Remove the redundant actionable endpoint predicate while preserving all other structural and trigger gates.
- [x] 1.3 [symbol-diagnostic] Synchronize actionable and live diagnostic criteria with their respective production filters.

## 2. Independent RS component

- [x] 2.1 [priority-engine] Bulk-load five-session `relative_strength_spy` baselines for actionable candidates.
- [x] 2.2 [priority-engine] Implement the deterministic 60% RS-level / 40% RS-trend component with neutral missing-data behavior.
- [x] 2.3 [priority-engine] Replace the duplicated `leader_quality` 15% contribution and expose an explainable breakdown.
- [x] 2.4 [priority-engine] Update the frontend component label without changing response structure beyond the component name/details.
- [x] 2.5 [priority-engine] Confirm that no trustworthy fundamental acceleration input exists and do not add a proxy or data source.
- [x] 2.6 [symbol-diagnostic] Use the same five-session RS baseline in the per-symbol actionable score breakdown.

## 3. Verification

- [x] 3.1 [priority-engine] Add tests for the actionable eligibility boundary and preservation of live/breakout near-high behavior.
- [x] 3.2 [priority-engine] Add tests for improving, stable, deteriorating, and missing RS history.
- [x] 3.3 [symbol-diagnostic] Run focused actionable, diagnostic, and breakout tests.
- [x] 3.4 [priority-engine] Run broader backend/static checks and record unrelated pre-existing or environment failures.
- [x] 3.5 [priority-engine] Validate OpenSpec artifacts and review the final diff for unrelated changes.
