"""Unit tests for the follow-through engine's pure logic (no DB).

Covers the provisional early-read classifier and the two-layer descriptor:
confirmed outcomes decide, provisional evidence only downgrades, and the
posture ceiling caps aggression when the market stops paying.
"""
from app.services.follow_through import (
    classify_follow_through,
    classify_provisional,
)
from app.services.market_posture import compute_posture


class TestClassifyProvisional:
    def test_atr_normalized_failing(self):
        # -6% on a $100 stock with $3 ATR = -2 ATR → failing.
        assert classify_provisional(-6.0, 100.0, 3.0) == 'failing'

    def test_atr_normalized_on_track(self):
        # +4% on a $100 stock with $3 ATR = +1.33 ATR → on track.
        assert classify_provisional(4.0, 100.0, 3.0) == 'on_track'

    def test_atr_normalization_scales_with_volatility(self):
        # Same -4% move: break on a tight name ($1.5 ATR → -2.7 ATR)...
        assert classify_provisional(-4.0, 100.0, 1.5) == 'failing'
        # ...noise on a volatile one ($6 ATR → -0.67 ATR).
        assert classify_provisional(-4.0, 100.0, 6.0) is None

    def test_ambiguous_zone_is_none(self):
        assert classify_provisional(0.5, 100.0, 3.0) is None

    def test_pct_fallback_without_atr(self):
        assert classify_provisional(-6.0, 100.0, None) == 'failing'
        assert classify_provisional(5.0, None, None) == 'on_track'
        assert classify_provisional(1.0, None, None) is None

    def test_no_pct5d_yet_is_none(self):
        assert classify_provisional(None, 100.0, 3.0) is None


def _ft(**kw):
    defaults = dict(
        success=0, failure=0, neutral=0,
        baseline_success=0, baseline_failure=0, baseline_neutral=0,
        prov_on_track=0, prov_failing=0,
    )
    defaults.update(kw)
    return classify_follow_through(**defaults)


class TestClassifyFollowThrough:
    def test_paying_vs_baseline(self):
        # Window delivery 60% vs baseline 45% → +15pp → PAYING.
        v = _ft(success=12, failure=5, neutral=3,
                baseline_success=45, baseline_failure=35, baseline_neutral=20)
        assert v['descriptor'] == "PAYING"
        assert v['basis'] == "baseline"
        assert abs(v['delta_pp'] - 15.0) < 1e-9

    def test_not_paying_vs_baseline(self):
        # Window delivery 20% vs baseline 45% → -25pp → NOT_PAYING.
        v = _ft(success=4, failure=12, neutral=4,
                baseline_success=45, baseline_failure=35, baseline_neutral=20)
        assert v['descriptor'] == "NOT_PAYING"

    def test_mixed_in_the_band(self):
        # 45% vs 45% → 0pp → MIXED.
        v = _ft(success=9, failure=7, neutral=4,
                baseline_success=45, baseline_failure=35, baseline_neutral=20)
        assert v['descriptor'] == "MIXED"

    def test_neutrals_count_against_delivery(self):
        # 10 SUCCESS + 10 NEUTRAL = 50% delivery, not 100% win rate.
        v = _ft(success=10, failure=0, neutral=10,
                baseline_success=45, baseline_failure=35, baseline_neutral=20)
        assert v['delivery_rate'] == 0.5

    def test_absolute_fallback_when_baseline_thin(self):
        # Only 10 baseline observations (< 30) → absolute thresholds.
        v = _ft(success=10, failure=5, neutral=5,
                baseline_success=5, baseline_failure=3, baseline_neutral=2)
        assert v['basis'] == "absolute"
        assert v['descriptor'] == "PAYING"  # 50% >= 45%

    def test_provisional_downgrades_paying_to_mixed(self):
        # Confirmed says PAYING, but 4 of 6 fresh signals are dying.
        v = _ft(success=12, failure=5, neutral=3,
                baseline_success=45, baseline_failure=35, baseline_neutral=20,
                prov_on_track=2, prov_failing=4)
        assert v['descriptor'] == "MIXED"
        assert "provisional_downgrade" in v['basis']

    def test_provisional_downgrades_mixed_to_not_paying(self):
        v = _ft(success=9, failure=7, neutral=4,
                baseline_success=45, baseline_failure=35, baseline_neutral=20,
                prov_on_track=1, prov_failing=5)
        assert v['descriptor'] == "NOT_PAYING"

    def test_provisional_never_upgrades(self):
        # Confirmed NOT_PAYING + fresh signals all rising → still NOT_PAYING.
        v = _ft(success=4, failure=12, neutral=4,
                baseline_success=45, baseline_failure=35, baseline_neutral=20,
                prov_on_track=8, prov_failing=0)
        assert v['descriptor'] == "NOT_PAYING"

    def test_provisional_below_min_sample_never_downgrades(self):
        # 2+2=4 classified (< 5) → confirmed verdict stands.
        v = _ft(success=12, failure=5, neutral=3,
                baseline_success=45, baseline_failure=35, baseline_neutral=20,
                prov_on_track=2, prov_failing=2)
        assert v['descriptor'] == "PAYING"

    def test_provisional_alone_warns_but_never_certifies_paying(self):
        # No confirmed sample; fresh signals mostly failing → NOT_PAYING.
        v = _ft(prov_on_track=1, prov_failing=6)
        assert v['descriptor'] == "NOT_PAYING"
        assert v['basis'] == "provisional"
        # Fresh signals mostly rising → only MIXED, never PAYING.
        v = _ft(prov_on_track=6, prov_failing=1)
        assert v['descriptor'] == "MIXED"

    def test_insufficient_everything_is_unknown(self):
        v = _ft(success=2, failure=1, prov_on_track=1, prov_failing=1)
        assert v['descriptor'] == "UNKNOWN"
        assert v['basis'] == "insufficient"


class TestPostureFollowThroughCeiling:
    def test_not_paying_caps_a_perfect_day_at_selectivo(self):
        # Anatomy perfect (EXPANDING×EXPANDING, ROBUST) but market not paying.
        v = compute_posture(
            "EXPANDING", "EXPANDING", "ROBUST",
            follow_through="NOT_PAYING", ft_delivery=0.21, ft_baseline=0.45,
        )
        assert v.state == "SELECTIVO"
        assert any("no está pagando" in r for r in v.reasons)
        assert any("21%" in r and "45%" in r for r in v.reasons)

    def test_not_paying_does_not_raise_defensive_states(self):
        v = compute_posture(
            "COLLAPSING", "THINNING", "ROBUST", follow_through="NOT_PAYING",
        )
        assert v.state == "DEFENSIVO"

    def test_paying_never_boosts(self):
        # PAYING is not a boost: STABLE×HEALTHY stays NORMAL.
        v = compute_posture(
            "STABLE", "HEALTHY", "ROBUST",
            follow_through="PAYING", ft_delivery=0.60,
        )
        assert v.state == "NORMAL"

    def test_unknown_follow_through_is_never_suppressive(self):
        v = compute_posture("EXPANDING", "EXPANDING", "ROBUST", follow_through="UNKNOWN")
        assert v.state == "AGRESIVO"

    def test_ft_cap_stacks_with_health_cap(self):
        # RECOVERING caps at NORMAL; NOT_PAYING caps further at SELECTIVO.
        v = compute_posture(
            "EXPANDING", "EXPANDING", "RECOVERING", follow_through="NOT_PAYING",
        )
        assert v.state == "SELECTIVO"
