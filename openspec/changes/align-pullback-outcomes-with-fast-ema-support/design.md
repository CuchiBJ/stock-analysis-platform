## Context

`entering_pullback` detects a leader approaching EMA9 or EMA21 from above, but its current shared pre-reclaim outcome ignores those supports. Stored extrema also hide whether support preceded continuation. The operator permits wicks below the averages if recovered at the close and requires the move within ten sessions after detection.

## Goals / Non-Goals

**Goals:** Match pullback outcomes to fast-average support, inspect chronology, exclude mutable daily bars, and replace legacy labels safely.

**Non-Goals:** Change detection or other outcome families; build a new trading strategy, exchange calendar, or prediction model. The initial implementation did not authorize production operations; a subsequent explicit operator request authorized the rollout recorded in `production-rollout.md`.

## Decisions

### Dedicated pure classifier

Add a small helper consuming the detection snapshot and ten ordered daily OHLC bars. It advances EMA9/21/50 from the saved detection values using `alpha = 2 / (period + 1)` and each session's close. This is deterministic and matches the existing EMA convention without queries for missing daily metrics. It preserves the original detection-context seed, which may be intraday rather than the final detection-day chart EMA.

EMA21 is the structural closing floor. A low touching EMA9 with a close at/above EMA9, or touching EMA21 with a close at/above EMA21, confirms support. A wick below either is allowed. Any low at/below EMA50, or any close below EMA21, invalidates the result across the entire window, before success is considered. Closing between EMA9 and EMA21 alone does not establish a recovered EMA9 test; a later recovered EMA21 test may qualify.

Continuation requires a strictly later session than the confirmed support test, a high at least `detection_price + 1.5 * detection_ATR`, and a close at/above that session's EMA9. Keeping the current advance threshold and detection-price reference avoids inventing a new magnitude. Same-bar highs cannot prove chronological continuation using daily OHLC. The old entering-pullback drawdown caps are removed; support preservation now determines invalidation. Other families keep their existing caps.

Missing/nonfinite/invalid required seeds or OHLC produce `INSUFFICIENT_DATA`. A complete, valid window with neither invalidation nor continuation is `NEUTRAL`.

### Complete sessions and a bounded window

Only pullbacks exclude prices dated on or after `as_of_date`, ensuring today's mutable bar never closes an outcome. Ten subsequent stored daily bars are required. Final classification therefore becomes visible no earlier than the calendar day after the tenth session. Later bars never extend the move window. Queries are also bounded by `as_of_date` for all families to prevent historical evaluation from seeing later prices.

### Historical synchronization without new schema

An Alembic data migration resets terminal pullback outcomes to `PENDING`, clears their derived prices, percentages, extrema, flags, and evaluation timestamp, and retains detection context. The existing evaluator rebuilds them under the new rule. Pending outcomes do not enter Calibration, follow-through, or empirical probability denominators, so legacy results cannot be presented as the new setup's evidence after migration.

The manual reclassification endpoint uses ordered stored prices for pullbacks, including rechecking `INSUFFICIENT_DATA` pullbacks, while other transitions retain aggregate reclassification. A shared reset helper prevents stale fill-once derived values from surviving an explicit reevaluation. Production migration and reevaluation were subsequently authorized explicitly and completed as recorded in `production-rollout.md`.

## Risks / Trade-offs

- [Detection EMA seeds may be intraday] → Explain the saved-context EMA trajectory rather than claiming exact final-chart reconstruction.
- [Ten stored bars may skip exchange sessions if symbol data is missing] → Retain the existing stored-bar horizon; a trusted exchange-session calendar is separate work. Insufficient windows remain pending and missing required inputs never become success.
- [Rebuilding legacy labels creates temporary pending counts and evaluator work] → Scope the migration to terminal entering pullbacks, preserve snapshots, and review migration output before deployment.
- [Daily highs do not represent realized trading profit] → Describe support and observed continuation, without implying execution results.

## Migration Plan

Deploy code with the data migration in the normal explicitly authorized deployment process. Stop evaluator writes while applying the migration, then restart evaluation; report rates only after their new settled sample qualifies. Downgrade resets terminal pullbacks again so the prior implementation can recompute its own rule; old exact labels are not restored. Do not roll code back while keeping new-rule labels as if they belonged to the old rule.

## Open Questions

None blocking. The retained 1.5 ATR continuation magnitude and detection-price reference were explicitly stated as implementation assumptions in this conversation; the operator specified wick recovery and a ten-session deadline.
