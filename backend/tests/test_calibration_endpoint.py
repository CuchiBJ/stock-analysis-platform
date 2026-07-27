"""Unit tests for calibration endpoint helpers.

Full integration test against the endpoint requires an async DB fixture
that this repo doesn't have yet — tests target the pure logic surfaces
(`_classify`, status ordering, constants).
"""
import pytest

from app.api.v1.endpoints.calibration import (
    MIN_SAMPLES_REQUIRED,
    RESOLVED_STATUSES,
    PENDING_STATUSES,
    _STATUS_ORDER,
    _classify,
    _rates,
)
from app.services.transition_engine import OperationalTransition


class TestClassify:
    def test_empirical_above_threshold(self):
        assert _classify(MIN_SAMPLES_REQUIRED) == "empirical"
        assert _classify(MIN_SAMPLES_REQUIRED + 1) == "empirical"
        assert _classify(100) == "empirical"

    def test_insufficient_below_threshold(self):
        assert _classify(1) == "insufficient"
        assert _classify(MIN_SAMPLES_REQUIRED - 1) == "insufficient"

    def test_no_data_at_zero(self):
        assert _classify(0) == "no_data"


class TestRates:
    def test_non_empirical_returns_none(self):
        assert _rates(2, 1, 5, "insufficient") == (None, None)
        assert _rates(0, 0, 0, "no_data") == (None, None)

    def test_success_rate_excludes_neutral(self):
        # 8 success / (8+2) decisive = 0.8, regardless of neutrals.
        succ, _ = _rates(8, 2, 90, "empirical")
        assert succ == pytest.approx(0.8)

    def test_delivery_rate_counts_neutral_in_denominator(self):
        # 8 / (8+2+90) settled = 0.08.
        _, deliv = _rates(8, 2, 90, "empirical")
        assert deliv == pytest.approx(8 / 100)

    def test_delivery_never_exceeds_win_rate(self):
        succ, deliv = _rates(8, 2, 90, "empirical")
        assert deliv <= succ

    def test_real_reclaiming_case(self):
        # From live data: S881 / F682 / N449.
        succ, deliv = _rates(881, 682, 449, "empirical")
        assert succ == pytest.approx(881 / 1563, abs=1e-4)   # ~0.564 win rate
        assert deliv == pytest.approx(881 / 2012, abs=1e-4)  # ~0.438 delivered

    def test_no_neutral_collapses_to_equal(self):
        # When there are zero neutrals, the two rates coincide.
        succ, deliv = _rates(8, 2, 0, "empirical")
        assert succ == deliv


class TestConstants:
    def test_min_samples_is_five(self):
        assert MIN_SAMPLES_REQUIRED == 5

    def test_resolved_statuses(self):
        assert set(RESOLVED_STATUSES) == {"SUCCESS", "FAILURE"}

    def test_pending_statuses(self):
        assert set(PENDING_STATUSES) == {"PENDING", "INSUFFICIENT_DATA"}

    def test_status_order_priority(self):
        assert _STATUS_ORDER["empirical"] < _STATUS_ORDER["insufficient"]
        assert _STATUS_ORDER["insufficient"] < _STATUS_ORDER["no_data"]


class TestTransitionTypeCoverage:
    def test_stable_is_excluded_from_calibration_set(self):
        values = [
            t.value for t in OperationalTransition if t.value != "stable"
        ]
        assert "stable" not in values
        # Phase 1 enum: 12 non-STABLE transitions (including breakout)
        assert len(values) == 12

    def test_all_phase1_transition_types_present(self):
        values = {t.value for t in OperationalTransition if t.value != "stable"}
        expected = {
            "entering_pullback",
            "volume_dry_up",
            "compressing",
            "flush_and_recover",
            "support_holding",
            "breakout",
            "reclaiming",
            "continuation_holding",
            "weakening",
            "distribution",
            "failing",
            "stabilizing",
        }
        assert values == expected
