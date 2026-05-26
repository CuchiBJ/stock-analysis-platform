## 1. Restructure Participation section

- [ ] 1.1 Reduce visible `MetricRow` calls in `<section>` 1 (Participation) from 9 to 3: keep only `breadth_above_ema21`, `breadth_momentum_5d`, `highs_lows_ratio`
- [ ] 1.2 Remove the 6 raw participation rows from the default render: `breadth_above_ema50`, `breadth_above_ema200`, `breadth_momentum_20d`, `near_highs_count`, `near_lows_count`, `participation_persistence`

## 2. Restructure Leadership section

- [ ] 2.1 Reduce visible `MetricRow` calls in `<section>` 2 (Leadership) from 10 to 4: keep `leader_count`, `leader_count_delta_20d`, `leader_pullback_quality_avg`, `leader_climactic_count`
- [ ] 2.2 Remove the 6 raw leadership rows from default render: `leader_count_delta_5d`, `leader_tightness_avg`, `leader_vol_contraction_avg`, `leader_rs_persistence_10d`, `leader_extension_count`, `leadership_turnover_5d`

## 3. Add "Raw metrics" toggle

- [ ] 3.1 Import `useState` and `ChevronRight`, `ChevronDown` from `lucide-react`
- [ ] 3.2 Add `const [showRaw, setShowRaw] = useState(false)` at the top of the component
- [ ] 3.3 After Leadership section, add a single button:
  ```tsx
  <button
    onClick={() => setShowRaw(!showRaw)}
    className="flex items-center gap-1.5 text-[11px] text-white/50 hover:text-white/80 transition-colors"
  >
    {showRaw ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
    Raw metrics (13)
  </button>
  ```
- [ ] 3.4 Below the button, render `{showRaw && (...)}` with the 13 removed rows grouped as: a small "Participation raw" sub-header + 6 rows, then "Leadership raw" sub-header + 7 rows (wait — 13 total split into 6 participation + 7 leadership? recount: 6 participation + 6 leadership = 12; check delta_5d which we kept or didn't — `leader_count_delta_5d` is removed = 1, that's 7 total leadership rows removed). Verify the actual count of removed leadership: `leader_count_delta_5d`, `leader_tightness_avg`, `leader_vol_contraction_avg`, `leader_rs_persistence_10d`, `leader_extension_count`, `leadership_turnover_5d` = 6. So 6 + 6 = 12 raw total. Update button label to "Raw metrics (12)".

## 4. Collapse Phase 2-4 pending section

- [ ] 4.1 Replace the entire section 3 (lines ~119-135) with a single line in the footer area:
  ```tsx
  <p className="text-[10px] text-white/30">
    Phase 2–4 pending: {ctx.engines_pending.join(' · ')}
  </p>
  ```
- [ ] 4.2 Remove the `<h3>` "Coming in Phase 2 – 4" header and the `<div className="space-y-2">{...map...}</div>` block

## 5. Simplify footer

- [ ] 5.1 Remove the `<p className="text-[10px] text-white/20">20d sample size: {p.delta_sample_size_20d} stocks</p>` line
- [ ] 5.2 Keep the `as_of` + `universe_size` line; add the new Phase 2-4 pending line (from task 4.1) below it as the second footer line

## 6. Verification

- [ ] 6.1 Run `cd frontend && npx tsc --noEmit` — expect zero errors
- [ ] 6.2 Open dashboard, click `MarketContextBar` to open drawer, visually verify:
  - Participation section: 3 metric rows visible
  - Leadership section: 4 metric rows visible
  - "Raw metrics (12)" button visible at the bottom of the metrics area
  - Click toggle: 12 raw rows appear, caret rotates ▸ → ▾
  - Click again: 12 raw rows hide
  - Phase 2-4 pending appears as a single line, not 5 cards
  - Footer has 2 lines max (`as_of/universe` + `Phase 2-4 pending`)
- [ ] 6.3 Close drawer and reopen — verify `showRaw` defaults to false again
- [ ] 6.4 Verify `MarketContextBar` itself is unchanged (no regression in the top bar)

## 7. Validate

- [ ] 7.1 Run `openspec validate simplify-market-context-drawer --strict` — expect clean
