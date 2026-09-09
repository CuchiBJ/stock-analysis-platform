"""Focused tests for explicit posture thresholds and hysteresis."""
from app.services.market_posture_policy import (
    POSTURE_THRESHOLDS,
    classify_policy_session,
    evaluate_policy_history,
)


def _day(
    *,
    breadth=0.65,
    density=0.12,
    participation="STABLE",
    leadership="HEALTHY",
    bullish=True,
    above_ema200=True,
    new_high=False,
    severity="clean",
    exceptional=False,
):
    return {
        "index_bullish": bullish,
        "index_above_ema200": above_ema200,
        "index_new_high": new_high,
        "breadth_ratio": breadth,
        "leader_density": density,
        "participation": participation,
        "leadership": leadership,
        "severity": severity,
        "exceptional_recovery": exceptional,
    }


class TestThresholdBands:
    def test_defensive_entry_and_buffered_exit(self):
        t = POSTURE_THRESHOLDS
        below = classify_policy_session(**{
            "index_bullish": True,
            "index_above_ema200": True,
            "index_new_high": False,
            "breadth_ratio": t.defensive_breadth_entry - 0.001,
            "participation": "STABLE",
            "leader_density": 0.10,
            "leadership": "HEALTHY",
            "severity": "clean",
        })
        assert below["defensive_entry"] is True
        assert below["defensive_exit"] is False

        buffer = classify_policy_session(**{
            "index_bullish": True,
            "index_above_ema200": True,
            "index_new_high": False,
            "breadth_ratio": 0.42,
            "participation": "STABLE",
            "leader_density": 0.055,
            "leadership": "HEALTHY",
            "severity": "clean",
        })
        assert buffer["defensive_entry"] is False
        assert buffer["defensive_exit"] is False

        recovered = classify_policy_session(**{
            "index_bullish": True,
            "index_above_ema200": True,
            "index_new_high": False,
            "breadth_ratio": t.defensive_breadth_exit,
            "participation": "STABLE",
            "leader_density": t.defensive_leader_density_exit,
            "leadership": "HEALTHY",
            "severity": "clean",
        })
        assert recovered["defensive_exit"] is True

    def test_defensive_state_holds_until_buffered_exit(self):
        evidence = evaluate_policy_history([
            _day(breadth=0.39, density=0.08),
            _day(breadth=0.41, density=0.055),
        ])
        assert evidence["defensive_active"] is True
        evidence = evaluate_policy_history([
            _day(breadth=0.39, density=0.08),
            _day(breadth=0.44, density=0.07),
        ])
        assert evidence["defensive_active"] is False

    def test_severe_anatomy_overrides_strong_levels(self):
        signals = classify_policy_session(**{
            "index_bullish": True,
            "index_above_ema200": True,
            "index_new_high": True,
            "breadth_ratio": 0.80,
            "participation": "EXPANDING",
            "leader_density": 0.20,
            "leadership": "EXHAUSTED",
            "severity": "severe",
        })
        assert signals["defensive_entry"] is True
        assert signals["normal_entry"] is False
        assert signals["aggressive_entry"] is False


class TestNormalHysteresis:
    def test_three_entry_sessions_activate_normal(self):
        evidence = evaluate_policy_history([_day(), _day(), _day()])
        assert evidence["normal_confirmation_streak"] == 3
        assert evidence["normal_active"] is True

    def test_normal_holds_inside_exit_band_then_exits_below_it(self):
        days = [_day(), _day(), _day(), _day(breadth=0.56, density=0.09)]
        assert evaluate_policy_history(days)["normal_active"] is True
        days.append(_day(breadth=0.54, density=0.09))
        assert evaluate_policy_history(days)["normal_active"] is False

    def test_missing_bullish_entry_never_activates_normal(self):
        evidence = evaluate_policy_history([
            _day(bullish=False), _day(bullish=False), _day(bullish=False)
        ])
        assert evidence["normal_active"] is False


class TestAggressiveHysteresis:
    def test_aggressive_requires_sustained_normal_then_strong_new_high(self):
        evidence = evaluate_policy_history([
            _day(),
            _day(),
            _day(
                breadth=0.75,
                density=0.18,
                participation="EXPANDING",
                leadership="EXPANDING",
                new_high=True,
            ),
        ])
        assert evidence["normal_active"] is True
        assert evidence["aggressive_active"] is True

    def test_aggressive_holds_exit_band_without_requiring_daily_new_high(self):
        days = [
            _day(),
            _day(),
            _day(
                breadth=0.75,
                density=0.18,
                participation="EXPANDING",
                leadership="EXPANDING",
                new_high=True,
            ),
            _day(breadth=0.66, density=0.13),
        ]
        assert evaluate_policy_history(days)["aggressive_active"] is True
        days.append(_day(breadth=0.64, density=0.13))
        evidence = evaluate_policy_history(days)
        assert evidence["aggressive_active"] is False
        assert evidence["normal_active"] is True


class TestExceptionalRetention:
    def test_exceptional_selective_retention_is_bounded_to_two_following_sessions(self):
        days = [
            _day(breadth=0.68, density=0.13, exceptional=True),
            _day(breadth=0.62, density=0.11),
            _day(breadth=0.58, density=0.09),
        ]
        evidence = evaluate_policy_history(days)
        assert evidence["exceptional_retained"] is True
        assert evidence["exceptional_retention_age"] == 2
        days.append(_day(breadth=0.58, density=0.09))
        assert evaluate_policy_history(days)["exceptional_retained"] is False

    def test_severe_day_immediately_cancels_exceptional_retention(self):
        evidence = evaluate_policy_history([
            _day(exceptional=True),
            _day(participation="COLLAPSING", severity="severe"),
        ])
        assert evidence["exceptional_retained"] is False
