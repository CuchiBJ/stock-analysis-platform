"""Symbol diagnostic — explain pass/fail per system list for any ticker.

Mirrors the filter logic of /actionable, /live, /queue/u-and-r,
/queue/emerging-leaders, /queue/building-bases as Python expressions
so each criterion is inspectable with (actual, threshold, passes).

DRIFT WARNING: each list's diagnose_*() must stay in sync with the
production filter. Tests in test_symbol_diagnostic.py guard against
divergence with synthetic metrics fixtures.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, timedelta
from typing import Any, Optional

from app.models.stock import StockMetrics
from app.services.quality_leader_gate import is_quality_leader, evaluate_minervini_criteria


@dataclass
class Criterion:
    name: str
    actual: Any            # value, None if missing
    threshold: Any         # number, [lo, hi] for range, or human-readable str
    passes: bool
    kind: str = "numeric"  # numeric | range | boolean | composite


@dataclass
class ListCheck:
    key: str               # machine id: "actionable", "u_and_r", ...
    name: str              # human label
    passes: bool           # True iff all criteria pass — does NOT guarantee inclusion when a cutoff applies
    criteria: list[Criterion] = field(default_factory=list)
    cutoff: Optional[dict] = None  # {kind: "top_n", n: 12, ranked_by: "priority_score"} when list applies a top-N cutoff after filtering


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _ge(name: str, actual: Optional[float], threshold: float) -> Criterion:
    if actual is None:
        return Criterion(name, None, threshold, False, "numeric")
    return Criterion(name, actual, threshold, actual >= threshold, "numeric")


def _gt(name: str, actual: Optional[float], threshold: float) -> Criterion:
    if actual is None:
        return Criterion(name, None, threshold, False, "numeric")
    return Criterion(name, actual, threshold, actual > threshold, "numeric")


def _in_range(name: str, actual: Optional[float], lo: float, hi: float) -> Criterion:
    if actual is None:
        return Criterion(name, None, [lo, hi], False, "range")
    return Criterion(name, actual, [lo, hi], lo <= actual <= hi, "range")


def _gt_field(name: str, actual: Optional[float], threshold: Optional[float]) -> Criterion:
    """A > B where both are runtime values."""
    if actual is None or threshold is None:
        return Criterion(name, actual, threshold, False, "numeric")
    return Criterion(name, actual, threshold, actual > threshold, "numeric")


def _bool(name: str, passes: bool, detail: str = "") -> Criterion:
    return Criterion(name, detail if detail else passes, "passes", passes, "boolean")


# ─── Per-list diagnostics ────────────────────────────────────────────────────

def diagnose_actionable(m: StockMetrics) -> ListCheck:
    """Mirrors _INSTITUTIONAL_SETUP + EMA trigger + /actionable extras."""
    crit: list[Criterion] = []

    # Institutional setup (9 conditions)
    crit.append(_ge("avg_volume_10d ≥ 800k",            m.avg_volume_10d, 800_000))
    crit.append(_ge("adr_percent ≥ 4%",                  m.adr_percent, 4.0))
    crit.append(_ge("current_price ≥ $5",                m.current_price, 5.0))
    crit.append(_gt("perf_1y > 30%",                     m.perf_1y, 30.0))
    crit.append(_gt_field("price > EMA50",               m.current_price, m.ema50))
    crit.append(_gt_field("price > SMA150",              m.current_price, m.sma150))
    crit.append(_gt_field("SMA150 > SMA200",             m.sma150, m.sma200))
    crit.append(_ge("distance to 52W high ≥ -3 ATR",     m.distance_to_high_52w_atr, -3.0))
    if m.current_price is not None and m.low_52w is not None:
        crit.append(Criterion(
            "price ≥ 52W low × 1.5",
            m.current_price, m.low_52w * 1.5,
            m.current_price >= m.low_52w * 1.5,
            "numeric",
        ))
    else:
        crit.append(Criterion("price ≥ 52W low × 1.5", None, None, False, "numeric"))

    # EMA trigger (either EMA9 or EMA21 within band)
    d9 = m.distance_to_ema9_atr
    d21 = m.distance_to_ema21_atr
    ema9_ok = d9 is not None and -1.0 <= d9 <= 0.5
    ema21_ok = d21 is not None and -1.0 <= d21 <= 0.5
    crit.append(Criterion(
        "EMA9 distance ∈ [-1.0, +0.5] ATR  OR  EMA21 distance ∈ [-1.0, +0.5] ATR",
        f"d_ema9={d9}, d_ema21={d21}",
        "either in [-1.0, +0.5]",
        ema9_ok or ema21_ok,
        "composite",
    ))

    # /actionable extras
    crit.append(_ge("pullback_quality_score ≥ 55",       m.pullback_quality_score, 55.0))
    crit.append(_ge("avg_volume_10d ≥ 700k (extra)",     m.avg_volume_10d, 700_000))
    crit.append(_ge("adr_percent ≥ 3% (extra)",          m.adr_percent, 3.0))

    passes = all(c.passes for c in crit)
    return ListCheck(
        "actionable", "Top Actionable Setups", passes, crit,
        cutoff={
            "kind": "top_n",
            "n": 12,
            "ranked_by": "priority_score (compound)",
            "note": "Passing filter ≠ appearing — endpoint returns top 12 ranked by priority_score; ties broken by pullback_quality.",
        },
    )


def diagnose_live(m: StockMetrics, has_recent_non_stable_obs: bool) -> ListCheck:
    """Mirrors /transitions/live filter: institutional + EMA trigger + non-stable transition."""
    crit: list[Criterion] = []

    # Institutional (same 9 as actionable)
    crit.append(_ge("avg_volume_10d ≥ 800k",            m.avg_volume_10d, 800_000))
    crit.append(_ge("adr_percent ≥ 4%",                  m.adr_percent, 4.0))
    crit.append(_ge("current_price ≥ $5",                m.current_price, 5.0))
    crit.append(_gt("perf_1y > 30%",                     m.perf_1y, 30.0))
    crit.append(_gt_field("price > EMA50",               m.current_price, m.ema50))
    crit.append(_gt_field("price > SMA150",              m.current_price, m.sma150))
    crit.append(_gt_field("SMA150 > SMA200",             m.sma150, m.sma200))
    crit.append(_ge("distance to 52W high ≥ -3 ATR",     m.distance_to_high_52w_atr, -3.0))

    # EMA trigger
    d9 = m.distance_to_ema9_atr
    d21 = m.distance_to_ema21_atr
    crit.append(Criterion(
        "EMA9 OR EMA21 distance ∈ [-1.0, +0.5] ATR",
        f"d_ema9={d9}, d_ema21={d21}",
        "either in [-1.0, +0.5]",
        (d9 is not None and -1.0 <= d9 <= 0.5) or (d21 is not None and -1.0 <= d21 <= 0.5),
        "composite",
    ))

    # Non-stable transition recently detected
    crit.append(_bool(
        "Recent non-stable transition observation exists",
        has_recent_non_stable_obs,
        "yes" if has_recent_non_stable_obs else "no observations recorded",
    ))

    passes = all(c.passes for c in crit)
    return ListCheck(
        "live", "Live Transition Feed", passes, crit,
        cutoff={
            "kind": "top_n",
            "n": 10,
            "ranked_by": "entering_pullback first, then pre-reclaim by observation_priority",
            "note": "Passing filter ≠ appearing — endpoint returns top 10 by transition priority order.",
        },
    )


def diagnose_u_and_r(
    m: StockMetrics,
    history_25d: list[dict],          # [{date, d21, d50}]
    has_recent_2d_obs: bool,
) -> ListCheck:
    """Mirrors setup_queue_service.list_u_and_r filter."""
    crit: list[Criterion] = []

    # Quality leader gate
    crit.append(_bool(
        "Minervini quality leader (8 SEPA criteria)",
        is_quality_leader(m),
        "pass" if is_quality_leader(m) else "fail (see Minervini detail)",
    ))

    # d21_atr range
    d21 = m.distance_to_ema21_atr
    crit.append(_in_range("distance_to_ema21 ∈ [-0.5, +1.5] ATR", d21, -0.5, 1.5))

    # Recent non-stable observation (last 2 days)
    crit.append(_bool(
        "Non-stable transition observation in last 2 days",
        has_recent_2d_obs,
        "yes" if has_recent_2d_obs else "no recent observation",
    ))

    # "From above" rule: any d21_atr > 0.5 between day-10 and day-5
    today = date.today()
    day10 = today - timedelta(days=10)
    day5 = today - timedelta(days=5)
    was_above = any(
        h.get("d21") is not None and h["d21"] > 0.5 and day10 <= h["date"] <= day5
        for h in history_25d
    )
    max_d21_in_window = max(
        (h["d21"] for h in history_25d
         if h.get("d21") is not None and day10 <= h["date"] <= day5),
        default=None,
    )
    crit.append(Criterion(
        f'"From above" rule: max d21_atr in days 5-10 ago > 0.5',
        max_d21_in_window,
        0.5,
        was_above,
        "numeric",
    ))

    # "No broke EMA50" rule: d50_atr never negative in last 25 days
    broke = any(h.get("d50") is not None and h["d50"] < 0 for h in history_25d)
    min_d50 = min(
        (h["d50"] for h in history_25d if h.get("d50") is not None),
        default=None,
    )
    crit.append(Criterion(
        '"No broke EMA50" rule: min d50_atr in last 25d ≥ 0',
        min_d50,
        0.0,
        not broke,
        "numeric",
    ))

    passes = all(c.passes for c in crit)
    return ListCheck("u_and_r", "Queue · Undercut & Rally", passes, crit)


def diagnose_emerging_leaders(m: StockMetrics) -> ListCheck:
    """Mirrors setup_queue_service.list_emerging_leaders filter.

    Quality filters + perf_13w > 20 + RS > 105 + above EMA50/200 + NOT fully Minervini.
    """
    crit: list[Criterion] = []

    # QUALITY_FILTERS (universe_filters)
    crit.append(_ge("avg_volume_10d ≥ 500k",   m.avg_volume_10d, 500_000))
    crit.append(_ge("current_price ≥ $5",      m.current_price, 5.0))
    crit.append(_ge("adr_percent ≥ 2%",         m.adr_percent, 2.0))

    # Performance + RS
    crit.append(_gt("perf_13w > 20%",          m.perf_13w, 20.0))
    crit.append(_gt("relative_strength_spy > 105", m.relative_strength_spy, 105.0))

    # Price above EMA50 + EMA200
    crit.append(_gt_field("price > EMA50",     m.current_price, m.ema50))
    crit.append(_gt_field("price > EMA200",    m.current_price, m.ema200))

    # MUST NOT be fully Minervini (emerging = not yet leader)
    is_leader = is_quality_leader(m)
    crit.append(_bool(
        "NOT fully Minervini quality leader",
        not is_leader,
        "passes (still emerging)" if not is_leader else "fails (already a quality leader)",
    ))

    passes = all(c.passes for c in crit)
    return ListCheck(
        "emerging_leaders", "Queue · Emerging Leaders", passes, crit,
        cutoff={
            "kind": "top_n",
            "n": 30,
            "ranked_by": "perf_13w descending",
            "note": "Passing filter ≠ appearing — endpoint returns top 30 by perf_13w.",
        },
    )


def diagnose_building_bases(m: StockMetrics, d21_history_30d: list[float]) -> ListCheck:
    """Mirrors setup_queue_service.list_building_bases filter."""
    crit: list[Criterion] = []

    # QUALITY_FILTERS
    crit.append(_ge("avg_volume_10d ≥ 500k",   m.avg_volume_10d, 500_000))
    crit.append(_ge("current_price ≥ $5",      m.current_price, 5.0))
    crit.append(_ge("adr_percent ≥ 2%",         m.adr_percent, 2.0))

    # VCP + weeks in base
    crit.append(_ge("vcp_score ≥ 70",           m.vcp_score, 70.0))
    crit.append(_ge("weeks_in_base ≥ 6",        m.weeks_in_base, 6.0))

    # Must be quality leader
    crit.append(_bool(
        "Minervini quality leader",
        is_quality_leader(m),
        "pass" if is_quality_leader(m) else "fail (see Minervini detail)",
    ))

    # ATR oscillation: max-min of d21_atr in last 20 days ≤ 2.0, need ≥10 data points
    if len(d21_history_30d) < 10:
        crit.append(Criterion(
            "ATR oscillation has ≥10 data points",
            len(d21_history_30d), 10, False, "numeric",
        ))
    else:
        atr_range = max(d21_history_30d) - min(d21_history_30d)
        crit.append(Criterion(
            "ATR oscillation (max-min d21_atr last ~20d) ≤ 2.0",
            atr_range, 2.0, atr_range <= 2.0, "numeric",
        ))

    passes = all(c.passes for c in crit)
    return ListCheck("building_bases", "Queue · Building Bases", passes, crit)


# ─── Assembly ────────────────────────────────────────────────────────────────

def list_check_to_dict(lc: ListCheck) -> dict:
    return {
        "key": lc.key,
        "name": lc.name,
        "passes": lc.passes,
        "criteria": [asdict(c) for c in lc.criteria],
        "cutoff": lc.cutoff,
    }
