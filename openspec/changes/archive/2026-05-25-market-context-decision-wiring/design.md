## Context

`market-context-engine-phase-1` shipped two production engines (participation,
leadership) returning multi-dimensional descriptors and a `MarketContextBar`
that surfaces them. But descriptors do not flow into any decision:

- `transitions.py /actionable` ranks by `priority_score` with no awareness
  of breadth collapse or leadership exhaustion.
- `queue.py` lens endpoints (U&R, emerging, building bases) return their
  full result set under any market context.
- Operators relying on the bar to inform position sizing must do the
  cross-reference manually.

`empirical-continuation-probability` left the door open: the calculator
accepts a `participation` parameter that Phase 1 doesn't populate (Level 1
cohort is skipped). This change does NOT activate that path — it operates
strictly at the ranking + lens-suppression layer, leaving the empirical
calculator untouched.

Current call sites that need a decision filter:
- `/api/v1/transitions/actionable` — applies a `_REGIME_CONT_MULT` derived
  from the OLD `MarketRegimeEngine` (still alive, not yet retired). That
  multiplier coexists with the new context multiplier we add. Both apply
  multiplicatively for now; old engine retirement is a separate change.
- `/api/v1/queue/u-and-r`, `/emerging-leaders`, `/building-bases` — no
  context awareness at all.

State at design time:
- `MarketContextEngine` returns participation in {`EXPANDING`, `STABLE`,
  `NARROWING`, `COLLAPSING`, `UNKNOWN`} and leadership in {`EXPANDING`,
  `HEALTHY`, `THINNING`, `COLLAPSING`, `EXHAUSTED`, `UNKNOWN`}
- Engine has its own in-memory cache (~5 min TTL)
- Cold-start: when no metrics exist yet, descriptors are `UNKNOWN`

## Goals / Non-Goals

**Goals:**

- Make every consumer of `priority_score` aware of the current
  participation × leadership pair, so the score is contextual not raw.
- When the rule table says "this lens does not work in this regime,"
  suppress the lens result with an explicit reason — never silently empty.
- Surface the suppression decision back to the operator on the
  `MarketContextBar` and to the queue page, so the cause-and-effect chain
  is visible end-to-end.
- Keep the rules table tiny, centralized, and easy to retune as outcome
  data accumulates over the next 4–6 weeks.
- Honor operator judgment: the system advises by default, but a UI-only
  "view anyway" override lets the operator see the suppressed result.

**Non-Goals:**

- Recalibrating the rule thresholds against observed outcomes — deferred to
  August 2026 alongside descriptor recalibration.
- Per-symbol or per-sector overrides — Phase 1 operates at lens granularity.
- A `?override_suppression=true` backend query parameter — kept UI-only so
  the backend always tells the truth and external consumers cannot bypass
  the rules accidentally.
- Wiring `participation_descriptor` into `EmpiricalProbabilityCalculator` —
  separate scope (and blocked on `participation_at_detection` column).
- Retiring the old `MarketRegimeEngine` and its `_REGIME_CONT_MULT` — both
  multipliers compose for now; retirement is a future change.
- Per-rule unit tests of multiplier math — the rules are small enough that
  the test surface is the integration endpoints.

## Decisions

### 1. One rules table, colocated with the filter — not a strategy class hierarchy

The rules are a Python `dict[tuple[str, str], ContextMultiplier]` keyed by
`(participation, leadership)`. Each entry is a dataclass with three fields.
Cells not in the dict fall back to the neutral `ContextMultiplier(1.0, [], [])`.

**Why:** the rules are operator-tunable judgment calls, not a polymorphic
domain. A dict makes the entire policy visible in 20 lines of code, easy to
diff during retuning, and easy to reason about during incidents. Strategy
classes would scatter the policy across files.

**Alternatives considered:** rules engine (too heavy), YAML config (loses
type safety and forces a reload step), one method per case (forces n!
branches).

### 2. Cold-start (`UNKNOWN`) is neutral, never suppressive

Any descriptor pair containing `UNKNOWN` returns multiplier 1.0 and no
suppression. The system never restricts the operator's view because of
missing data — only because of observed adverse data.

**Why:** the alternative (suppress on UNKNOWN) would break the system on a
fresh database, after schema migrations that clear caches, or whenever the
descriptor pipeline lags. Honest default: when we don't know, we don't
intervene.

### 3. `building-bases` lens is NEVER suppressed

Building bases reflects multi-week structural formation. A two-day breadth
collapse does not invalidate an 8-week base. Surfacing those candidates
during weak regimes is *more* valuable, not less — they're the inventory
for when conditions turn.

**Why:** the lens semantics differ. U&R and emerging-leaders are
short-horizon ("act now") and depend on regime alignment; building-bases is
long-horizon ("watch for the next leg") and is regime-independent by
construction.

### 4. Score multiplier composes with the existing `_REGIME_CONT_MULT`

`priority_score` already gets multiplied by `_REGIME_CONT_MULT` from the old
`MarketRegimeEngine`. The new `context_multiplier` multiplies on top. Both
caps at 1.0 via the existing `min(1.0, ...)`.

**Why:** we don't retire the old engine in this change — that's a separate
deletion that needs A/B validation. Composing them lets us ship the new
filter without ripping out the old one, and the operator will see the
combined effect on `priority_score`.

**Trade-off:** during the transition period, suppression by the new filter
+ down-multiplier by the old engine can stack. Acceptable because the
result is "be more cautious," which is the correct error direction in
ambiguous regimes.

### 5. Suppression returns a structured response, not 200-empty

When a lens is suppressed the response shape is:

```json
{
  "suppressed": true,
  "suppression_reason": "participation COLLAPSING — U&R setups historically fail when breadth is collapsing",
  "context_snapshot": {"participation": "COLLAPSING", "leadership": "THINNING"},
  "results": []
}
```

Non-suppressed responses include `suppressed: false`, `suppression_reason: null`,
the same `context_snapshot`, and the populated `results` list.

**Why:** an empty `[]` is ambiguous — could mean "no candidates today" or
"suppressed." Conflating those hides the rule from the operator and from
any external consumer. Explicit `suppressed` is a documented contract
change, not a silent regime shift.

### 6. UI-only "view anyway" override

The frontend renders a button on the suppression card that flips local
state and re-renders the candidate list (which the backend always returned
inside `results` even when suppressed). The backend has no override flag.

**Why:** backend honesty + operator autonomy. The system gives its
recommendation explicitly; the operator can disregard it without negotiating
with the API. Also prevents external API consumers from accidentally
bypassing the rule with a query parameter copy-pasted from a curl command.

**Alternative considered:** backend `?override_suppression=true` flag —
rejected because it creates two truth values for the same endpoint and
would need to be threaded through every consumer.

### 7. Cache TTL of 5 minutes, keyed by descriptor pair only

`context_decision_filter` caches `ContextMultiplier` results in-process by
`(participation, leadership)` tuple. TTL matches the upstream
`MarketContextEngine` cache. There are at most 25 distinct keys
(5 participation × 5 leadership), so the cache size is trivially bounded.

**Why:** the multiplier is a pure function of the descriptor pair, and
descriptors change at human time scales (minutes, not seconds). 5 minutes
covers a fetch cycle without paying the rules cost twice.

### 8. Suppression decisions log at INFO, not DEBUG

When a lens is suppressed, log a single line:

```
INFO context_decision_filter: lens=u-and-r suppressed reason="participation=COLLAPSING + leadership=THINNING"
```

**Why:** an operator looking at an unexpectedly empty queue can `grep`
`context_decision_filter` in logs and immediately see why. INFO is the
right level because this is operator-actionable, not debugging detail.

### 9. The rules table is the contract; the constants live in spec

The Phase 1 rule cells (COLLAPSING, NARROWING + adverse leadership,
EXHAUSTED override, EXPANDING + supportive) are encoded in the
`context-decision-filter` spec as scenarios. The implementation file is the
single source of truth, but spec scenarios describe the expected behavior
so retuning is a spec change, not a code change.

**Why:** rule thresholds are operator-tunable but they are also
behavior-defining. Keeping them in the spec means a change in policy
requires a spec update, which forces a deliberate workflow — not a
one-line PR.

## Risks / Trade-offs

### Risk 1: Heuristic thresholds are wrong → false suppression
The rule cells (when a multiplier kicks in, which lens suppresses) are
operator judgment, not data-derived. Wrong calls suppress good setups
during weak regimes, or fail to suppress during truly hostile conditions.

**Mitigation:** the "view anyway" override means a wrong suppression costs
one click, not a missed setup. The rule table is small (≤6 cells) and
easy to retune. August 2026 recalibration milestone is the formal review
point.

**Accepted trade-off:** shipping with conservative rules is more valuable
than waiting months for empirical validation. The override is the safety
net.

### Risk 2: Operator stops trusting suppression and clicks "view anyway" reflexively
If the rules are perceived as wrong, the override becomes the default
behavior and the suppression card is noise.

**Mitigation:** Phase 1 rules are intentionally conservative (only
COLLAPSING fully suppresses; everything else multiplies down). Track use
informally via operator feedback. If override rate is high, the rules need
retuning before adding more.

**Accepted trade-off:** no telemetry built in Phase 1. Adding usage tracking
later is straightforward but premature now.

### Risk 3: External API consumers don't check `suppressed` and treat it as empty
A curl script or future mobile client written before this change interprets
`results: []` as "no candidates" rather than "suppressed."

**Mitigation:** the response always includes `suppressed: false` field
even when not suppressed, so consumers see the new shape immediately and
can switch logic. The change is documented as a contract change in the
proposal. No external consumers exist today besides the frontend.

**Accepted trade-off:** explicit `suppressed: bool` flag is more useful
long-term than backwards-compatible silent emptiness.

### Risk 4: `MarketContextEngine` cache miss inside a request adds latency
When the descriptor cache is cold, the engine runs ~17 queries to compute
context. Doing that inside the actionable/queue request adds 200-400ms.

**Mitigation:** `context_decision_filter` has its own cache on top, so
once warm the cost is a dict lookup. Cold-call latency budget is acceptable
for the 4 affected endpoints (none are sub-100ms paths). Pre-warming the
context engine on app startup is a future optimization, not needed for
Phase 1.

**Accepted trade-off:** brief latency penalty during cold-start in
exchange for always-fresh context.

### Risk 5: Composing with `_REGIME_CONT_MULT` produces over-correction
Both the old regime multiplier and the new context multiplier can lower
`priority_score` simultaneously. A 0.5 × 0.65 = 0.325 effective multiplier
is possible during the worst combined regimes.

**Mitigation:** the result is bounded by `min(1.0, ...)` (already present)
and the floor of 0 (scores can't go negative). Over-cautious ranking is
the correct error direction during ambiguous regimes — under-cautious is
the dangerous one.

**Accepted trade-off:** the old engine retirement is a follow-up change.
Composition is the right interim behavior.

### Risk 6: Cold-start returns `UNKNOWN` and the operator thinks the rules are broken
A user opening the dashboard for the first time sees no suppression even
in obviously hostile conditions, because descriptors are `UNKNOWN` until
the engine computes them.

**Mitigation:** the `context_snapshot` field is always in the response, so
the operator sees `participation: UNKNOWN` and understands why no filtering
is applied. The bar surfaces the same state. Cold-start is short
(< 1 min after startup).

**Accepted trade-off:** never suppressing on UNKNOWN is the right default;
the visible context_snapshot keeps the operator informed.
