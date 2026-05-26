"""Unit tests for calibration endpoint helpers.

Full integration test against the endpoint requires an async DB fixture
that this repo doesn't have yet — tests target the pure logic surfaces
(`_classify`, status ordering, constants).
"""
from app.api.v1.endpoints.calibration import (
    MIN_SAMPLES_REQUIRED,
    RESOLVED_STATUSES,
    PENDING_STATUSES,
    _STATUS_ORDER,
    _classify,
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
        # Phase 1 enum: 11 non-STABLE transitions
        assert len(values) == 11

    def test_all_phase1_transition_types_present(self):
        values = {t.value for t in OperationalTransition if t.value != "stable"}
        expected = {
            "entering_pullback",
            "volume_dry_up",
            "compressing",
            "flush_and_recover",
            "support_holding",
            "reclaiming",
            "continuation_holding",
            "weakening",
            "distribution",
            "failing",
            "stabilizing",
        }
        assert values == expected
