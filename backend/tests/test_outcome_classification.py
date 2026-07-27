"""Unit tests for OutcomeTracker._classify_outcome.

Targets the PRE_RECLAIM rule, which defines SUCCESS as a real forward
advance (>=1.5 ATR) rather than merely touching the EMA — see
`backend/app/services/outcome_tracker.py`.
"""
from types import SimpleNamespace

from app.services.outcome_tracker import OutcomeTracker


def _obs(**kwargs):
    """Minimal observation stub with the fields _classify_outcome reads."""
    defaults = dict(
        transition_type="entering_pullback",
        max_drawdown_atr_within_10d=None,
        max_gain_atr_within_10d=None,
        pct_5d=None,
        broke_ema50_within_10d=False,
        max_drawdown_within_10d=None,
        max_gain_within_10d=None,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# _classify_outcome doesn't touch self/db, so a bare instance is fine.
tracker = OutcomeTracker(db=None)


class TestPreReclaimClassification:
    def test_good_advance_is_success(self):
        obs = _obs(max_gain_atr_within_10d=1.5, max_drawdown_atr_within_10d=-1.0)
        assert tracker._classify_outcome(obs) == "SUCCESS"

    def test_insufficient_advance_is_neutral(self):
        obs = _obs(max_gain_atr_within_10d=1.0, max_drawdown_atr_within_10d=-1.0)
        assert tracker._classify_outcome(obs) == "NEUTRAL"

    def test_no_gain_data_is_neutral(self):
        # atr==0 at detection => max_gain_atr is None => cannot confirm advance.
        obs = _obs(max_gain_atr_within_10d=None, max_drawdown_atr_within_10d=-1.0)
        assert tracker._classify_outcome(obs) == "NEUTRAL"

    def test_broke_ema50_is_failure(self):
        obs = _obs(max_gain_atr_within_10d=2.0, broke_ema50_within_10d=True)
        assert tracker._classify_outcome(obs) == "FAILURE"

    def test_deep_drawdown_is_failure(self):
        obs = _obs(max_gain_atr_within_10d=2.0, max_drawdown_atr_within_10d=-3.5)
        assert tracker._classify_outcome(obs) == "FAILURE"

    def test_shakeout_drawdown_is_neutral(self):
        # +2 ATR advance but a -2.8 ATR drawdown: too shaken for a clean
        # success, yet structure (EMA50) held => no-man's-land => NEUTRAL.
        obs = _obs(max_gain_atr_within_10d=2.0, max_drawdown_atr_within_10d=-2.8)
        assert tracker._classify_outcome(obs) == "NEUTRAL"

    def test_advance_with_borderline_drawdown_is_success(self):
        obs = _obs(max_gain_atr_within_10d=1.6, max_drawdown_atr_within_10d=-2.4)
        assert tracker._classify_outcome(obs) == "SUCCESS"

    def test_rule_applies_to_whole_pre_reclaim_group(self):
        for t in ("volume_dry_up", "compressing", "flush_and_recover", "support_holding"):
            obs = _obs(transition_type=t, max_gain_atr_within_10d=1.5,
                       max_drawdown_atr_within_10d=-1.0)
            assert tracker._classify_outcome(obs) == "SUCCESS", t
