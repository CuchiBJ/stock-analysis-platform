"""Regression contracts retained from the retired actionable ranking."""

from types import SimpleNamespace

from sqlalchemy.dialects import postgresql

# Register destination auth models before SQLAlchemy configures the shared
# mapper registry while compiling expressions containing the Stock ORM class.
import app.models.user  # noqa: F401

from app.services.live_transition_service import LIVE_INSTITUTIONAL_FILTERS, passes_breakout_trigger
from app.services.actionable_ranking import calculate_relative_strength_pullback_score


def _compiled(expression) -> str:
    return str(expression.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


class TestEligibilityScope:
    def test_live_institutional_filter_retains_52w_high_distance_gate(self):
        compiled = " ".join(_compiled(expression) for expression in LIVE_INSTITUTIONAL_FILTERS)
        assert "distance_to_high_52w_atr >= -3.0" in compiled

    def test_breakout_trigger_remains_strictly_near_high(self):
        near = SimpleNamespace(distance_to_ema21_atr=1.0, distance_to_high_52w_atr=-1.0)
        far = SimpleNamespace(distance_to_ema21_atr=1.0, distance_to_high_52w_atr=-1.01)

        assert passes_breakout_trigger(near)
        assert not passes_breakout_trigger(far)


class TestRelativeStrengthDuringPullback:
    def test_improving_rs_is_rewarded(self):
        score, detail = calculate_relative_strength_pullback_score(108.0, 104.0)

        assert score == 88.0
        assert detail["status"] == "improving"
        assert detail["trend_score"] == 100.0

    def test_stable_rs_receives_stable_score(self):
        score, detail = calculate_relative_strength_pullback_score(106.0, 106.0)

        assert score == 72.0
        assert detail["status"] == "stable"
        assert detail["trend_score"] == 60.0

    def test_deteriorating_rs_is_penalized(self):
        score, detail = calculate_relative_strength_pullback_score(98.0, 106.0)

        assert score == 24.0
        assert detail["status"] == "deteriorating"
        assert detail["trend_score"] == 0.0

    def test_missing_history_is_neutral_and_explainable(self):
        score, detail = calculate_relative_strength_pullback_score(108.0, None)

        assert score == 50.0
        assert detail["status"] == "missing_history_neutral"
        assert detail["rs_delta_pct"] is None
