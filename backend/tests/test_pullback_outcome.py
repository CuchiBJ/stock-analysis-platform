"""Behavioral regressions for recovered EMA support followed by continuation."""
import asyncio
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.services.outcome_tracker import OutcomeTracker
from app.services.pullback_outcome import classify_entering_pullback


def snapshot(**overrides):
    values = dict(
        symbol="TEST", transition_type="entering_pullback",
        date_detected=date(2026, 6, 1), price_at_detection=100.0,
        atr_at_detection=2.0, ema9_at_detection=99.0,
        ema21_at_detection=97.0, ema50_at_detection=90.0,
        outcome_status="PENDING", price_1d=None, price_5d=None, price_20d=None,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def bar(low=100.0, high=101.0, close=100.0, **overrides):
    return SimpleNamespace(low=low, high=high, close=close, **overrides)


def supported_window():
    return [bar(low=98.0)] + [bar()] * 9


def test_ema9_test_then_later_continuation_is_success():
    prices = supported_window()
    prices[1] = bar(low=100.0, high=103.0, close=102.0)
    assert classify_entering_pullback(snapshot(), prices) == "SUCCESS"


def test_wick_below_both_fast_emas_can_recover_at_close():
    prices = supported_window()
    prices[0] = bar(low=96.0, close=98.0)
    prices[2] = bar(high=103.0, close=102.0)
    assert classify_entering_pullback(snapshot(), prices) == "SUCCESS"


def test_ema50_touch_invalidates_even_after_continuation():
    prices = supported_window()
    prices[1] = bar(high=103.0, close=102.0)
    prices[9] = bar(low=90.0)
    assert classify_entering_pullback(snapshot(), prices) == "FAILURE"


def test_exact_evolving_ema50_touch_is_failure():
    prices = [bar(low=90.0, close=90.0, high=91.0)] * 10
    assert classify_entering_pullback(
        snapshot(ema9_at_detection=90.0, ema21_at_detection=90.0), prices
    ) == "FAILURE"


def test_close_below_ema21_invalidates_despite_later_rebound():
    prices = supported_window()
    prices[0] = bar(low=95.0, close=96.0)
    prices[1] = bar(high=104.0, close=103.0)
    assert classify_entering_pullback(snapshot(), prices) == "FAILURE"


def test_close_between_averages_alone_is_not_invalidation_or_support():
    prices = [bar(low=98.0, close=98.5)] + [bar()] * 9
    prices[1] = bar(high=103.0, close=102.0)
    # EMA9 was touched without recovery; EMA21 was not touched.
    assert classify_entering_pullback(snapshot(), prices) == "NEUTRAL"


def test_gain_before_support_is_not_continuation():
    prices = [bar(high=104.0, close=103.0)] + [bar()] * 9
    assert classify_entering_pullback(snapshot(), prices) == "NEUTRAL"


def test_same_session_support_and_high_cannot_prove_continuation():
    prices = supported_window()
    prices[0] = bar(low=98.0, high=104.0, close=102.0)
    assert classify_entering_pullback(snapshot(), prices) == "NEUTRAL"


def test_target_without_ema9_closing_recovery_is_not_continuation():
    prices = supported_window()
    prices[1] = bar(low=97.5, high=103.0, close=98.0)
    assert classify_entering_pullback(snapshot(), prices) == "NEUTRAL"


def test_support_without_enough_advance_is_neutral():
    assert classify_entering_pullback(snapshot(), supported_window()) == "NEUTRAL"


def test_tenth_session_qualifies_but_eleventh_does_not():
    prices = supported_window()
    prices[9] = bar(high=103.0, close=102.0)
    assert classify_entering_pullback(snapshot(), prices) == "SUCCESS"
    prices[9] = bar()
    prices.append(bar(high=110.0, close=109.0))
    assert classify_entering_pullback(snapshot(), prices) == "NEUTRAL"


def test_fewer_than_ten_completed_bars_remain_pending():
    assert classify_entering_pullback(snapshot(), supported_window()[:9]) == "PENDING"


@pytest.mark.parametrize("field", [
    "price_at_detection", "atr_at_detection", "ema9_at_detection",
    "ema21_at_detection", "ema50_at_detection",
])
@pytest.mark.parametrize("value", [None, 0.0, -1.0, float("nan"), float("inf")])
def test_missing_or_invalid_detection_inputs_are_insufficient(field, value):
    assert classify_entering_pullback(
        snapshot(**{field: value}), supported_window()
    ) == "INSUFFICIENT_DATA"


@pytest.mark.parametrize("bad_bar", [
    bar(low=float("nan")), bar(high=float("inf")), bar(close=0.0),
    bar(low=102.0), bar(high=99.0),
])
def test_invalid_price_bar_is_insufficient(bad_bar):
    prices = supported_window()
    prices[5] = bad_bar
    assert classify_entering_pullback(snapshot(), prices) == "INSUFFICIENT_DATA"


def test_evolving_ema21_can_invalidate_above_original_ema21():
    prices = supported_window()
    for i in range(1, 6):
        prices[i] = bar(low=102.0, high=104.0, close=103.0)
    prices[6] = bar(low=97.5, close=98.0)
    assert prices[6].close > snapshot().ema21_at_detection
    assert classify_entering_pullback(snapshot(), prices) == "FAILURE"


class PriceDb:
    """Apply the evaluated query's date predicates to synthetic stored bars."""
    def __init__(self, prices):
        self.prices = prices

    async def execute(self, statement):
        from sqlalchemy.sql import operators
        from sqlalchemy.sql.visitors import iterate

        selected = list(self.prices)
        for clause in iterate(statement):
            if not hasattr(clause, "operator") or str(getattr(clause, "left", "")) != "stock_prices.date":
                continue
            bound = clause.right.value
            compare = {
                operators.gt: lambda value: value > bound,
                operators.le: lambda value: value <= bound,
                operators.lt: lambda value: value < bound,
            }[clause.operator]
            selected = [p for p in selected if compare(p.date)]
        selected.sort(key=lambda p: p.date)
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: selected))


def dated_prices():
    dates = []
    cursor = date(2026, 6, 1)
    while len(dates) < 11:
        cursor += timedelta(days=1)
        if cursor.weekday() < 5:
            dates.append(cursor)
    prices = supported_window() + [bar(high=110.0, close=109.0)]
    # Copy repeated neutral bar objects before assigning individual dates.
    return [bar(low=p.low, high=p.high, close=p.close, date=d) for p, d in zip(prices, dates)]


def test_todays_tenth_bar_remains_pending_then_settles_after_it_closes():
    prices = dated_prices()
    prices[9] = bar(low=100.0, high=103.0, close=102.0, date=prices[9].date)
    obs = snapshot()
    tracker = OutcomeTracker(PriceDb(prices))
    asyncio.run(tracker._evaluate_one(obs, prices[9].date))
    assert obs.outcome_status == "PENDING"
    asyncio.run(tracker._evaluate_one(obs, prices[9].date + timedelta(days=1)))
    assert obs.outcome_status == "SUCCESS"


def test_historical_as_of_cannot_see_future_prices():
    prices = dated_prices()
    obs = snapshot()
    asyncio.run(OutcomeTracker(PriceDb(prices))._evaluate_one(obs, prices[4].date))
    assert obs.outcome_status == "PENDING"
    assert obs.price_5d is None


@pytest.mark.parametrize("count,bad_index", [(4, 0), (6, 4), (10, 5)])
def test_invalid_completed_close_does_not_abort_partial_or_full_evaluation(count, bad_index):
    prices = dated_prices()[:count]
    prices[bad_index].close = None
    obs = snapshot()
    asyncio.run(OutcomeTracker(PriceDb(prices))._evaluate_one(
        obs, prices[-1].date + timedelta(days=1)
    ))
    assert obs.outcome_status == "INSUFFICIENT_DATA"


@pytest.mark.parametrize("bad_close", [None, float("nan"), float("inf")])
def test_invalid_twentieth_close_does_not_abort_valid_ten_session_outcome(bad_close):
    prices = dated_prices()
    cursor = prices[-1].date
    while len(prices) < 20:
        cursor += timedelta(days=1)
        if cursor.weekday() < 5:
            prices.append(bar(date=cursor))
    prices[19].close = bad_close
    obs = snapshot()
    asyncio.run(OutcomeTracker(PriceDb(prices))._evaluate_one(obs, cursor + timedelta(days=1)))
    assert obs.outcome_status == "NEUTRAL"
    assert obs.price_20d is None


def test_reclassification_rebuilds_stale_fields_and_chronology():
    prices = dated_prices()
    prices[5] = bar(low=89.0, high=101.0, close=100.0, date=prices[5].date)
    obs = snapshot(outcome_status="SUCCESS", price_1d=999.0, pct_1d=999.0,
                   price_5d=999.0, max_gain_atr_within_10d=999.0, price_20d=999.0)
    tracker = OutcomeTracker(PriceDb(prices))
    asyncio.run(tracker.reevaluate_pullback(obs, prices[-1].date + timedelta(days=1)))
    assert obs.outcome_status == "FAILURE"
    assert obs.price_1d == 100.0
    assert obs.pct_1d == 0.0
    assert obs.price_5d == 100.0
    assert obs.price_20d is None
    assert obs.max_gain_atr_within_10d == 0.5


def test_reclassification_rejects_unrelated_transition():
    obs = snapshot(transition_type="volume_dry_up", outcome_status="SUCCESS")
    with pytest.raises(ValueError):
        asyncio.run(OutcomeTracker(PriceDb([])).reevaluate_pullback(obs, date(2026, 6, 30)))
    assert obs.outcome_status == "SUCCESS"
