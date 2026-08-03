"""Pure orchestration tests for the empirical cohort fallback ladder."""
import asyncio
from datetime import date

import pytest

from app.services.empirical_probability_calculator import EmpiricalProbabilityCalculator


class FakeCalculator(EmpiricalProbabilityCalculator):
    def __init__(self, responses):
        super().__init__(db=None)
        self.responses = responses
        self.calls = []

    async def _query_cohort(
        self,
        transition_type,
        rs_bucket=None,
        regime=None,
        since=None,
        as_of_date=None,
    ):
        key = (rs_bucket, regime, since is not None)
        self.calls.append((transition_type, rs_bucket, regime, since, as_of_date))
        return self.responses.get(key, (0, 0, 0))


def run_lookup(calculator, **kwargs):
    EmpiricalProbabilityCalculator.clear_cache()
    return asyncio.run(calculator.lookup(**kwargs))


def test_prefers_recent_transition_regime_rs_at_twenty_settled():
    calc = FakeCalculator({("110_120", "risk_off", True): (10, 5, 5)})
    result = run_lookup(
        calc,
        transition_type="entering_pullback",
        rs_value=115,
        current_regime="risk_off",
        as_of_date=date(2026, 7, 27),
    )
    assert result.source == "empirical"
    assert result.basis == "transition_recent_regime_rs"
    assert result.sample_size == 20
    assert result.probability == pytest.approx(0.5)
    assert len(calc.calls) == 1


def test_falls_back_in_specificity_order():
    calc = FakeCalculator({
        ("110_120", "risk_on", True): (10, 5, 4),
        (None, None, True): (15, 10, 5),
    })
    result = run_lookup(
        calc,
        transition_type="reclaiming",
        rs_value=115,
        current_regime="risk_on",
        as_of_date=date(2026, 7, 27),
    )
    assert result.basis == "transition_recent"
    assert result.sample_size == 30
    assert [(call[1], call[2], call[3] is not None) for call in calc.calls] == [
        ("110_120", "risk_on", True),
        (None, None, True),
    ]


def test_global_cohort_requires_fifty_samples():
    calc = FakeCalculator({
        (None, None, False): (20, 20, 10),
    })
    result = run_lookup(
        calc,
        transition_type="continuation_holding",
        rs_value=105,
        current_regime="unknown",
    )
    assert result.source == "empirical"
    assert result.basis == "transition_all"
    assert result.sample_size == 50


def test_stable_transition_uses_rule_based_without_querying():
    calc = FakeCalculator({(None, None): (100, 0)})
    result = run_lookup(
        calc,
        transition_type="stable",
        rs_value=125,
        current_regime="risk_on",
    )
    assert result.source == "rule_based"
    assert result.basis == "rule_formula"
    assert calc.calls == []


def test_insufficient_ladder_uses_rule_based():
    calc = FakeCalculator({
        ("100_110", "choppy", False): (10, 5, 4),
        (None, "choppy", False): (15, 10, 4),
        ("100_110", None, False): (15, 10, 4),
        (None, None, False): (20, 20, 9),
    })
    result = run_lookup(
        calc,
        transition_type="breakout",
        rs_value=105,
        current_regime="choppy",
    )
    assert result.source == "rule_based"
    assert result.sample_size == 0
    assert result.basis == "rule_formula"
