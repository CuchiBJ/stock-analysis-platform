"""Pure severity and recovery policy for Market Context health.

Database aggregation and participation/leadership descriptor calculation stay in
``MarketContextEngine``. This module owns the auditable state policy: distinguish
ordinary pullbacks from severe relapses and qualify an uneven recovery without
requiring a brittle consecutive-day streak.
"""
from __future__ import annotations

from typing import Literal, Sequence

DamageSeverity = Literal["clean", "mild", "severe"]

CLEAN: DamageSeverity = "clean"
MILD: DamageSeverity = "mild"
SEVERE: DamageSeverity = "severe"

HEALTH_MIN_CLASSIFIED_DAYS = 10
REPAIR_WINDOW_DAYS = 7
REPAIR_REQUIRED_CLEAN_DAYS = 5
SEVERE_LOOKBACK_DAYS = 3

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


def compute_health_state(severities: Sequence[DamageSeverity]) -> dict:
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
    }
