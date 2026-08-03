## Context

`MarketContextEngine` currently converts each classified session into a boolean `damaged` flag and `_health_state()` requires five trailing `False` values to enter `RECOVERING`. This intentionally asymmetric policy prevents one strong rebound from erasing prior damage, but it also gives a routine `NARROWING`/`THINNING` pullback the same reset power as `COLLAPSING`/`EXHAUSTED`. The live UI therefore describes an unrealistic consecutive-session hurdle and can remain `DEFENSIVO` through a legitimate stair-step recovery.

The engine is already larger than 900 lines. Database aggregation remains cohesive there, but the pure health policy should be isolated so severity and recovery rules can be tested without database fixtures.

## Goals / Non-Goals

**Goals:**

- Distinguish mild pullbacks from severe relapses.
- Allow up to two non-clean sessions inside a seven-session repair window.
- Prevent recent severe deterioration from qualifying as recovery.
- Keep the existing damage-memory and posture hierarchy conservative.
- Make recovery progress and blocking severe damage visible without adding an analytics table.
- Extract the pure severity/recovery policy into a small service module.

**Non-Goals:**

- Recalibrate descriptor thresholds or leader definitions.
- Change follow-through classification or its posture ceiling.
- Persist health snapshots or intraday transitions.
- Redesign the full Market Context component.

## Decisions

### D1. Three-level daily severity

Every classified day receives one of:

- `clean`: participation is `STABLE/EXPANDING` and leadership is `HEALTHY/EXPANDING`.
- `mild`: participation is `NARROWING` or leadership is `THINNING`, with no severe descriptor.
- `severe`: participation is `COLLAPSING`, or leadership is `COLLAPSING/EXHAUSTED`.

Severity uses worst-case composition, so severe always overrides mild. The existing `damaged` boolean remains `severity != clean` for backward compatibility and for the 20-session damage/episode counters.

Alternative rejected: reduce the consecutive streak from five to three. It remains path-dependent and still lets a mild one-day pullback erase all repair progress.

### D2. Recovery is five clean of seven with a severe-damage veto

`RECOVERING` activates when the latest seven classified sessions contain at least five `clean` sessions and the latest three contain zero `severe` sessions. Mild sessions consume one of the two tolerated slots but do not reset all progress. A severe session blocks recovery for three classified sessions.

The existing `ROBUST`, `FRAGILE`, and `DAMAGED` thresholds remain. `ROBUST` additionally requires zero severe sessions in the latest three so a fresh collapse cannot coexist with a robust label. Recovery remains an overlay after the baseline state is computed.

Alternative rejected: use a weighted score. The 5-of-7 rule is easier to explain and audit while still matching the intended market behavior.

### D3. Additive health contract

Keep `repair_streak` as the trailing clean-session diagnostic. Add:

- `repair_clean_days`: clean count in the rolling repair window.
- `repair_window_days`: number of classified sessions considered, capped at 7.
- `repair_required_clean_days`: constant 5.
- `recent_severe_days`: severe count in the latest three.
- `severe_lookback_days`: number considered, capped at 3.
- `severity` on each daily series point.

This avoids silently changing the meaning of an existing field and permits older frontend clients to ignore the additions.

### D4. Pure policy extraction

Create `app/services/market_health.py` containing constants, severity classification, and the pure health-state reducer. `MarketContextEngine` retains SQL aggregation and descriptor calculation, delegates severity/state policy to the new module, and keeps compatibility wrappers for existing callers/tests where useful.

### D5. Compact visual encoding

The damage strip uses gray for clean, amber for mild, and red for severe. The drawer presents one concise recovery line (`X/7 limpias · Y severas/3`) and updates the unlock/explanation copy. It does not add a new card or raw table.

## Risks / Trade-offs

- **[Recovery becomes too permissive]** → A severe-damage veto over the latest three sessions and the unchanged follow-through ceiling prevent normal sizing while relapses or failed signals remain active.
- **[Old clients do not understand severity]** → `damaged` remains present and semantically unchanged; all new API fields are additive.
- **[A mild pullback can still delay recovery]** → This is intentional: it consumes one of two tolerated slots without erasing the entire window.
- **[Intraday classifications can fluctuate]** → No new persistence is introduced; the change addresses repair semantics, not pipeline readiness.

## Migration Plan

1. Deploy backend policy and additive API fields.
2. Deploy frontend severity colors and recovery copy.
3. No data migration or backfill is required because health is derived on demand.
4. Rollback restores the prior pure policy; stored data is unaffected.

## Open Questions

None. The agreed initial calibration is 5 clean of 7 and zero severe of the latest 3; future changes should be evidence-driven.
