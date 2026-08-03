"""Tests for the pipeline-health-visibility surface.

Covered:
  - compute_market_state — pure function, all 5 session phases
  - record_cycle — upsert semantics, last_success_at preservation, DB-error safety
"""
import asyncio
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytz
from sqlalchemy.dialects import postgresql

from app.api.v1.endpoints.health import _coverage, compute_market_state
from app.data.pipeline_heartbeat import record_cycle
from app.data.scheduler import DataScheduler


ET = pytz.timezone("US/Eastern")


def _et(year, month, day, hour, minute):
    return ET.localize(datetime(year, month, day, hour, minute))


# ---- compute_market_state ----------------------------------------------------

def test_market_state_pre_market_weekday():
    state = compute_market_state(_et(2026, 6, 2, 8, 0))  # Tue 08:00 ET
    assert state["session_phase"] == "pre_market"
    assert state["is_open"] is False
    assert state["is_warmup"] is False
    assert state["minutes_since_open"] == -90


def test_market_state_warmup_window():
    state = compute_market_state(_et(2026, 6, 2, 9, 45))  # Tue 09:45 ET
    assert state["session_phase"] == "warmup"
    assert state["is_open"] is True
    assert state["is_warmup"] is True
    assert state["minutes_since_open"] == 15


def test_market_state_warmup_boundary_inclusive():
    state = compute_market_state(_et(2026, 6, 2, 10, 30))
    assert state["is_warmup"] is True
    assert state["session_phase"] == "warmup"


def test_market_state_regular_just_after_warmup():
    state = compute_market_state(_et(2026, 6, 2, 10, 31))
    assert state["is_warmup"] is False
    assert state["session_phase"] == "regular"
    assert state["is_open"] is True


def test_market_state_regular_session():
    state = compute_market_state(_et(2026, 6, 2, 13, 0))
    assert state["session_phase"] == "regular"
    assert state["is_open"] is True
    assert state["minutes_since_open"] == 210


def test_market_state_after_hours():
    state = compute_market_state(_et(2026, 6, 2, 17, 0))
    assert state["session_phase"] == "after_hours"
    assert state["is_open"] is False
    assert state["is_warmup"] is False


def test_market_state_late_evening_closed():
    state = compute_market_state(_et(2026, 6, 2, 21, 0))
    assert state["session_phase"] == "closed"


def test_market_state_saturday_returns_closed():
    state = compute_market_state(_et(2026, 6, 6, 11, 0))  # Saturday
    assert state["session_phase"] == "closed"
    assert state["is_open"] is False
    assert state["is_warmup"] is False
    assert state["minutes_since_open"] is None


# ---- quality cohort coverage -------------------------------------------------

def _scalar_result(value):
    result = MagicMock()
    result.scalar.return_value = value
    return result


def test_coverage_uses_same_reference_cohort_for_actual_and_expected():
    """Today's filter changes must not look like failed metric refreshes."""
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[
        _scalar_result(date(2026, 7, 31)),  # working price date
        _scalar_result(date(2026, 7, 30)),  # last complete metrics session
        _scalar_result(619),                # reference quality cohort
        _scalar_result(618),                # refreshed members of that cohort
    ])

    coverage = _run(_coverage(db, _et(2026, 7, 31, 13, 0)))

    assert coverage == {"expected": 619, "actual": 618, "pct": 99.8}

    actual_stmt = db.execute.await_args_list[3].args[0]
    actual_sql = str(actual_stmt.compile(
        dialect=postgresql.dialect(),
        compile_kwargs={"literal_binds": True},
    ))
    # The actual query selects today's fresh rows, but cohort membership and all
    # QUALITY_FILTERS are evaluated at the reference date inside the subquery.
    assert "stock_metrics.date = '2026-07-31'" in actual_sql
    assert "stock_metrics.date = '2026-07-30'" in actual_sql
    assert "stock_metrics.symbol IN (SELECT" in actual_sql


# ---- clock-skew self-recovery ------------------------------------------------

def test_future_dated_markers_flags_skewed_cadence():
    """A marker stamped well in the future (backward clock correction) is flagged
    so the loop can reset and self-recover instead of freezing."""
    now = _et(2026, 6, 2, 13, 0)
    markers = {
        "price": now - timedelta(minutes=10),        # past — fine
        "fast_metrics": now + timedelta(hours=3),    # future — skew
        "slow_metrics": None,                        # unset — ignored
        "realtime_discovery": now + timedelta(seconds=30),  # within tolerance
    }
    flagged = DataScheduler._future_dated_markers(markers, now)
    assert flagged == ["fast_metrics"]


def test_future_dated_markers_empty_when_all_in_past():
    now = _et(2026, 6, 2, 13, 0)
    markers = {
        "price": now - timedelta(minutes=1),
        "fast_metrics": now - timedelta(minutes=5),
        "slow_metrics": now,
    }
    assert DataScheduler._future_dated_markers(markers, now) == []


# ---- record_cycle ------------------------------------------------------------
# These use asyncio.run to avoid requiring pytest-asyncio at runtime.

def _run(coro):
    return asyncio.run(coro)


def test_record_cycle_ok_includes_last_success_at_in_update():
    db = AsyncMock()

    _run(record_cycle(
        db, "slow_metrics",
        duration_seconds=12.3,
        symbols_processed=4000, symbols_expected=4000,
        status="ok",
    ))

    assert db.execute.await_count == 1
    db.commit.assert_awaited_once()
    stmt = db.execute.await_args.args[0]
    update_clause = stmt._post_values_clause.update_values_to_set  # type: ignore[attr-defined]
    update_key_names = [k[0].name if hasattr(k[0], "name") else str(k[0]) for k in update_clause]
    assert "last_success_at" in update_key_names


def test_record_cycle_partial_omits_last_success_update():
    """When status=partial, last_success_at should NOT be in the upsert SET clause
    (so the prior successful timestamp is preserved)."""
    db = AsyncMock()

    _run(record_cycle(
        db, "slow_metrics",
        duration_seconds=20.0,
        symbols_processed=3000, symbols_expected=4000,
        status="partial",
        error_message="Polygon 429 on batch 12",
    ))

    stmt = db.execute.await_args.args[0]
    update_clause = stmt._post_values_clause.update_values_to_set  # type: ignore[attr-defined]
    update_key_names = [k[0].name if hasattr(k[0], "name") else str(k[0]) for k in update_clause]
    assert "last_success_at" not in update_key_names


def test_record_cycle_db_failure_does_not_raise():
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=RuntimeError("DB unreachable"))

    _run(record_cycle(
        db, "price",
        duration_seconds=1.0,
        status="failed",
        error_message="connection refused",
    ))
    db.rollback.assert_awaited()
