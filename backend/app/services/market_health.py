"""Pure severity and recovery policy for Market Context health.

Database aggregation and participation/leadership descriptor calculation stay in
``MarketContextEngine``. This module owns the auditable state policy: distinguish
ordinary pullbacks from severe relapses and qualify an uneven recovery without
requiring a brittle consecutive-day streak.
"""
from __future__ import annotations

from typing import Literal, Sequence

from app.services.market_posture_policy import POSTURE_THRESHOLDS

DamageSeverity = Literal["clean", "mild", "severe"]

CLEAN: DamageSeverity = "clean"
MILD: DamageSeverity = "mild"
SEVERE: DamageSeverity = "severe"

HEALTH_MIN_CLASSIFIED_DAYS = 10
REPAIR_WINDOW_DAYS = 7
REPAIR_REQUIRED_CLEAN_DAYS = 5
SEVERE_LOOKBACK_DAYS = 3

# Accelerated recovery is deliberately narrower than the normal repair policy:
# it can only relax a DAMAGED posture from DEFENSIVO to SELECTIVO.  Returning to
# NORMAL still requires the existing 5-clean-of-7 health transition.
ACCELERATED_RECOVERY_REQUIRED_DAYS = POSTURE_THRESHOLDS.normal_confirmation_days
ACCELERATED_RECOVERY_BREADTH_MIN = POSTURE_THRESHOLDS.normal_breadth_entry
ACCELERATED_RECOVERY_LEADER_DENSITY_MIN = POSTURE_THRESHOLDS.normal_leader_density_entry

# Exceptional momentum thresholds are intentionally above recent empirical
# extremes (90-session p95 at implementation: +16.48pp breadth and +27.67%
# leader-density expansion). This is a one-session escape hatch to SELECTIVO,
# never a replacement for normal health repair.
EXCEPTIONAL_RECOVERY_BREADTH_MIN = POSTURE_THRESHOLDS.exceptional_breadth_entry
EXCEPTIONAL_RECOVERY_BREADTH_DELTA_MIN_PP = (
    POSTURE_THRESHOLDS.exceptional_breadth_delta_min_pp
)
EXCEPTIONAL_RECOVERY_LEADER_DENSITY_MIN = (
    POSTURE_THRESHOLDS.exceptional_leader_density_entry
)
EXCEPTIONAL_RECOVERY_LEADER_DELTA_MIN_PCT = (
    POSTURE_THRESHOLDS.exceptional_leader_density_delta_min_pct
)

ROBUST_MAX_DAMAGED_DAYS = 2
ROBUST_MAX_EPISODES = 1
DAMAGED_MIN_DAYS = 8
DAMAGED_RECENT_WINDOW = 5
DAMAGED_MIN_RECENT = 3

_MILD_PARTICIPATION = frozenset({"NARROWING"})
_SEVERE_PARTICIPATION = frozenset({"COLLAPSING"})
_MILD_LEADERSHIP = frozenset({"THINNING"})
_SEVERE_LEADERSHIP = frozenset({"COLLAPSING", "EXHAUSTED"})


def classify_damage_severity(participation: str, leadership: str) -> DamageSeverity:
    """Return the worst daily severity across participation and leadership."""
    p = (participation or "UNKNOWN").upper()
    l = (leadership or "UNKNOWN").upper()
    if p in _SEVERE_PARTICIPATION or l in _SEVERE_LEADERSHIP:
        return SEVERE
    if p in _MILD_PARTICIPATION or l in _MILD_LEADERSHIP:
        return MILD
    return CLEAN


def is_confirmed_recovery_session(
    *,
    index_bullish: bool,
    breadth_ratio: float,
    participation: str,
    leader_density: float,
    leadership: str,
    severity: DamageSeverity,
) -> bool:
    """Return whether one session supplies full level + rate recovery evidence.

    Levels prevent a sharp bounce from a still-weak base from qualifying; the
    EXPANDING descriptors require positive five-session rates of change.  A
    severe session is always vetoed even if malformed inputs otherwise appear
    constructive.
    """
    return (
        severity != SEVERE
        and index_bullish
        and breadth_ratio > ACCELERATED_RECOVERY_BREADTH_MIN
        and (participation or "UNKNOWN").upper() == "EXPANDING"
        and leader_density > ACCELERATED_RECOVERY_LEADER_DENSITY_MIN
        and (leadership or "UNKNOWN").upper() == "EXPANDING"
    )


def is_exceptional_recovery_session(
    *,
    index_bullish: bool,
    index_new_high: bool,
    breadth_ratio: float,
    breadth_delta_pp: float,
    participation: str,
    leader_density: float,
    leader_density_delta_pct: float,
    leadership: str,
    severity: DamageSeverity,
) -> bool:
    """Return whether one session is exceptional enough for early SELECTIVO.

    Unlike ordinary confirmation, this requires an actual index new-high print,
    absolute participation/leadership levels, and expansion rates well beyond
    recent p95 observations. Severe anatomy remains an absolute veto.
    """
    return (
        severity != SEVERE
        and index_bullish
        and index_new_high
        and breadth_ratio > EXCEPTIONAL_RECOVERY_BREADTH_MIN
        and breadth_delta_pp > EXCEPTIONAL_RECOVERY_BREADTH_DELTA_MIN_PP
        and (participation or "UNKNOWN").upper() == "EXPANDING"
        and leader_density > EXCEPTIONAL_RECOVERY_LEADER_DENSITY_MIN
        and leader_density_delta_pct > EXCEPTIONAL_RECOVERY_LEADER_DELTA_MIN_PCT
        and (leadership or "UNKNOWN").upper() == "EXPANDING"
    )


def trailing_confirmation_streak(confirmations: Sequence[bool]) -> int:
    """Count consecutive confirmed-recovery sessions at the series tail."""
    streak = 0
    for confirmed in reversed(confirmations):
        if not confirmed:
            break
        streak += 1
    return streak


def compute_health_state(
    severities: Sequence[DamageSeverity],
    recovery_confirmations: Sequence[bool] = (),
    exceptional_recovery_sessions: Sequence[bool] = (),
) -> dict:
    """Reduce ascending daily severities into health state and diagnostics.

    Recovery is evidence over a rolling window, not a consecutive streak:
    at least 5 clean of the latest 7 and no severe relapse in the latest 3.
    """
    values = list(severities)
    damaged = [severity != CLEAN for severity in values]
    n = len(values)
    damaged_days = sum(damaged)
    episodes = sum(
        1 for i, flag in enumerate(damaged)
        if flag and (i == 0 or not damaged[i - 1])
    )

    repair_streak = 0
    for severity in reversed(values):
        if severity != CLEAN:
            break
        repair_streak += 1
    days_since_last_damage = repair_streak if damaged_days else None

    repair_window = values[-REPAIR_WINDOW_DAYS:]
    severe_window = values[-SEVERE_LOOKBACK_DAYS:]
    repair_clean_days = sum(1 for severity in repair_window if severity == CLEAN)
    recent_severe_days = sum(1 for severity in severe_window if severity == SEVERE)
    repair_ready = (
        len(repair_window) == REPAIR_WINDOW_DAYS
        and repair_clean_days >= REPAIR_REQUIRED_CLEAN_DAYS
        and recent_severe_days == 0
    )
    recovery_confirmation_streak = trailing_confirmation_streak(
        recovery_confirmations
    )
    exceptional_recovery_session = bool(
        exceptional_recovery_sessions and exceptional_recovery_sessions[-1]
    )

    if n < HEALTH_MIN_CLASSIFIED_DAYS:
        state = "UNKNOWN"
    elif (
        damaged_days <= ROBUST_MAX_DAMAGED_DAYS
        and episodes <= ROBUST_MAX_EPISODES
        and recent_severe_days == 0
    ):
        state = "ROBUST"
    else:
        recent_damage = damaged[-DAMAGED_RECENT_WINDOW:]
        if damaged_days >= DAMAGED_MIN_DAYS or sum(recent_damage) >= DAMAGED_MIN_RECENT:
            state = "DAMAGED"
        else:
            state = "FRAGILE"
        if repair_ready:
            state = "RECOVERING"

    return {
        "state": state,
        "episodes": episodes,
        "damaged_days": damaged_days,
        "repair_streak": repair_streak,
        "days_since_last_damage": days_since_last_damage,
        "repair_clean_days": repair_clean_days,
        "repair_window_days": len(repair_window),
        "repair_required_clean_days": REPAIR_REQUIRED_CLEAN_DAYS,
        "recent_severe_days": recent_severe_days,
        "severe_lookback_days": len(severe_window),
        "recovery_confirmation_streak": recovery_confirmation_streak,
        "recovery_confirmation_required_days": ACCELERATED_RECOVERY_REQUIRED_DAYS,
        "exceptional_recovery_session": exceptional_recovery_session,
    }
