"""Unit tests for symbol_diagnostic — verify per-list helpers pass/fail
correctly with synthetic metrics fixtures.
"""
from datetime import date, timedelta
from types import SimpleNamespace

from app.services.symbol_diagnostic import (
    diagnose_actionable,
    diagnose_live,
    diagnose_u_and_r,
    diagnose_emerging_leaders,
    diagnose_building_bases,
)


def _passing_metrics():
    """Synthetic StockMetrics-like that should pass actionable/live/quality_leader."""
    return SimpleNamespace(
        symbol="TEST",
        avg_volume_10d=2_000_000,
        adr_percent=5.0,
        current_price=100.0,
        perf_1y=50.0,
        ema9=99.0,
        ema21=98.0,
        ema50=95.0,
        ema200=80.0,
        sma50=96.0,
        sma150=88.0,
        sma200=80.0,
        distance_to_ema9=1.0,
        distance_to_ema9_atr=0.0,
        distance_to_ema21=2.0,
        distance_to_ema21_atr=0.2,
        distance_to_ema50=5.0,
        distance_to_ema50_atr=1.0,
        distance_to_high_52w_atr=-1.0,
        high_52w=110.0,
        low_52w=50.0,
        relative_strength_spy=120.0,
        relative_strength_qqq=115.0,
        pullback_quality_score=80.0,
        weeks_in_base=8,
        vcp_score=75.0,
        atr=2.0,
        atr_percent=2.0,
        volume_contraction=20.0,
        weekly_tightness=0.5,
        weekly_volatility_contraction=0.7,
        weekly_trend_quality=0.8,
        setup_quality=0.7,
        relative_volume=1.0,
        perf_1w=2.0,
        perf_4w=10.0,
        perf_13w=25.0,
        rsi=60.0,
    )


class TestActionable:
    def test_passes_with_good_metrics(self):
        check = diagnose_actionable(_passing_metrics())
        assert check.passes, f"expected pass; failing criteria: {[c.name for c in check.criteria if not c.passes]}"

    def test_fails_when_volume_short(self):
        m = _passing_metrics()
        m.avg_volume_10d = 500_000  # below 800k threshold
        check = diagnose_actionable(m)
        assert not check.passes
        # Find the failing criterion
        names = [c.name for c in check.criteria if not c.passes]
        assert any("800k" in n for n in names)

    def test_fails_when_ema_distance_too_far(self):
        m = _passing_metrics()
        m.distance_to_ema9_atr = 2.0   # outside [-1.0, +0.5]
        m.distance_to_ema21_atr = 1.5  # also outside
        check = diagnose_actionable(m)
        assert not check.passes


class TestLive:
    def test_passes_with_recent_obs(self):
        check = diagnose_live(_passing_metrics(), has_recent_non_stable_obs=True)
        assert check.passes

    def test_fails_without_recent_obs(self):
        check = diagnose_live(_passing_metrics(), has_recent_non_stable_obs=False)
        assert not check.passes


class TestUAndR:
    def test_passes_with_complete_setup(self):
        today = date.today()
        history = [
            # Day 5-10 ago has d21 > 0.5
            {"date": today - timedelta(days=8), "d21": 0.8, "d50": 1.5},
            {"date": today - timedelta(days=6), "d21": 0.6, "d50": 1.4},
            # d50 never negative anywhere
            {"date": today - timedelta(days=15), "d21": 0.3, "d50": 0.5},
        ]
        check = diagnose_u_and_r(_passing_metrics(), history, has_recent_2d_obs=True)
        assert check.passes, f"failing: {[c.name for c in check.criteria if not c.passes]}"

    def test_fails_when_never_above(self):
        today = date.today()
        history = [
            {"date": today - timedelta(days=8), "d21": 0.2, "d50": 1.5},  # never > 0.5
        ]
        check = diagnose_u_and_r(_passing_metrics(), history, has_recent_2d_obs=True)
        assert not check.passes

    def test_fails_when_broke_ema50(self):
        today = date.today()
        history = [
            {"date": today - timedelta(days=8), "d21": 0.8, "d50": -0.3},  # broke EMA50
        ]
        check = diagnose_u_and_r(_passing_metrics(), history, has_recent_2d_obs=True)
        assert not check.passes


class TestEmergingLeaders:
    def test_fails_when_already_minervini(self):
        # Passing metrics already passes is_quality_leader → emerging should FAIL
        check = diagnose_emerging_leaders(_passing_metrics())
        # Need NOT fully Minervini = fail
        not_minervini_crit = next(c for c in check.criteria if "NOT fully Minervini" in c.name)
        assert not not_minervini_crit.passes

    def test_passes_when_partial_minervini(self):
        m = _passing_metrics()
        m.perf_1y = 25.0  # below 30 threshold → not fully Minervini
        check = diagnose_emerging_leaders(m)
        # Now should pass NOT-fully-Minervini check; rest still good
        assert check.passes, f"failing: {[c.name for c in check.criteria if not c.passes]}"


class TestBuildingBases:
    def test_passes_with_tight_consolidation(self):
        # ATR oscillation: 12 points all within range
        d21_history = [0.3, 0.4, 0.2, 0.1, 0.3, 0.4, 0.5, 0.2, 0.3, 0.1, 0.4, 0.3]
        check = diagnose_building_bases(_passing_metrics(), d21_history)
        assert check.passes, f"failing: {[c.name for c in check.criteria if not c.passes]}"

    def test_fails_when_oscillation_too_wide(self):
        d21_history = [2.5, -0.5, 2.0, -1.0, 1.5, -0.8, 2.0, 0.0, 1.5, 0.5]  # range > 2.0
        check = diagnose_building_bases(_passing_metrics(), d21_history)
        assert not check.passes

    def test_fails_without_enough_history(self):
        d21_history = [0.3, 0.4, 0.2]  # < 10 points
        check = diagnose_building_bases(_passing_metrics(), d21_history)
        assert not check.passes
