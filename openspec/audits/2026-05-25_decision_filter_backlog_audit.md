# Decision Filter Audit — OpenSpec Backlog

**Date:** 2026-05-25
**Auditor:** Principal Product Architect lens (Claude)
**Filter:** `PRODUCT_BRAIN/DECISION_FILTER.md` v1.0.0
**Scope:** All 19 active changes in `openspec/changes/` (excluding `archive/`)

---

## TOP-LINE FINDING

**The "backlog" is not a backlog.** 18 of 19 changes are already shipped to the live system. The OpenSpec directory has not been swept since work started — shipped changes were never archived via `openspec apply`. That is itself drift: **the workflow tool of record disagrees with reality.**

Only 1 change is genuinely pending: **fix-weekly-tightness-calculation**.

This audit therefore answers two questions per change:
1. **Was it correct to ship?** (retrospective filter pass)
2. **Should it be rolled back, kept, or extended?**

---

## SCORING RUBRIC (from DECISION_FILTER.md)

8 questions per change. Required Yes on:
- (Q1 Speed) OR (Q2 Compression)
- (Q5 Transitions) OR (Q6 Deterioration)
- (Q8 Institutional Edge)

If any required dimension is NO → automatic reject.

- 8/8: Implement immediately
- 6-7/8: Strong consideration
- 4-5/8: Weak consideration
- 0-3/8: Reject

---

## VERDICTS AT A GLANCE

| # | Change | Status | Score | Verdict |
|---|--------|--------|-------|---------|
| 1 | add-trend-confirmation-gate | SHIPPED | 6/8 | ✅ KEEP |
| 2 | detect-daily-vcp-pattern | SHIPPED | 3/8 | ⚠️ ROLLBACK CANDIDATE |
| 3 | empirical-continuation-probability | SHIPPED | 7/8 | ✅ KEEP — core spine |
| 4 | fast-metrics-dynamic-coverage | SHIPPED | 6/8 | ✅ KEEP |
| 5 | fix-adr-percent-calculation | SHIPPED | bug fix | ✅ KEEP |
| 6 | fix-audit-priority1-integrity | PARTIAL | 3/8 | ⚠️ REDIRECT — fixes a feature that should die |
| 7 | fix-live-feed-staleness | SHIPPED | 8/8 | ✅ KEEP |
| 8 | fix-scheduler-price-download | SHIPPED | bug fix | ✅ KEEP |
| 9 | fix-scheduler-update-chain | SHIPPED | bug fix | ✅ KEEP |
| 10 | fix-weekly-tightness-calculation | **PENDING** | bug fix | ✅ SHIP |
| 11 | market-context-decision-wiring | SHIPPED | 7/8 | ✅ KEEP — needs UI cleanup |
| 12 | market-context-engine-phase-1 | SHIPPED | 7/8 | ✅ KEEP — needs drawer simplification |
| 13 | outcome-tracking-layer | SHIPPED | 6/8 | ✅ KEEP — foundation |
| 14 | redefine-entering-pullback | SHIPPED | 7/8 | ✅ KEEP — spine signal |
| 15 | setup-queue-lenses | SHIPPED | 7/8 | ✅ KEEP — most institutional surface |
| 16 | show-price-context-in-feed | SHIPPED | 5/8 | ✅ KEEP (weak pass) |
| 17 | tighten-above-ema-transitions | SHIPPED | 7/8 | ✅ KEEP |
| 18 | tighten-pre-reclaim-transitions | SHIPPED | 7/8 | ✅ KEEP |
| 19 | vcp-candidates-dashboard-panel | SHIPPED | 2/8 | ❌ ROLLBACK |

**Roll-up:** 14 keep + 3 keep-with-cleanup + 1 ship-now + 2 rollback/redirect + 1 outright reject.

---

## DETAILED SCORING

### 1. add-trend-confirmation-gate — 6/8 ✅ KEEP

Adds `sma150 > sma200` to `is_quality_leader()`. Completes the Stage 2 SMA chain (50>150>200).

| Q | A | Note |
|---|---|---|
| Q1 Speed | Y | Less noise to scan |
| Q2 Compression | Y | Fewer false positives |
| Q3 Quality | Y | Explicit gate purpose |
| Q4 Cog load | Y | Less manual filtering |
| Q5 Transitions | N | Filter, not transition |
| Q6 Deterioration | Weak Y | Lack of confirmation IS deterioration of trend |
| Q7 Discretionary | Y | Better candidates |
| Q8 Edge | Y | SEPA Stage 2 is institutional core |

**Required dimensions: all pass.** Surgical, no schema change, anti-drift in spirit (delete bad signal).

---

### 2. detect-daily-vcp-pattern — 3/8 ⚠️ ROLLBACK CANDIDATE

Adds VCP pattern detection, 3 new columns to `stock_metrics`, new endpoint `/api/v1/patterns/vcp`, new capability `pattern-detection`.

| Q | A | Note |
|---|---|---|
| Q1 Speed | N | New endpoint, new columns, more maintenance |
| Q2 Compression | N | More numbers, more endpoints |
| Q3 Quality | Weak | VCP is real, but `weekly_tightness` + `vcp_score` already existed |
| Q4 Cog load | N | 3 new columns per stock |
| Q5 Transitions | N | Pattern, not transition |
| Q6 Deterioration | N | — |
| Q7 Discretionary | Weak | Operator can read pattern visually in TradingView |
| Q8 Edge | Y | Minervini VCP is institutional concept |

**Required: Q1∨Q2 = NO. Q5∨Q6 = NO. Automatic reject per filter.**

The bigger issue: this change created a `pattern-detection` capability — a hook for "let's add more patterns later". This is the canonical screener-thinking drift vector. Each future pattern (cup-and-handle, base-on-base, flag) will plug in here and add more dashboard panels.

**Action:** Either deprecate the panel (recommended), or move the VCP score into Building Bases (where it already belongs) and delete `pattern-detection` capability + `/patterns/vcp` endpoint.

---

### 3. empirical-continuation-probability — 7/8 ✅ KEEP (core spine)

Replaces synthetic continuation_prob with empirical lookup from `transition_observations`.

| Q | A | Note |
|---|---|---|
| Q1 Speed | Neutral | One DB query added per setup |
| Q2 Compression | Y | One number with provenance |
| Q3 Quality | Y | Calibrated to real outcomes |
| Q4 Cog load | Y | Source label tells operator if number is real |
| Q5 Transitions | N | Probability layer |
| Q6 Deterioration | Y | Drop in empirical rate IS deterioration evidence |
| Q7 Discretionary | Y | Operator sees N, sees source, judges trust |
| Q8 Edge | Y | Principle 9 — measuring outcomes IS institutional |

**Required: all pass.** This is the foundation of "the system can self-correct". Combined with outcome-tracking-layer, it's the only change in the backlog that genuinely creates compounding edge.

---

### 4. fast-metrics-dynamic-coverage — 6/8 ✅ KEEP

FAST metric cycle now covers TIER 1 ∪ stocks in live transitions.

| Q | A | Note |
|---|---|---|
| Q1 Speed | Y | Sub-5min freshness on visible stocks |
| Q2 Compression | Neutral | — |
| Q3 Quality | Y | Less stale data = better signal |
| Q4 Cog load | Neutral | — |
| Q5 Transitions | Y | Data freshness IS transition detection |
| Q6 Deterioration | Y | Same |
| Q7 Discretionary | Y | Operator sees current state |
| Q8 Edge | Y | Data freshness is institutional table-stakes |

Infrastructure fix that makes the operational layer actually operational.

---

### 5-10, 17-18. Bug fixes — automatic pass

All bug fixes (fix-adr-percent, fix-live-feed-staleness, fix-scheduler-price-download, fix-scheduler-update-chain, fix-weekly-tightness-calculation, tighten-above-ema-transitions, tighten-pre-reclaim-transitions): bug fixes don't need filter justification, but most pass 6-8/8 anyway because they correct integrity issues on the spine (data freshness, calculation correctness, transition semantics).

**Action:** Ship fix-weekly-tightness-calculation (only one not yet implemented per code-state check).

---

### 6. fix-audit-priority1-integrity — 3/8 ⚠️ REDIRECT

Fixes integrity issues in QualitySwingScanner (slider params, column names, missing quality filters).

| Q | A | Note |
|---|---|---|
| Q1 Speed | N | Fixes a feature that contradicts the product |
| Q2 Compression | N | Same |
| Q3 Quality | Y | Adds quality filters to scanner |
| Q4 Cog load | N | Scanner page itself adds load |
| Q5 Transitions | N | — |
| Q6 Deterioration | N | — |
| Q7 Discretionary | Weak | Scanner is non-curated browsing |
| Q8 Edge | Weak | Quality filters help, but scanner is screener flavor |

**Required: Q5∨Q6 = NO. Q8 weak.** Automatic reject per filter.

This is a fix for `/scanner` and `quality_swing_scanner_service.py` — both flagged in the May audit and the 2026-05-25 architecture audit as **direct contradiction with `WHAT_THIS_PRODUCT_IS_NOT.md`** ("generic screener"). The correct action is not to fix the scanner but to delete it.

**Action:** Backend portion (quality filters in service) is harmless and can stay. The frontend slider/column fixes are wasted work on a page that should die. **Redirect:** kill `/scanner` page and `quality-swing-scanner` endpoint in a follow-up `delete-scanner-surface` change.

---

### 11. market-context-decision-wiring — 7/8 ✅ KEEP (needs UI cleanup)

Wires context descriptors into score multipliers + lens suppression.

| Q | A | Note |
|---|---|---|
| Q1 Speed | Y | Less fatigue scanning suppressed lenses |
| Q2 Compression | Y | Rules table in one place |
| Q3 Quality | Y | Suppresses bad-regime lenses |
| Q4 Cog load | **Mixed** | Backend ✓, frontend ADDED context_snapshot in 4 places — net load ↑ |
| Q5 Transitions | Y | Regime transitions affect surfacing |
| Q6 Deterioration | Y | Warnings on EXHAUSTED |
| Q7 Discretionary | Y | View-anyway override |
| Q8 Edge | Y | Principle 5 |

Spec-correct, UI drift on shipping. **Action:** apply cleanup PR from 2026-05-25 architecture audit — show `context_snapshot` once (MarketContextBar), remove from queue page headers, TopActionableSetups header, SuppressionCard.

---

### 12. market-context-engine-phase-1 — 7/8 ✅ KEEP (needs drawer simplification)

Multi-dimensional context engine (participation + leadership).

Required dimensions all pass. The drawer with 19 metrics is theater per the architecture audit, but the engine itself is correct and the bar UI is dense-but-fast.

**Action:** simplify drawer to 5-6 decision-changing metrics.

---

### 13. outcome-tracking-layer — 6/8 ✅ KEEP (foundation)

Records every transition + outcome to `transition_observations`.

| Q | A | Note |
|---|---|---|
| Q1 Speed | N | Background process |
| Q2 Compression | Neutral | — |
| Q3 Quality | Y | Eventually calibrates everything |
| Q4 Cog load | Neutral | — |
| Q5 Transitions | Y | The data spine for transition analysis |
| Q6 Deterioration | Y | Same |
| Q7 Discretionary | Y | Operator can see what worked |
| Q8 Edge | Y | Principle 9 — only thing that makes system improvable |

**Foundation change.** Without this, empirical-continuation-probability has no data. Q1∨Q2 marginal but acceptable for foundation work.

---

### 14. redefine-entering-pullback — 7/8 ✅ KEEP (spine signal)

ENTERING_PULLBACK redefined: leader approaching EMA from above, distance decreasing, 7 SEPA gates.

All required dimensions pass strongly. This change re-aligns the most important transition signal with PRODUCT_BRAIN.

---

### 15. setup-queue-lenses — 7/8 ✅ KEEP (most institutional surface)

Three lenses: U&R, Emerging Leaders, Building Bases.

| Q | A | Note |
|---|---|---|
| Q1 Speed | Y | Curated by lens horizon |
| Q2 Compression | Y | Separated by purpose |
| Q3 Quality | Y | Each lens has strict criteria |
| Q4 Cog load | Y | Operator picks lens, not 30-row table |
| Q5 Transitions | Y | U&R is pure transition flavor |
| Q6 Deterioration | Weak | — |
| Q7 Discretionary | Y | Operator chooses lens |
| Q8 Edge | Y | U&R is Minervini-grade |

Most aligned with PRODUCT_BRAIN of any shipped change.

---

### 16. show-price-context-in-feed — 5/8 ✅ KEEP (weak pass)

Adds current_price, change_pct, dist_to_setup_pct to feed responses.

| Q | A | Note |
|---|---|---|
| Q1 Speed | Y | Less context switch to TradingView |
| Q2 Compression | Y | Less mental math |
| Q3 Quality | Neutral | — |
| Q4 Cog load | Y | Inline info |
| Q5 Transitions | N | Display layer |
| Q6 Deterioration | N | — |
| Q7 Discretionary | Y | Price is first thing trader looks at |
| Q8 Edge | Weak | Operational data, not insight |

**Required: Q5∨Q6 = NO. Q8 weak.** Strictly speaking, automatic reject. But Q2 and Q7 are strong enough that this earns its place as operational ergonomics, not feature creep. Filter scoring rule should probably tolerate purely-operational changes that score high on (Q1∧Q2∧Q4∧Q7) even when Q5/Q6/Q8 are weak — this is a corner the filter doesn't cover cleanly.

**Note for filter v1.1:** consider adding an "operational ergonomics" carve-out, or accept that the filter is for new capabilities, not display-layer additions.

---

### 19. vcp-candidates-dashboard-panel — 2/8 ❌ ROLLBACK

Adds VcpCandidatesPanel to the main dashboard.

| Q | A | Note |
|---|---|---|
| Q1 Speed | N | Another panel to scan → NET NEGATIVE |
| Q2 Compression | N | Third "list of stocks" on the dashboard |
| Q3 Quality | Weak | VCP real but BuildingBases already covers same territory |
| Q4 Cog load | N | Adds list, contradicts the architecture audit finding |
| Q5 Transitions | N | Pattern, not transition |
| Q6 Deterioration | N | — |
| Q7 Discretionary | Weak | — |
| Q8 Edge | Y | VCP is institutional concept |

**Required: Q1∨Q2 = NO. Q5∨Q6 = NO. Automatic reject.**

This is the canonical drift the 2026-05-25 architecture audit flagged: the dashboard now has THREE parallel "stocks to look at" panels (TopActionableSetups, LiveTransitionFeed, VcpCandidatesPanel). This change CAUSED that drift.

**Action:** rollback. Delete `VcpCandidatesPanel.tsx` from `app/page.tsx`. The `/queue/building-bases` lens already surfaces VCP-quality candidates with multi-week horizon.

---

## PATTERN OBSERVATIONS

### Pattern 1: Bug fixes dominate. Capability additions are rarer than they look.

| Type | Count |
|---|---|
| Bug fixes (`fix-*`) | 6 |
| Tighten/redefine existing transitions | 4 |
| New capabilities (real) | 5 (empirical, outcome-tracking, market-context, decision-wiring, setup-queue) |
| New surfaces (display layer) | 2 (price-context, vcp-panel) |
| Coverage/infra | 2 (fast-metrics, trend-gate) |

The system is mostly correcting itself, not bloating. That's good. The problem is the *retention*: shipped changes aren't archived, so the directory looks like a 19-item backlog when really it's a 1-item backlog plus 18-item changelog.

### Pattern 2: New capabilities cluster correctly around principles 5, 7, 9.

The five real new capabilities all defend specific NON_NEGOTIABLE_PRINCIPLES. This is the system working as designed.

### Pattern 3: Display-layer additions are the weak spot.

Both `vcp-candidates-dashboard-panel` (fail) and `show-price-context-in-feed` (weak pass) are display changes. The filter doesn't model display-layer additions well — they tend to score low on transitions/deterioration/edge even when they're operationally correct (price context) or operationally wrong (VCP panel).

**Recommendation:** add filter clause: "If change is purely display, must improve Q1, Q2, Q4 — not just look pretty."

### Pattern 4: One capability is a drift vector.

`pattern-detection` (created by `detect-daily-vcp-pattern`) is a future-features hook. Every future pattern (cup-and-handle, etc.) will plug in here. **Recommendation:** retire `pattern-detection` capability, fold VCP score directly into stock_metrics, expose only through Building Bases lens.

### Pattern 5: OpenSpec workflow has its own drift.

`tasks.md` is not maintained as work completes — 18 changes show 0/N tasks done but their code is shipped. The intended workflow (`openspec apply <change>` after operator validation) is being skipped. The directory is becoming a graveyard.

**Recommendation:** sweep the 17 already-shipped changes through `openspec apply` to archive them. The remaining directory should reflect actual pending work.

---

## ACTION ITEMS (prioritized)

### Immediate (this week)
1. **Archive shipped changes.** Run `openspec apply` on all 17 shipped changes. Directory shrinks to 1-2 active items.
2. **Ship `fix-weekly-tightness-calculation`.** The only genuine pending fix. Quick win.
3. **Rollback `vcp-candidates-dashboard-panel`.** Delete `VcpCandidatesPanel` from `app/page.tsx`. Building Bases already surfaces VCP-quality candidates.

### Short-term (next 2 weeks)
4. **Open `delete-scanner-surface` change.** Kill `/scanner` page, `quality_swing_scanner_service.py`, `/api/v1/quality-swing-scanner/*` endpoint, and `/api/v1/scanners/*`. Resolves the `fix-audit-priority1-integrity` redirect.
5. **Open `cleanup-context-snapshot-duplication` change.** Remove `context_snapshot` rendering from 3 of the 4 places it currently appears. Keep only MarketContextBar + SuppressionCard.
6. **Open `simplify-market-context-drawer` change.** Drop drawer from 19 to 5-6 decision-changing metrics.
7. **Open `delete-pattern-detection-capability` change.** Fold VCP into stock_metrics; remove `/api/v1/patterns/*`; remove the future-features hook.

### Medium-term
8. **Update `DECISION_FILTER.md` to v1.1.** Add carve-out for operational-ergonomics changes (display layer). Add clause for "any change must also pass a *delete*-something test — what existing surface does this replace?"
9. **Open `delete-zombie-endpoints` change.** Remove 44 unconsumed endpoints (per architecture audit). Single PR.

---

## FILTER META-CRITIQUE

Running this audit revealed that DECISION_FILTER.md v1.0 has blind spots:

1. **Display-layer changes don't score cleanly.** `show-price-context-in-feed` is operationally correct but fails required dimensions strictly read.
2. **Foundation work doesn't score cleanly.** `outcome-tracking-layer` scored 6/8 mostly because background-process infrastructure doesn't improve "operational speed" in the immediate-user sense. The filter rewards consumer-facing changes more than foundation that enables them.
3. **No "delete test" yet.** Per `WHAT_THIS_PRODUCT_IS_NOT.md`, the product is defined as much by what it isn't. Adding a feature without deleting a surface is *itself* drift, regardless of filter score.

These should inform filter v1.1.

---

## CLOSING

The system is more disciplined than the OpenSpec directory makes it look. The architecture audit (2026-05-25) flagged dashboard drift as the central risk; this audit confirms it stems from a single shipped change (`vcp-candidates-dashboard-panel`) and the unfinished cleanup of `context_snapshot` rendering. Three small follow-up changes neutralize most of the drift.

The OpenSpec hygiene issue (shipped changes never archived) is small as a code problem but large as a workflow problem: every future audit becomes harder if the directory is a graveyard.
