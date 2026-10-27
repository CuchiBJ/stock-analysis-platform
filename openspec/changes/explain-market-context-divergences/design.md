## Context
The session-change helper already validates exact dates against current context and preceding stored SPY session, normalizes missing/conflicting evolution observations and rounds displayed deltas. It returns typed directions and dated evidence. No backend work is required.

## Goals / Non-Goals
Surface opposing session moves without requiring mental comparison. No prediction, posture override, multi-week technical divergences, significance threshold, VIX rule or sector evolution.

## Decisions
- New `market-context-divergences.ts` consumes `summarizeSessionChanges(overview, undefined)` and uses IDs/directions, never parses summary strings or duplicates numeric/date rules. Existing helper stays unchanged.
- Four comparisons in fixed order: SPY/participation, SPY/leaders, QQQ/participation, QQQ/leaders. Each is evaluable only when both rows are available, including unchanged. Missing either row means unevaluable with the missing row's reason, not no divergence.
- Opposite nonzero directions only. Index up/internal down is deterioration and appears first. Index down/internal up is an internal improvement against a falling index, appears second and is described literally (not recovery confirmation). Flat or same direction is no opposing movement; the precision is the session summary's displayed precision, not a calibrated significance threshold.
- At most four findings; tie order follows pair order. Each finding includes literal Spanish narrative and both rows' labeled delta plus before/after/date evidence. No severity score or inferred persistence.
- Result contract includes findings, evaluated count (0..4), total=4 and unavailable comparisons with reasons. Full no-finding state says no opposing moves in these four session comparisons. Partial state says none among evaluated comparisons and makes incompleteness explicit. Zero coverage says insufficient comparable evidence. Missing reasons use compact native details disclosure with accessible summary.
- A standalone compact section `Divergencias de la sesión` follows SessionChanges in MarketContextPage. Show explanatory rule, coverage and per-finding evidence; restrained deterioration styling and neutral internal improvement styling. Do not alter Dashboard context or policy. Preserve existing loading/error/auth handling by rendering inside the existing data guard.
- Include daily-universe caveat: changing participation and leader counts can reflect different eligible populations, not individual entries/exits. State that these are opposing movements between two stored sessions, not confirmation of a trend reversal. No broad market-strength claim when comparisons agree.

## Risks / Trade-offs
Small rounded nonzero changes can be noisy → label as descriptive opposing movements and expose exact deltas, no significance assertion. Stored SPY gaps → reuse exact dates and existing session reference caveat. Duplicate findings across indices → bounded four findings with meaningful pair labels, no extra charts.

## Migration Plan
Frontend-only addition, no migration/dependency. No deployment authorized.
## Open Questions
None.
