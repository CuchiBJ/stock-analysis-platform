"""The leader filter and its diagnostic must agree on the 1% SMA separation."""
from types import SimpleNamespace

import pytest

from app.services.quality_leader_gate import (
    evaluate_minervini_criteria,
    is_quality_leader,
)


@pytest.mark.parametrize(
    "sma150, expected",
    [(99.0, False), (100.0, False), (100.5, False), (101.0, False),
     (101.01, True), (103.0, True), (106.0, True), (None, False)],
)
def test_sma_separation(sma150, expected):
    metrics = SimpleNamespace(
        perf_1y=50.0, ema200=100.0, current_price=200.0,
        sma50=150.0, sma150=sma150, sma200=100.0,
        low_52w=100.0, high_52w=210.0, adr_percent=5.0,
        distance_to_ema50_atr=1.0,
    )

    assert is_quality_leader(metrics) is expected
    criteria = evaluate_minervini_criteria(metrics)
    diagnostic = criteria['sma150_gt_sma200_x_101']
    assert diagnostic['passes'] is expected
    if sma150 is not None:
        assert diagnostic['threshold'] == 101.0


def test_missing_sma200_fails_filter_and_diagnostic():
    metrics = SimpleNamespace(
        perf_1y=50.0, ema200=100.0, current_price=200.0,
        sma50=150.0, sma150=103.0, sma200=None,
        low_52w=100.0, high_52w=210.0, adr_percent=5.0,
        distance_to_ema50_atr=1.0,
    )
    assert is_quality_leader(metrics) is False
    assert evaluate_minervini_criteria(metrics)['sma150_gt_sma200_x_101']['passes'] is False
