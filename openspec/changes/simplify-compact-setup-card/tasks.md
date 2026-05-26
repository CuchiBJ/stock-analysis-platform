## 1. CompactSetupCard — strip footer

- [ ] 1.1 Remove the `<div className="flex items-center justify-between pt-1 border-t border-white/8">...</div>` footer block at lines ~171-181 entirely
- [ ] 1.2 Remove imports `Clock`, `TrendingUp`, `TrendingDown`, `Activity` from `lucide-react` (keep `Flame`)
- [ ] 1.3 Remove the `TRANSITION_ICON` constant (lines ~40-48)
- [ ] 1.4 Remove the local `const icon = TRANSITION_ICON[transition] ?? TRANSITION_ICON.stable` line

## 2. CompactSetupCard — strip "Base" metric

- [ ] 2.1 Remove the 4th grid cell (`Base` label + value) from the metrics grid (lines ~165-168). Grid stays `grid-cols-2` with three filled cells; the empty cell is acceptable (verified by D3 in design)

## 3. CompactSetupCard — move probability source to tooltip

- [ ] 3.1 Build a `probabilityTooltip` string when `probabilitySource` is set: `'Probabilidad empírica · N=<sampleSize>'` for empirical, `'Probabilidad rule-based · sin sample histórico suficiente'` for rule_based
- [ ] 3.2 Add `title={probabilityTooltip}` to the `<span>` wrapping the `{contPct}%` value
- [ ] 3.3 Remove the two `{probabilitySource === 'empirical' && (...)}` and `{probabilitySource === 'rule_based' && (...)}` blocks (lines ~125-134)
- [ ] 3.4 Remove the outer `<div className="flex flex-col items-end gap-0.5">` wrapper that exists only to stack the cont% above the sub-line; replace with the original flex row

## 4. TopActionableSetups — stop passing `base`

- [ ] 4.1 Remove the `base: isEma9 ? 'fast' : '8w'` line from the `keyMetrics` object passed to `CompactSetupCard` (line ~162)
- [ ] 4.2 No other changes needed in this file — the simplification is invisible to it

## 5. Verification

- [ ] 5.1 Run `cd frontend && npx tsc --noEmit` — expect zero errors
- [ ] 5.2 Restart frontend dev server, load `/dashboard`, visually verify:
  - Each card has no bottom border-t footer line
  - No "Nd in state" / no transition icon / no transition label visible
  - Metrics grid shows 3 cells: Dist, RS, Vol (no Base)
  - Hovering the continuation % shows the source/N tooltip via browser-native title
  - Cards still align uniformly in the 6-column grid
- [ ] 5.3 Count visible elements per card in inspector — confirm ≤15

## 6. Cleanup

- [ ] 6.1 If the empty grid cell looks asymmetric per D3, switch the grid to `grid-cols-3` with 3 horizontal cells of equal width (lower priority; only if visually disruptive)
- [ ] 6.2 Run `openspec validate simplify-compact-setup-card --strict` — expect clean
