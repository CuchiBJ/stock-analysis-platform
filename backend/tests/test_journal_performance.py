"""Pure journal outcome and economic-metric tests (no database required)."""

from __future__ import annotations

from datetime import date

import pytest

from app.api.v1.endpoints.journal import (
    _aggregate,
    _classify_resolved_decision,
    _decision_economic_metrics,
    _decision_result_detail,
    _decision_runner_breakeven_id,
    _decision_weighted_r,
    _performance_trades,
)
from app.models.stock import JournalTrade


def _trade(
    trade_id: int,
    pnl: float,
    *,
    parent_trade_id: int | None = None,
    is_open: bool = False,
    entry_price: float = 100.0,
    exit_price: float = 101.0,
    exit_date: date = date(2026, 8, 5),
    r_multiple: float | None = None,
    exit_reason: str = "unknown",
) -> JournalTrade:
    return JournalTrade(
        id=trade_id,
        symbol="AAPL",
        setup="breakout",
        context="unknown",
        entry_date=date(2026, 8, 1),
        entry_price=entry_price,
        qty=10.0,
        exit_date=None if is_open else exit_date,
        exit_price=None if is_open else exit_price,
        pnl_dollars=None if is_open else pnl,
        r_multiple=r_multiple,
        exit_reason=exit_reason,
        parent_trade_id=parent_trade_id,
        source_row=trade_id,
    )


def test_decision_outcome_uses_be_band_and_requires_full_resolution():
    assert _classify_resolved_decision([_trade(1, 0.75)]) == "breakeven"
    assert _classify_resolved_decision([_trade(2, 20.0)]) == "win"
    assert _classify_resolved_decision([_trade(3, -20.0)]) == "loss"
    assert _classify_resolved_decision([_trade(4, 20.0), _trade(5, 0, is_open=True)]) is None


@pytest.mark.parametrize(
    ("r_multiple", "pnl"),
    [(0.017, -1.85), (-0.021, -2.32), (0.09, 20.0), (-0.09, -20.0)],
)
def test_near_zero_r_takes_priority_as_break_even(r_multiple: float, pnl: float):
    trade = _trade(8, pnl, r_multiple=r_multiple)

    assert _classify_resolved_decision([trade]) == "breakeven"
    aggregate = _aggregate([trade])
    assert aggregate["wins"] == 0
    assert aggregate["losses"] == 0
    assert aggregate["breakeven"] == 1


def test_results_outside_r_band_keep_existing_pnl_classification():
    assert _classify_resolved_decision([_trade(8, 20.0, r_multiple=0.101)]) == "win"
    assert _classify_resolved_decision([_trade(9, -20.0, r_multiple=-0.101)]) == "loss"


def test_dca_trades_are_excluded_from_the_performance_population():
    tactical = _trade(12, 20.0)
    dca = _trade(13, 50.0)
    dca.setup = "dca"

    assert _performance_trades([tactical, dca]) == [tactical]


def test_decision_outcome_keeps_a_profitable_partial_as_a_win():
    legs = [
        _trade(10, 20.0),
        _trade(11, -20.0, parent_trade_id=10),
    ]
    assert _classify_resolved_decision(legs) == "win"


def test_profitable_partial_with_exact_entry_price_runner_stays_a_win():
    legs = [
        _trade(
            10,
            0.02,
            exit_price=100.0,
            exit_date=date(2026, 8, 5),
            r_multiple=0.0,
        ),
        _trade(
            11,
            0.03,
            parent_trade_id=10,
            exit_price=110.0,
            exit_date=date(2026, 8, 2),
            r_multiple=1.0,
            exit_reason="partial_take",
        ),
    ]

    # Net P&L is deliberately inside the normal BE band. The exact runner-at-
    # entry pattern and positive total R preserve the economic win.
    assert _decision_weighted_r(legs) == pytest.approx(0.5)
    assert _classify_resolved_decision(legs) == "win"
    assert _decision_result_detail(legs) == "runner_breakeven"
    assert _decision_runner_breakeven_id(legs) == 10


def test_runner_be_detail_requires_exact_and_unambiguous_exit_data():
    almost_be = [
        _trade(20, 4.0, exit_price=100.01, exit_date=date(2026, 8, 5)),
        _trade(21, 20.0, parent_trade_id=20, exit_price=110.0, exit_date=date(2026, 8, 2)),
    ]
    same_day_without_explicit_partial = [
        _trade(30, 4.0, exit_price=100.0, exit_date=date(2026, 8, 5)),
        _trade(31, 20.0, parent_trade_id=30, exit_price=110.0, exit_date=date(2026, 8, 5)),
    ]

    assert _decision_result_detail(almost_be) is None
    assert _decision_result_detail(same_day_without_explicit_partial) is None


def test_explicit_same_day_partial_identifies_the_runner_without_a_time():
    legs = [
        _trade(40, 4.0, exit_price=100.0, exit_date=date(2026, 8, 5)),
        _trade(
            41,
            20.0,
            parent_trade_id=40,
            exit_price=110.0,
            exit_date=date(2026, 8, 5),
            exit_reason="partial_take",
        ),
    ]

    assert _decision_result_detail(legs) == "runner_breakeven"
    assert _decision_runner_breakeven_id(legs) == 40


def test_decision_economic_metrics_split_signed_wins_and_losses():
    decisions = {
        1: [_trade(1, 40.0)],
        2: [_trade(2, 60.0)],
        3: [_trade(3, -10.0)],
        4: [_trade(4, -30.0)],
        5: [_trade(5, 0.5)],
        6: [_trade(6, 20.0), _trade(7, 0, is_open=True)],
    }

    metrics = _decision_economic_metrics(decisions)

    assert metrics["decision_average_gain"] == pytest.approx(50.0)
    assert metrics["decision_average_loss"] == pytest.approx(-20.0)
    assert metrics["decision_total_gains"] == pytest.approx(100.0)
    assert metrics["decision_total_losses"] == pytest.approx(-40.0)
