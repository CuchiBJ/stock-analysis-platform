"""Pure statistics helpers for context-aware calibration reporting."""
from __future__ import annotations

from math import sqrt
from typing import Optional


MIN_SETTLED_SAMPLES = 20


def wilson_interval(success: int, total: int, z: float = 1.96) -> Optional[tuple[float, float]]:
    """Return the Wilson score interval for a binomial proportion."""
    if total <= 0:
        return None
    proportion = success / total
    z2 = z * z
    denominator = 1 + z2 / total
    center = (proportion + z2 / (2 * total)) / denominator
    margin = (
        z
        * sqrt((proportion * (1 - proportion) / total) + z2 / (4 * total * total))
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def cohort_statistics(
    *,
    success: int = 0,
    failure: int = 0,
    neutral: int = 0,
    pending: int = 0,
    min_samples: int = MIN_SETTLED_SAMPLES,
) -> dict:
    """Build an honest, JSON-ready calibration cohort summary.

    A settled signal includes SUCCESS, FAILURE, and NEUTRAL. The empirical
    threshold is therefore based on every known outcome, not only decisive
    outcomes, because delivery rate uses the same denominator.
    """
    decisive = success + failure
    settled = decisive + neutral
    observed = settled + pending

    if settled == 0:
        status = "no_data"
    elif settled < min_samples:
        status = "insufficient"
    else:
        status = "empirical"

    success_rate = None
    delivery_rate = None
    confidence_interval = None
    if status == "empirical":
        success_rate = success / decisive if decisive else None
        delivery_rate = success / settled
        interval = wilson_interval(success, settled)
        if interval is not None:
            confidence_interval = {
                "low": round(interval[0], 4),
                "high": round(interval[1], 4),
            }

    return {
        "n_observed": observed,
        "n_settled": settled,
        "n_resolved": decisive,
        "n_pending": pending,
        "success_count": success,
        "failure_count": failure,
        "neutral_count": neutral,
        "success_rate": round(success_rate, 4) if success_rate is not None else None,
        "delivery_rate": round(delivery_rate, 4) if delivery_rate is not None else None,
        "confidence_interval": confidence_interval,
        "status": status,
        "samples_needed": max(0, min_samples - settled),
    }


def classify_drift(historical: dict, recent: dict) -> str:
    """Classify statistically separated recent delivery versus history."""
    if historical.get("status") != "empirical" or recent.get("status") != "empirical":
        return "insufficient"

    hist_interval = historical.get("confidence_interval")
    recent_interval = recent.get("confidence_interval")
    if not hist_interval or not recent_interval:
        return "insufficient"

    if recent_interval["high"] < hist_interval["low"]:
        return "deteriorating"
    if recent_interval["low"] > hist_interval["high"]:
        return "improving"
    return "stable"


def rate_delta_pp(current: dict, baseline: dict) -> Optional[float]:
    current_rate = current.get("delivery_rate")
    baseline_rate = baseline.get("delivery_rate")
    if current_rate is None or baseline_rate is None:
        return None
    return round((current_rate - baseline_rate) * 100, 2)
