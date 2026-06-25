"""Unit tests for the `breakout` operational transition.

Covers detection (coiling near highs + volume compression on a SEPA leader)
and the breakout quality score. Pure-function tests — no DB required.
"""
from types import SimpleNamespace

from app.services.transition_engine import TransitionEngine, OperationalTransition
from app.services.observation_scorer import score_breakout_quality


def _quality_leader(**overrides):
    """A synthetic StockMetrics that passes the 8 Minervini SEPA criteria,
    positioned above EMA21 near its 52w high. Override fields per test.
    """
    m = SimpleNamespace(
        # Minervini gate
        perf_1y=50.0, ema200=100.0, current_price=200.0,
        sma50=150.0, sma150=130.0, sma200=120.0,
        low_52w=100.0, high_52w=180.0, adr_percent=5.0,
        distance_to_ema50_atr=1.0,
        # Positioning
        distance_to_ema9_atr=2.0,
        distance_to_ema21_atr=1.5,
        distance_to_high_52w_atr=-0.5,
        relative_volume=0.7,
        relative_strength_spy=110.0,
        # Base / volatility
        weekly_tightness=0.5,
        weekly_trend_quality=0.8,
        weeks_in_base=6,
        volume_contraction=0.5,
        vcp_score=70.0,
    )
    for k, v in overrides.items():
        setattr(m, k, v)
    return m


class TestBreakoutDetection:
    def _detect(self, metrics, volume_change_pct):
        engine = TransitionEngine(None)  # db unused by this method
        return engine._determine_operational_transition(
            rs_change=0.0,
            volume_change_pct=volume_change_pct,
            structure_change=0.1,
            ema21_distance_change=0.05,
            current_metrics=metrics,
            prev_ema21_atr=1.4,
            ema9_distance_change=0.0,
        )

    def test_coiling_near_highs_with_dry_volume_is_breakout(self):
        m = _quality_leader()
        assert self._detect(m, volume_change_pct=-10.0) == OperationalTransition.BREAKOUT

    def test_overextended_above_ema21_is_not_breakout(self):
        # Lejos por encima de la EMA21 = extendido, no coiling.
        m = _quality_leader(distance_to_ema21_atr=3.0)
        assert self._detect(m, volume_change_pct=-10.0) != OperationalTransition.BREAKOUT

    def test_volume_not_contracting_is_not_breakout(self):
        # volume_contraction <= 0 → el volumen no se seca de verdad (p.ej. spike
        # reciente contamina la ventana de 3 días).
        m = _quality_leader(volume_contraction=-1.0)
        assert self._detect(m, volume_change_pct=-10.0) != OperationalTransition.BREAKOUT

    def test_volume_expansion_today_is_not_breakout(self):
        m = _quality_leader(relative_volume=1.5)
        assert self._detect(m, volume_change_pct=-10.0) != OperationalTransition.BREAKOUT

    def test_far_from_high_is_not_breakout(self):
        m = _quality_leader(distance_to_high_52w_atr=-3.0)
        assert self._detect(m, volume_change_pct=-10.0) != OperationalTransition.BREAKOUT

    def test_loose_base_is_not_breakout(self):
        m = _quality_leader(weekly_tightness=0.2)
        assert self._detect(m, volume_change_pct=-10.0) != OperationalTransition.BREAKOUT

    def test_non_leader_is_not_breakout(self):
        m = _quality_leader(perf_1y=5.0)  # fails Minervini perf gate
        assert self._detect(m, volume_change_pct=-10.0) != OperationalTransition.BREAKOUT


class TestBreakoutQualityScore:
    def test_tight_near_highs_scores_high(self):
        m = _quality_leader()
        assert score_breakout_quality(m) >= 70

    def test_loose_far_scores_low(self):
        m = _quality_leader(
            distance_to_high_52w_atr=-3.0, weekly_tightness=0.1,
            relative_volume=1.3, volume_contraction=0.0,
            weekly_trend_quality=0.2, weeks_in_base=1, vcp_score=10.0,
        )
        loose = score_breakout_quality(m)
        tight = score_breakout_quality(_quality_leader())
        assert loose < tight
        assert loose < 40
