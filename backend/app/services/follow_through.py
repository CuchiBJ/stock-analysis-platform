"""Follow-through engine — is the market PAYING recent signals?

The behavioral dimension of Market Context: instead of describing the market's
anatomy (breadth, leader counts), it measures the market's response to capital
— what happened to the bullish transitions detected in the recent window
(pre-reclaim setups, breakouts, reclaims), scored by outcome_tracker.

Two layers, because outcomes need ~10 trading days to resolve:
- CONFIRMED: resolved observations (SUCCESS/FAILURE/NEUTRAL) in the window,
  read as delivery rate = SUCCESS / (S+F+N). Neutrals count against — a signal
  that settled without paying still tied up capital.
- PROVISIONAL: young PENDING observations read through their early proxies
  (pct_5d, ATR-normalized). Provisional evidence can only DOWNGRADE the
  descriptor, never certify PAYING — fresh signals dying is actionable now;
  fresh signals rising still have 5 days to fail.

Deterioration-family transitions (weakening/distribution/failing) are excluded:
their SUCCESS means the stock FELL, which would invert the reading.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.services.outcome_tracker import BREAKOUT, PRE_RECLAIM, RECLAIM_CONT

# Bullish signal families — the only ones where SUCCESS means "the market paid".
BULLISH_TRANSITIONS = frozenset(PRE_RECLAIM | BREAKOUT | RECLAIM_CONT)

FT_FAMILIES = {
    'pre_reclaim':          frozenset(PRE_RECLAIM),
    'breakout':             frozenset(BREAKOUT),
    'reclaim_continuation': frozenset(RECLAIM_CONT),
}

# Detection window (~15 trading days) and the baseline history before it.
FT_WINDOW_CAL_DAYS = 21
FT_BASELINE_CAL_DAYS = 180

# Minimum samples before each layer is trusted.
FT_MIN_RESOLVED = 6
FT_MIN_BASELINE_RESOLVED = 30
FT_MIN_PROVISIONAL = 5

# Provisional read on a PENDING observation's 5-day move, in ATR units.
FT_PROV_ON_TRACK_ATR = 1.0
FT_PROV_FAILING_ATR = -1.5
FT_PROV_ON_TRACK_PCT = 4.0    # fallback when ATR is missing
FT_PROV_FAILING_PCT = -5.0

# Descriptor thresholds. Baseline-relative when history allows, absolute fallback
# otherwise (0.45 ≈ the empirical all-history delivery rate at launch).
FT_PAYING_DELTA_PP = +10.0
FT_NOT_PAYING_DELTA_PP = -15.0
FT_PAYING_ABS = 0.45
FT_NOT_PAYING_ABS = 0.25
FT_PROV_FAIL_DOWNGRADE = 0.5   # ≥50% of fresh signals failing → downgrade one notch


@dataclass
class FollowThroughAnalysis:
    descriptor: str            # PAYING | MIXED | NOT_PAYING | UNKNOWN
    basis: str                 # baseline | absolute | provisional | insufficient (+downgrade tag)
    window_days: int           # calendar days of the detection window
    signals: int               # bullish signals detected in window (all statuses)
    resolved: int
    success: int
    failure: int
    neutral: int
    pending: int
    delivery_rate: Optional[float]       # S/(S+F+N) among resolved in window
    baseline_rate: Optional[float]       # same over the baseline period
    baseline_n: int
    delta_pp: Optional[float]            # (delivery - baseline) in percentage points
    provisional_on_track: int
    provisional_failing: int
    provisional_unclear: int
    per_family: dict = field(default_factory=dict)  # {family: {signals, success, failure, neutral, delivery}}


def classify_provisional(
    pct_5d: Optional[float],
    price_at_detection: Optional[float],
    atr_at_detection: Optional[float],
) -> Optional[str]:
    """Early read on a PENDING observation: 'on_track', 'failing', or None.

    ATR-normalized when possible (a -4% move is noise on a 6% ADR name and a
    break on a 2% one); percentage fallback otherwise. None = too early or too
    ambiguous to lean on — never force a young signal into a bucket.
    """
    if pct_5d is None:
        return None
    if price_at_detection and atr_at_detection and atr_at_detection > 0:
        move_atr = (pct_5d / 100.0 * price_at_detection) / atr_at_detection
        if move_atr <= FT_PROV_FAILING_ATR:
            return 'failing'
        if move_atr >= FT_PROV_ON_TRACK_ATR:
            return 'on_track'
        return None
    if pct_5d <= FT_PROV_FAILING_PCT:
        return 'failing'
    if pct_5d >= FT_PROV_ON_TRACK_PCT:
        return 'on_track'
    return None


def classify_follow_through(
    *,
    success: int,
    failure: int,
    neutral: int,
    baseline_success: int,
    baseline_failure: int,
    baseline_neutral: int,
    prov_on_track: int,
    prov_failing: int,
) -> dict:
    """Pure descriptor logic → {descriptor, basis, delivery_rate, baseline_rate, delta_pp}.

    Confirmed layer decides; provisional layer can only downgrade one notch
    (PAYING→MIXED, MIXED→NOT_PAYING) or, with no confirmed sample yet, warn on
    its own (never certifying PAYING by itself).
    """
    resolved = success + failure + neutral
    delivery = (success / resolved) if resolved else None

    baseline_n = baseline_success + baseline_failure + baseline_neutral
    baseline = (baseline_success / baseline_n) if baseline_n else None

    delta_pp = None
    prov_classified = prov_on_track + prov_failing

    if resolved >= FT_MIN_RESOLVED:
        if baseline_n >= FT_MIN_BASELINE_RESOLVED:
            delta_pp = (delivery - baseline) * 100
            if delta_pp >= FT_PAYING_DELTA_PP:
                descriptor = "PAYING"
            elif delta_pp <= FT_NOT_PAYING_DELTA_PP:
                descriptor = "NOT_PAYING"
            else:
                descriptor = "MIXED"
            basis = "baseline"
        else:
            if delivery >= FT_PAYING_ABS:
                descriptor = "PAYING"
            elif delivery <= FT_NOT_PAYING_ABS:
                descriptor = "NOT_PAYING"
            else:
                descriptor = "MIXED"
            basis = "absolute"

        if (
            prov_classified >= FT_MIN_PROVISIONAL
            and prov_failing / prov_classified >= FT_PROV_FAIL_DOWNGRADE
            and descriptor != "NOT_PAYING"
        ):
            descriptor = "MIXED" if descriptor == "PAYING" else "NOT_PAYING"
            basis += "+provisional_downgrade"

    elif prov_classified >= FT_MIN_PROVISIONAL:
        fail_rate = prov_failing / prov_classified
        descriptor = "NOT_PAYING" if fail_rate >= FT_PROV_FAIL_DOWNGRADE else "MIXED"
        basis = "provisional"
    else:
        descriptor = "UNKNOWN"
        basis = "insufficient"

    return {
        'descriptor':    descriptor,
        'basis':         basis,
        'delivery_rate': delivery,
        'baseline_rate': baseline,
        'delta_pp':      delta_pp,
    }
