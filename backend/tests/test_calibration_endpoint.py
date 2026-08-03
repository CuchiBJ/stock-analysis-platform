"""Unit tests for calibration endpoint helpers.

Full integration test against the endpoint requires an async DB fixture
that this repo doesn't have yet — tests target the pure logic surfaces
(`_classify`, status ordering, constants).
"""
import pytest
import asyncio
from datetime import date
from types import SimpleNamespace

from app.api.v1.endpoints.calibration import (
    MIN_SAMPLES_REQUIRED,
    RESOLVED_STATUSES,
    PENDING_STATUSES,
    _STATUS_ORDER,
    _classify,
    _rates,
    _reclassify_observation_regimes,
)
from app.services.transition_engine import OperationalTransition
from app.services.calibration_statistics import (
    classify_drift,
    cohort_statistics,
    wilson_interval,
)


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
    def test_min_samples_is_conservative(self):
        assert MIN_SAMPLES_REQUIRED == 20

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


class TestContextAwareCohorts:
    def test_settled_threshold_includes_neutral(self):
        cohort = cohort_statistics(success=8, failure=2, neutral=10, pending=3)
        assert cohort["status"] == "empirical"
        assert cohort["n_settled"] == 20
        assert cohort["n_resolved"] == 10
        assert cohort["delivery_rate"] == pytest.approx(0.4)
        assert cohort["success_rate"] == pytest.approx(0.8)
        assert cohort["n_pending"] == 3

    def test_insufficient_cohort_hides_rates(self):
        cohort = cohort_statistics(success=10, failure=5, neutral=4)
        assert cohort["status"] == "insufficient"
        assert cohort["samples_needed"] == 1
        assert cohort["delivery_rate"] is None
        assert cohort["confidence_interval"] is None

    def test_wilson_interval_contains_observed_rate(self):
        low, high = wilson_interval(30, 100)
        assert low < 0.30 < high
        assert 0 <= low <= high <= 1

    def test_drift_requires_non_overlapping_intervals(self):
        historical = cohort_statistics(success=60, failure=20, neutral=20)
        deteriorating = cohort_statistics(success=10, failure=50, neutral=40)
        improving = cohort_statistics(success=90, failure=5, neutral=5)
        overlapping = cohort_statistics(success=55, failure=25, neutral=20)

        assert classify_drift(historical, deteriorating) == "deteriorating"
        assert classify_drift(historical, improving) == "improving"
        assert classify_drift(historical, overlapping) == "stable"

    def test_drift_is_insufficient_without_both_cohorts(self):
        empirical = cohort_statistics(success=15, failure=5, neutral=0)
        insufficient = cohort_statistics(success=3, failure=2, neutral=0)
        assert classify_drift(empirical, insufficient) == "insufficient"


class _RowsResult:
    def __init__(self, rows=None, rowcount=0):
        self._rows = rows or []
        self.rowcount = rowcount

    def all(self):
        return self._rows


class _ReclassifyDb:
    def __init__(self):
        self.results = [
            _RowsResult([
                SimpleNamespace(date_detected=date(2026, 7, 24), cnt=10),
                SimpleNamespace(date_detected=date(2026, 7, 25), cnt=5),
            ]),
            _RowsResult(rowcount=7),
            _RowsResult(rowcount=3),
        ]
        self.committed = False

    async def execute(self, _statement):
        return self.results.pop(0)

    async def commit(self):
        self.committed = True


class _ReclassifyEngine:
    def __init__(self, _db):
        pass

    async def detect_regime(self, target):
        value = "risk_off" if target.day == 24 else "transition"
        return SimpleNamespace(
            as_of=target,
            regime=SimpleNamespace(value=value),
        )


def test_regime_reclassification_groups_dates_and_counts_changes():
    db = _ReclassifyDb()
    result = asyncio.run(
        _reclassify_observation_regimes(db, engine_factory=_ReclassifyEngine)
    )
    assert result == {
        "evaluated": 15,
        "changed": 10,
        "dates_evaluated": 2,
        "by_regime": {"risk_off": 10, "transition": 5},
        "unresolved_dates": [],
    }
    assert db.committed is True
