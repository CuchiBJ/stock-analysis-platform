"""Auditable level + trend policy and hysteresis for Market Context posture.

The descriptor engines still describe five-session rates of change.  This
module adds the missing absolute-level gates and stateful entry/exit bands used
by the operational posture.  All ratios are universe-normalized.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Sequence


@dataclass(frozen=True)
class PostureThresholds:
    # Hard defensive floors. A session below either is defensive regardless of
    # the other dimension. Exiting that zone requires a small positive buffer.
    defensive_breadth_entry: float = 0.40
    defensive_breadth_exit: float = 0.43
    defensive_leader_density_entry: float = 0.05
    defensive_leader_density_exit: float = 0.06

    # NORMAL requires three confirmed sessions above the entry levels. Once
    # active it persists to the lower exit bands to avoid daily threshold churn.
    normal_breadth_entry: float = 0.60
    normal_breadth_exit: float = 0.55
    normal_leader_density_entry: float = 0.10
    normal_leader_density_exit: float = 0.08
    normal_confirmation_days: int = 3

    # AGRESIVO requires an already-confirmed normal environment plus a current
    # index new high and strong expansion. Its exit bands are deliberately lower.
    aggressive_breadth_entry: float = 0.70
    aggressive_breadth_exit: float = 0.65
    aggressive_leader_density_entry: float = 0.15
    aggressive_leader_density_exit: float = 0.12

    # Recovery overrides remain SELECTIVO-only. The exceptional rate thresholds
    # sit above the observed 90-session p95 (+16.48pp / +27.67%).
    exceptional_breadth_entry: float = 0.65
    exceptional_breadth_delta_min_pp: float = 20.0
    exceptional_leader_density_entry: float = 0.12
    exceptional_leader_density_delta_min_pct: float = 50.0

    # A one-session exceptional override may hold SELECTIVO for today plus two
    # following sessions, but only while normal exit-quality anatomy survives.
    exceptional_retention_sessions: int = 2


POSTURE_THRESHOLDS = PostureThresholds()

_SEVERE_PARTICIPATION = frozenset({"COLLAPSING"})
_SEVERE_LEADERSHIP = frozenset({"COLLAPSING", "EXHAUSTED"})
_NORMAL_PARTICIPATION = frozenset({"STABLE", "EXPANDING"})
_NORMAL_LEADERSHIP = frozenset({"HEALTHY", "EXPANDING"})


def thresholds_contract() -> dict:
    """JSON-ready threshold contract exposed by the Market Context API."""
    return asdict(POSTURE_THRESHOLDS)


def classify_policy_session(
    *,
    index_bullish: bool,
    index_above_ema200: bool,
    index_new_high: bool,
    breadth_ratio: float,
    participation: str,
    leader_density: float,
    leadership: str,
    severity: str,
    thresholds: PostureThresholds = POSTURE_THRESHOLDS,
) -> dict:
    """Classify one session against every posture entry/exit band."""
    p = (participation or "UNKNOWN").upper()
    l = (leadership or "UNKNOWN").upper()
    severe = (
        severity == "severe"
        or p in _SEVERE_PARTICIPATION
        or l in _SEVERE_LEADERSHIP
    )
    complete = breadth_ratio is not None and leader_density is not None

    defensive_entry = bool(
        complete
        and (
            breadth_ratio < thresholds.defensive_breadth_entry
            or leader_density < thresholds.defensive_leader_density_entry
        )
    ) or severe
    defensive_exit = bool(
        complete
        and breadth_ratio >= thresholds.defensive_breadth_exit
        and leader_density >= thresholds.defensive_leader_density_exit
        and not severe
    )
    normal_entry = bool(
        complete
        and index_bullish
        and breadth_ratio > thresholds.normal_breadth_entry
        and leader_density > thresholds.normal_leader_density_entry
        and p in _NORMAL_PARTICIPATION
        and l in _NORMAL_LEADERSHIP
        and not severe
    )
    normal_exit = bool(
        complete
        and index_above_ema200
        and breadth_ratio >= thresholds.normal_breadth_exit
        and leader_density >= thresholds.normal_leader_density_exit
        and p not in _SEVERE_PARTICIPATION
        and l not in _SEVERE_LEADERSHIP
        and not severe
    )
    aggressive_entry = bool(
        complete
        and index_bullish
        and index_new_high
        and breadth_ratio > thresholds.aggressive_breadth_entry
        and leader_density > thresholds.aggressive_leader_density_entry
        and p == "EXPANDING"
        and l == "EXPANDING"
        and not severe
    )
    aggressive_exit = bool(
        complete
        and index_above_ema200
        and breadth_ratio >= thresholds.aggressive_breadth_exit
        and leader_density >= thresholds.aggressive_leader_density_exit
        and p in _NORMAL_PARTICIPATION
        and l in _NORMAL_LEADERSHIP
        and not severe
    )
    return {
        "complete": complete,
        "severe": severe,
        "defensive_entry": defensive_entry,
        "defensive_exit": defensive_exit,
        "normal_entry": normal_entry,
        "normal_exit": normal_exit,
        "aggressive_entry": aggressive_entry,
        "aggressive_exit": aggressive_exit,
    }


def evaluate_policy_history(
    days: Sequence[dict],
    *,
    thresholds: PostureThresholds = POSTURE_THRESHOLDS,
) -> dict:
    """Reduce ascending classified sessions into hysteretic policy state.

    NORMAL activates after three consecutive entry-quality sessions. AGRESIVO
    activates only from confirmed NORMAL on a strong new-high session. Active
    states persist while their lower exit bands hold. Exceptional recovery has
    a separate two-session bounded retention and is immediately cancelled by a
    severe day or failure of NORMAL exit-quality anatomy.
    """
    defensive_active = False
    normal_active = False
    aggressive_active = False
    normal_streak = 0
    exceptional_age = None
    today_signals = None

    for day in days:
        signals = classify_policy_session(
            index_bullish=day.get("index_bullish", False),
            index_above_ema200=day.get("index_above_ema200", False),
            index_new_high=day.get("index_new_high", False),
            breadth_ratio=day.get("breadth_ratio"),
            participation=day.get("participation", "UNKNOWN"),
            leader_density=day.get("leader_density"),
            leadership=day.get("leadership", "UNKNOWN"),
            severity=day.get("severity", "severe"),
            thresholds=thresholds,
        )
        day["policy_signals"] = signals
        today_signals = signals

        if defensive_active and signals["defensive_exit"]:
            defensive_active = False
        if signals["defensive_entry"]:
            defensive_active = True

        normal_streak = normal_streak + 1 if signals["normal_entry"] else 0
        if normal_active and not signals["normal_exit"]:
            normal_active = False
        if not normal_active and normal_streak >= thresholds.normal_confirmation_days:
            normal_active = True

        if aggressive_active and not signals["aggressive_exit"]:
            aggressive_active = False
        if not aggressive_active and normal_active and signals["aggressive_entry"]:
            aggressive_active = True

        if day.get("exceptional_recovery", False):
            exceptional_age = 0
        elif exceptional_age is not None:
            exceptional_age += 1

        if (
            exceptional_age is not None
            and (
                exceptional_age > thresholds.exceptional_retention_sessions
                or not signals["normal_exit"]
                or signals["severe"]
            )
        ):
            exceptional_age = None

    return {
        "thresholds": thresholds_contract(),
        "defensive_active": defensive_active,
        "normal_confirmation_streak": normal_streak,
        "normal_confirmation_required_days": thresholds.normal_confirmation_days,
        "normal_active": normal_active,
        "aggressive_active": aggressive_active,
        "exceptional_retained": exceptional_age is not None,
        "exceptional_retention_age": exceptional_age,
        "exceptional_retention_sessions": thresholds.exceptional_retention_sessions,
        "today": today_signals or {},
    }
