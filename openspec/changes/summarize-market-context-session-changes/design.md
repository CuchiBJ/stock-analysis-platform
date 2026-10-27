## Context
Evolution contains dated breadth ratios and leader counts but no posture snapshots. Benchmarks use stored SPY dates as the session reference. VIX has cached Cboe daily history but its response currently hides the preceding date.
## Goals / Non-Goals
Summarize only evidenced changes. No historical posture reconstruction: historical analysis can include subsequently resolved outcomes and is not a record of an issued posture.
## Decisions
- Add optional `previous_date` and `previous_price` to benchmark and VIX responses, preserving existing fields. Benchmark previous_date is the stored SPY session immediately before its own quote; price is null if that symbol has no valid close on that date. VIX uses its actual preceding observation.
- Reference pair is context.as_of and SPY.previous_date, only if SPY.date equals as_of and dates are valid/ordered. Explain that the reference is the preceding session available in stored SPY history, not a certified exchange calendar.
- Participation and leaders require evolution observations at exactly both reference dates. Never skip a null or missing row. Use normalized evolution duplicate handling. Do not use 5-day changes.
- Benchmark and VIX comparison requires their date and previous_date to equal the pair and positive finite prices. Calculate deltas from closes. Missing fields from older responses are unavailable.
- Participation decrease, leader decrease, benchmark decline, and VIX rise sort before improvements, then unchanged, then unavailable; stable dimension order breaks ties. VIX language describes volatility increasing/decreasing, never a posture change. Changes are descriptive, not recommendations.
- Participation delta is percentage points (two decimals), leaders integer counts, prices percentage changes (two decimals), VIX points (two decimals). Classification uses displayed rounded delta to avoid contradictory zero changes.
- Posture always explicitly unavailable because issued snapshots are absent. Never equate damage severity with posture.
- Six compact rows under “Qué cambió desde la sesión anterior”, after posture. Each row has inline before/after evidence with dates or an explicit reason. VIX pending/error remains explicit; cached failure data must carry a warning. Mention daily eligible populations may differ; leader count change does not identify entries/exits.
## Risks / Trade-offs
Stored SPY gaps can span multiple real sessions → always display exact dates and stored-history caveat. Different daily populations → explicit coverage caveat. Partial histories → per-dimension absence, no global no-change claim.
## Migration Plan
Additive fields; older payloads degrade safely. Local implementation only.
## Open Questions
None.
