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
    """Membership gate: quality universe + Minervini leader + weeks_in_base ≥ 6.
    (Ranking by VCP-quality is endpoint-side, not a pass/fail criterion here.)"""

    def test_passes_with_quality_base(self):
        # Quality leader, 8 weeks in base, passes the liquidity universe
        check = diagnose_building_bases(_passing_metrics())
        assert check.passes, f"failing: {[c.name for c in check.criteria if not c.passes]}"

    def test_fails_when_base_too_short(self):
        m = _passing_metrics()
        m.weeks_in_base = 4  # below the 6-week minimum
        check = diagnose_building_bases(m)
        assert not check.passes
        names = [c.name for c in check.criteria if not c.passes]
        assert any("weeks_in_base" in n for n in names)

    def test_fails_when_not_quality_leader(self):
        m = _passing_metrics()
        m.perf_1y = 25.0  # breaks a Minervini SEPA criterion → not a leader
        check = diagnose_building_bases(m)
        assert not check.passes
        names = [c.name for c in check.criteria if not c.passes]
        assert any("Minervini" in n for n in names)


# ─── Benchmark handling ──────────────────────────────────────────────────────

from app.services.benchmarks import is_benchmark, BENCHMARK_SYMBOLS
from app.api.v1.endpoints.stocks import _build_benchmark_assessment


def _spy_like_metrics():
    """SPY-like: low ADR, perf_1y below 30% — would be branded 'roto' by the
    leader gate, but is a benchmark and must NOT be."""
    return SimpleNamespace(
        symbol="SPY",
        current_price=520.0,
        ema50=510.0,
        ema200=480.0,
        sma150=495.0,
        sma200=475.0,
        perf_1y=12.0,
        perf_13w=5.0,
        adr_percent=1.1,
    )


class TestIsBenchmark:
    def test_known_benchmarks(self):
        for s in ("SPY", "QQQ", "IWM", "DIA"):
            assert is_benchmark(s)
            assert s in BENCHMARK_SYMBOLS

    def test_case_insensitive(self):
        assert is_benchmark("spy")
        assert is_benchmark("Qqq")

    def test_non_benchmark(self):
        assert not is_benchmark("AAPL")
        assert not is_benchmark(None)
        assert not is_benchmark("")


class TestBenchmarkAssessment:
    def test_verdict_is_benchmark_not_roto(self):
        stock = SimpleNamespace(symbol="SPY", name="SPDR S&P 500", market_group="ETF")
        assessment, ctx = _build_benchmark_assessment(stock, _spy_like_metrics())
        assert assessment["verdict"] == "benchmark"
        assert "roto" not in assessment["headline"].lower()
        assert "Setup roto" not in assessment["headline"]
        # No blocker-severity gaps for a healthy uptrending benchmark
        assert all(g["severity"] != "blocker" for g in assessment["gaps"])

    def test_trend_alcista_when_above_mas(self):
        stock = SimpleNamespace(symbol="SPY", name="SPDR S&P 500", market_group="ETF")
        _, ctx = _build_benchmark_assessment(stock, _spy_like_metrics())
        assert ctx["trend"] == "alcista"

    def test_trend_bajista_when_below_ema200(self):
        m = _spy_like_metrics()
        m.current_price = 450.0   # below EMA200=480
        m.sma150 = 470.0          # SMA150 < SMA200=475
        stock = SimpleNamespace(symbol="SPY", name="SPDR S&P 500", market_group="ETF")
        assessment, ctx = _build_benchmark_assessment(stock, m)
        assert ctx["trend"] == "bajista"
        assert "roto" not in assessment["headline"].lower()


from app.services.benchmarks import compute_index_trend


class TestComputeIndexTrend:
    def test_alcista(self):
        # price above EMA50/EMA200, SMA150 > SMA200
        assert compute_index_trend(728.0, 724.0, 683.0, 691.0, 683.0) == "alcista"

    def test_bajista(self):
        # price below EMA200, SMA150 < SMA200
        assert compute_index_trend(450.0, 470.0, 480.0, 470.0, 475.0) == "bajista"

    def test_lateral_mixed(self):
        # above EMA200 but below EMA50 → neither alcista nor bajista
        assert compute_index_trend(485.0, 490.0, 480.0, 485.0, 478.0) == "lateral"

    def test_lateral_on_missing_inputs(self):
        assert compute_index_trend(None, 724.0, 683.0, 691.0, 683.0) == "lateral"
