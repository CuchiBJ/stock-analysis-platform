from __future__ import annotations

import asyncio
from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

import pytest

from scripts import claim_legacy_journal as claim


def _report(*, unowned=0, invalid_parent=0, invalid_stop=0, invalid_link=0):
    return claim.JournalValidationReport(
        trade_count=2,
        unowned_trade_count=unowned,
        open_trade_count=1,
        closed_trade_count=1,
        trade_ids_checksum="ids",
        trade_fields_checksum="fields",
        decision_parent_count=1,
        invalid_parent_target_count=invalid_parent,
        stop_event_count=1,
        invalid_stop_target_count=invalid_stop,
        stop_events_checksum="stops",
        linked_observation_count=1,
        invalid_linked_observation_count=invalid_link,
        quantity_sum="12",
        pnl_dollars_sum="5",
        entry_notional_sum="120",
    )


class _UpdateDB:
    def __init__(self, rowcount):
        self.rowcount = rowcount
        self.execute_calls = 0
        self.flushed = False

    async def execute(self, _statement):
        self.execute_calls += 1
        return SimpleNamespace(rowcount=self.rowcount)

    async def flush(self):
        self.flushed = True


async def _noop(*_args, **_kwargs):
    return None


def test_legacy_claim_assigns_all_rows_and_preserves_invariants(monkeypatch):
    admin_id = uuid4()
    before = _report(unowned=2)
    after = replace(before, unowned_trade_count=0)
    reports = iter((before, after))
    db = _UpdateDB(rowcount=2)

    monkeypatch.setattr(claim, "lock_journal_tables", _noop)
    monkeypatch.setattr(
        claim,
        "validate_admin_target",
        lambda *_args, **_kwargs: _async_value(SimpleNamespace(id=admin_id)),
    )
    monkeypatch.setattr(
        claim,
        "capture_journal_validation",
        lambda *_args, **_kwargs: _async_value(next(reports)),
    )
    monkeypatch.setattr(
        claim,
        "_table_rows",
        lambda *_args, **_kwargs: _async_value(
            [{"owner_user_id": None}, {"owner_user_id": None}]
        ),
    )

    result = asyncio.run(
        claim.claim_legacy_journal(
            db, admin_email="admin@example.com", dry_run=True
        )
    )

    assert result.assigned_trade_count == 2
    assert result.before == before
    assert result.after == after
    assert db.execute_calls == 1
    assert db.flushed is True


def test_claim_is_idempotent_when_every_row_already_has_target_owner(monkeypatch):
    admin_id = uuid4()
    unchanged = _report(unowned=0)
    reports = iter((unchanged, unchanged))
    db = _UpdateDB(rowcount=0)
    monkeypatch.setattr(claim, "lock_journal_tables", _noop)
    monkeypatch.setattr(
        claim,
        "validate_admin_target",
        lambda *_args, **_kwargs: _async_value(SimpleNamespace(id=admin_id)),
    )
    monkeypatch.setattr(
        claim,
        "capture_journal_validation",
        lambda *_args, **_kwargs: _async_value(next(reports)),
    )
    monkeypatch.setattr(
        claim,
        "_table_rows",
        lambda *_args, **_kwargs: _async_value([{"owner_user_id": admin_id}]),
    )

    result = asyncio.run(
        claim.claim_legacy_journal(db, admin_email="admin@example.com")
    )

    assert result.assigned_trade_count == 0
    assert result.before == result.after


def test_mixed_owner_state_aborts_before_update(monkeypatch):
    admin_id = uuid4()
    db = _UpdateDB(rowcount=0)
    monkeypatch.setattr(claim, "lock_journal_tables", _noop)
    monkeypatch.setattr(
        claim,
        "validate_admin_target",
        lambda *_args, **_kwargs: _async_value(SimpleNamespace(id=admin_id)),
    )
    monkeypatch.setattr(
        claim,
        "capture_journal_validation",
        lambda *_args, **_kwargs: _async_value(_report(unowned=1)),
    )
    monkeypatch.setattr(
        claim,
        "_table_rows",
        lambda *_args, **_kwargs: _async_value(
            [{"owner_user_id": None}, {"owner_user_id": uuid4()}]
        ),
    )

    with pytest.raises(claim.JournalClaimError, match="different account"):
        asyncio.run(
            claim.claim_legacy_journal(db, admin_email="admin@example.com")
        )

    assert db.execute_calls == 0


def test_integrity_failure_aborts_before_update(monkeypatch):
    db = _UpdateDB(rowcount=0)
    monkeypatch.setattr(claim, "lock_journal_tables", _noop)
    monkeypatch.setattr(
        claim,
        "validate_admin_target",
        lambda *_args, **_kwargs: _async_value(SimpleNamespace(id=uuid4())),
    )
    monkeypatch.setattr(
        claim,
        "capture_journal_validation",
        lambda *_args, **_kwargs: _async_value(_report(invalid_stop=1)),
    )

    with pytest.raises(claim.JournalClaimError, match="stop events"):
        asyncio.run(
            claim.claim_legacy_journal(db, admin_email="admin@example.com")
        )

    assert db.execute_calls == 0


class _TransactionSession:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


def test_failure_rolls_back_the_whole_claim(monkeypatch):
    session = _TransactionSession()
    monkeypatch.setattr(claim, "AsyncSessionLocal", lambda: session)

    async def fail(*_args, **_kwargs):
        raise claim.JournalClaimError("validation failed")

    monkeypatch.setattr(claim, "claim_legacy_journal", fail)

    with pytest.raises(claim.JournalClaimError):
        asyncio.run(
            claim.run_claim(admin_email="admin@example.com", dry_run=False)
        )

    assert session.commits == 0
    assert session.rollbacks == 1


def test_dry_run_rolls_back_and_execute_commits(monkeypatch):
    result = claim.JournalClaimResult(True, 0, _report(), _report())

    async def succeed(*_args, **kwargs):
        return replace(result, dry_run=kwargs["dry_run"])

    monkeypatch.setattr(claim, "claim_legacy_journal", succeed)

    dry_session = _TransactionSession()
    monkeypatch.setattr(claim, "AsyncSessionLocal", lambda: dry_session)
    asyncio.run(claim.run_claim(admin_email="admin@example.com", dry_run=True))
    assert (dry_session.commits, dry_session.rollbacks) == (0, 1)

    execute_session = _TransactionSession()
    monkeypatch.setattr(claim, "AsyncSessionLocal", lambda: execute_session)
    asyncio.run(claim.run_claim(admin_email="admin@example.com", dry_run=False))
    assert (execute_session.commits, execute_session.rollbacks) == (1, 0)


async def _async_value(value):
    return value
