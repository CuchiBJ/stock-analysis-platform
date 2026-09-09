"""Decision grouping rules shared by import and manual journal entries."""

from __future__ import annotations

from datetime import date

from app.models.stock import JournalTrade
from app.services.journal_decisions import assign_decision_links


def _open_trade(trade_id: int, symbol: str, setup: str, entry_date: date) -> JournalTrade:
    return JournalTrade(
        id=trade_id,
        symbol=symbol,
        setup=setup,
        context="unknown",
        entry_date=entry_date,
        entry_price=100.0,
        qty=1.0,
        source_row=trade_id,
    )


def test_two_open_buys_in_the_same_symbol_share_one_decision():
    first = _open_trade(10, "AAPL", "u_and_r", date(2026, 8, 1))
    second = _open_trade(11, "AAPL", "u_and_r", date(2026, 8, 10))

    changed = assign_decision_links([second, first])

    assert changed == 1
    assert first.parent_trade_id is None
    assert second.parent_trade_id == first.id


def test_dca_and_tactical_positions_in_the_same_symbol_stay_separate():
    dca_first = _open_trade(20, "SPY", "dca", date(2026, 4, 1))
    dca_second = _open_trade(21, "SPY", "dca", date(2026, 9, 1))
    tactical = _open_trade(22, "SPY", "breakout", date(2026, 8, 1))

    assign_decision_links([dca_first, dca_second, tactical])

    assert dca_first.parent_trade_id is None
    assert dca_second.parent_trade_id == dca_first.id
    assert tactical.parent_trade_id is None
