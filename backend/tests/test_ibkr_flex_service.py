"""Tests for the IBKR Flex → journal sync core (no network, no DB).

Covers the risky deterministic logic:
  - parse_executions: STK filter, field extraction, abs qty/commission
  - _read_flex_status: status envelope vs. real query response
  - _parse_flex_date: IBKR date formats
  - pair_executions: FIFO pairing, P&L incl. commissions, and the idempotency
    keys that make re-sync safe (closed "<sell>:<buy>", open "<buy>:open"),
    including the open→closed key transition.
"""
import asyncio
from datetime import date

import pytest

import app.services.ibkr_flex_service as flex
from app.services.ibkr_flex_service import (
    IbkrFlexError,
    _FlexTransient,
    _parse_flex_date,
    _read_flex_status,
    _send_with_retry,
    pair_executions,
    parse_executions,
)


def _query_xml(trades: str) -> str:
    return (
        '<FlexQueryResponse queryName="q" type="AF">'
        '<FlexStatements count="1"><FlexStatement accountId="U1">'
        f"<Trades>{trades}</Trades>"
        "</FlexStatement></FlexStatements></FlexQueryResponse>"
    )


def _trade(**attrs) -> str:
    return "<Trade " + " ".join(f'{k}="{v}"' for k, v in attrs.items()) + " />"


# ── parse_executions ─────────────────────────────────────────────────────────

def test_parse_executions_extracts_stk_and_skips_others():
    xml = _query_xml(
        _trade(tradeID="B1", symbol="AAPL", assetCategory="STK", buySell="BUY",
               tradeDate="20260601", quantity="100", tradePrice="150.25", ibCommission="-1.0")
        + _trade(tradeID="O1", symbol="SPY", assetCategory="OPT", buySell="BUY",
                 tradeDate="20260601", quantity="1", tradePrice="2.0", ibCommission="-0.5")
        + _trade(tradeID="S1", symbol="AAPL", assetCategory="STK", buySell="SELL",
                 tradeDate="20260605", quantity="-40", tradePrice="160", ibCommission="-1.0")
    )
    execs = parse_executions(xml)
    assert [e.trade_id for e in execs] == ["B1", "S1"]  # OPT filtered out
    b1 = execs[0]
    assert b1.symbol == "AAPL"
    assert b1.side == "BUY"
    assert b1.quantity == 100.0
    assert b1.price == 150.25
    assert b1.commission == 1.0  # abs of -1.0
    assert b1.trade_date == date(2026, 6, 1)
    assert execs[1].quantity == 40.0  # abs of -40


def test_parse_executions_includes_missing_asset_category():
    """When the Flex query omits the assetCategory column it arrives empty; such
    rows are included (treated as stock) rather than dropped."""
    xml = _query_xml(
        _trade(tradeID="B1", symbol="AAPL", buySell="BUY",
               tradeDate="20260601", quantity="100", tradePrice="150", ibCommission="-1.0")
        + _trade(tradeID="O1", symbol="SPY", assetCategory="OPT", buySell="BUY",
                 tradeDate="20260601", quantity="1", tradePrice="2.0", ibCommission="-0.5")
    )
    execs = parse_executions(xml)
    assert [e.trade_id for e in execs] == ["B1"]  # missing-category kept, OPT dropped


def test_parse_executions_skips_incomplete_rows():
    xml = _query_xml(
        _trade(tradeID="B1", symbol="AAPL", assetCategory="STK", buySell="BUY",
               tradeDate="20260601", tradePrice="150")  # missing quantity
    )
    assert parse_executions(xml) == []


# ── status envelope ──────────────────────────────────────────────────────────

def test_read_flex_status_success_envelope():
    xml = ("<FlexStatementResponse><Status>Success</Status>"
           "<ReferenceCode>123</ReferenceCode></FlexStatementResponse>")
    status, code, msg = _read_flex_status(xml)
    assert status == "Success"


def test_read_flex_status_returns_none_for_query_response():
    status, code, msg = _read_flex_status(_query_xml(""))
    assert status is None and code is None


# ── date parsing ─────────────────────────────────────────────────────────────

def test_parse_flex_date_formats():
    assert _parse_flex_date("20260615") == date(2026, 6, 15)
    assert _parse_flex_date("2026-06-15") == date(2026, 6, 15)
    assert _parse_flex_date("20260615;101530") == date(2026, 6, 15)
    assert _parse_flex_date("") is None


# ── pairing + idempotency keys ───────────────────────────────────────────────

def test_pair_round_trip_pnl_includes_commissions():
    execs = parse_executions(_query_xml(
        _trade(tradeID="B1", symbol="AAPL", assetCategory="STK", buySell="BUY",
               tradeDate="20260601", quantity="100", tradePrice="150", ibCommission="-1.0")
        + _trade(tradeID="S1", symbol="AAPL", assetCategory="STK", buySell="SELL",
                 tradeDate="20260605", quantity="100", tradePrice="160", ibCommission="-1.0")
    ))
    legs = pair_executions(execs)
    assert len(legs) == 1
    leg = legs[0]
    assert leg.is_open is False
    assert leg.broker_exec_id == "S1:B1"
    assert leg.broker_open_exec_id == "B1"
    assert leg.qty == 100
    # (160-150)*100 - 1 buy - 1 sell = 998
    assert leg.pnl_dollars == 998.0


def test_pair_partial_then_full_keys_transition():
    """A partial sell yields a closed leg + an open remainder. Once the position
    is fully sold, the open key disappears — which is what lets the sync delete
    the stale open row and dedupe the unchanged closed leg."""
    buy = _trade(tradeID="B1", symbol="AAPL", assetCategory="STK", buySell="BUY",
                 tradeDate="20260601", quantity="100", tradePrice="150", ibCommission="-1.0")
    sell40 = _trade(tradeID="S1", symbol="AAPL", assetCategory="STK", buySell="SELL",
                    tradeDate="20260605", quantity="40", tradePrice="160", ibCommission="-1.0")
    sell60 = _trade(tradeID="S2", symbol="AAPL", assetCategory="STK", buySell="SELL",
                    tradeDate="20260610", quantity="60", tradePrice="170", ibCommission="-1.0")

    partial = pair_executions(parse_executions(_query_xml(buy + sell40)))
    keys_partial = {l.broker_exec_id for l in partial}
    assert keys_partial == {"S1:B1", "B1:open"}
    closed = next(l for l in partial if not l.is_open)
    assert closed.qty == 40
    # (160-150)*40 - 0.4 buy share - 1.0 sell = 398.6
    assert closed.pnl_dollars == 398.6

    full = pair_executions(parse_executions(_query_xml(buy + sell40 + sell60)))
    keys_full = {l.broker_exec_id for l in full}
    assert keys_full == {"S1:B1", "S2:B1"}  # open remainder gone
    assert all(not l.is_open for l in full)


def test_pair_is_deterministic_across_runs():
    """Same executions → identical keys, so re-sync skips everything."""
    execs = parse_executions(_query_xml(
        _trade(tradeID="B1", symbol="MSFT", assetCategory="STK", buySell="BUY",
               tradeDate="20260601", quantity="10", tradePrice="400", ibCommission="-1.0")
    ))
    run1 = {l.broker_exec_id for l in pair_executions(execs)}
    run2 = {l.broker_exec_id for l in pair_executions(execs)}
    assert run1 == run2 == {"B1:open"}


# ── SendRequest throttle retry ───────────────────────────────────────────────

def test_send_with_retry_recovers_from_transient(monkeypatch):
    """A couple of 1001 throttles then success → returns the reference code."""
    calls = {"n": 0}

    async def fake_send(client, token, query_id):
        calls["n"] += 1
        if calls["n"] < 3:
            raise _FlexTransient("1001", "busy")
        return "REF123"

    monkeypatch.setattr(flex, "_send_request", fake_send)
    ref = asyncio.run(_send_with_retry(None, "t", "q", base_delay=0))
    assert ref == "REF123"
    assert calls["n"] == 3


def test_send_with_retry_persistent_throttle_raises_friendly(monkeypatch):
    async def always_throttled(client, token, query_id):
        raise _FlexTransient("1001", "busy")

    monkeypatch.setattr(flex, "_send_request", always_throttled)
    with pytest.raises(IbkrFlexError) as exc:
        asyncio.run(_send_with_retry(None, "t", "q", retries=2, base_delay=0))
    assert "limitando" in str(exc.value)


def test_pair_fifo_across_two_buys():
    execs = parse_executions(_query_xml(
        _trade(tradeID="B1", symbol="NVDA", assetCategory="STK", buySell="BUY",
               tradeDate="20260601", quantity="100", tradePrice="150", ibCommission="-1.0")
        + _trade(tradeID="B2", symbol="NVDA", assetCategory="STK", buySell="BUY",
                 tradeDate="20260602", quantity="50", tradePrice="160", ibCommission="-1.0")
        + _trade(tradeID="S1", symbol="NVDA", assetCategory="STK", buySell="SELL",
                 tradeDate="20260605", quantity="120", tradePrice="170", ibCommission="-1.2")
    ))
    legs = pair_executions(execs)
    keys = {l.broker_exec_id for l in legs}
    # S1 closes all of B1 (100) and 20 of B2; 30 of B2 remain open.
    assert keys == {"S1:B1", "S1:B2", "B2:open"}
    open_leg = next(l for l in legs if l.is_open)
    assert open_leg.qty == 30
