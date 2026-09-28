"""Schema-level checks for staged journal ownership.

These tests deliberately exercise the ORM metadata as a fresh database and
inspect the Alembic operations separately.  The production migrations target
PostgreSQL, while the in-memory database keeps the uniqueness/cascade tests
fast and deterministic.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError

from app.models.stock import JournalStopEvent, JournalTrade
from app.models.user import User


def _load_migration(module_name: str, filename: str):
    path = Path(__file__).parents[1] / "alembic" / "versions" / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


expand = _load_migration(
    "journal_ownership_expand", "c8d9e0f1a2b3_add_identity_tables.py"
)
contract = _load_migration(
    "journal_ownership_contract", "d9e0f1a2b3c4_contract_journal_ownership.py"
)


@pytest.fixture()
def ownership_engine():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    User.__table__.create(engine)
    JournalTrade.__table__.create(engine)
    JournalStopEvent.__table__.create(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def _user_row(user_id, email):
    return {
        "id": user_id,
        "email": email,
        "password_hash": "hash",
        "role": "user",
        "state": "active",
    }


def _trade_row(owner_id, broker_exec_id):
    return {
        "owner_user_id": owner_id,
        "symbol": "TEST",
        "setup": "breakout",
        "context": "unknown",
        "entry_date": date(2026, 1, 2),
        "entry_price": 10.0,
        "qty": 5.0,
        "entry_reason": "other",
        "exit_reason": "unknown",
        "source_row": 1,
        "imported_at": datetime.now(timezone.utc),
        "broker_exec_id": broker_exec_id,
    }


def test_fresh_metadata_enforces_per_owner_broker_uniqueness(ownership_engine):
    first_owner = uuid4()
    second_owner = uuid4()
    with ownership_engine.begin() as connection:
        connection.execute(
            User.__table__.insert(),
            [
                _user_row(first_owner, "one@example.com"),
                _user_row(second_owner, "two@example.com"),
            ],
        )
        connection.execute(
            JournalTrade.__table__.insert(),
            _trade_row(first_owner, "shared-broker-id"),
        )
        connection.execute(
            JournalTrade.__table__.insert(),
            _trade_row(second_owner, "shared-broker-id"),
        )

    with pytest.raises(IntegrityError):
        with ownership_engine.begin() as connection:
            connection.execute(
                JournalTrade.__table__.insert(),
                _trade_row(first_owner, "shared-broker-id"),
            )


def test_stop_events_are_removed_with_their_trade(ownership_engine):
    owner_id = uuid4()
    with ownership_engine.begin() as connection:
        connection.execute(User.__table__.insert(), _user_row(owner_id, "owner@example.com"))
        trade_id = connection.execute(
            JournalTrade.__table__.insert().returning(JournalTrade.id),
            _trade_row(owner_id, None),
        ).scalar_one()
        connection.execute(
            JournalStopEvent.__table__.insert(),
            {
                "trade_id": trade_id,
                "kind": "initial",
                "occurred_at": datetime.now(timezone.utc),
                "auto_classified": True,
            },
        )
        connection.execute(JournalTrade.__table__.delete().where(JournalTrade.id == trade_id))
        assert connection.scalar(select(JournalStopEvent.id)) is None


class _OperationRecorder:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def record(*args, **kwargs):
            self.calls.append((name, args, kwargs))

        return record


def test_expand_migration_is_nullable_and_owner_first(monkeypatch):
    recorder = _OperationRecorder()
    monkeypatch.setattr(expand, "op", recorder)
    monkeypatch.setattr(expand, "_abort_if_rows_exist", lambda *_args: None)

    expand.upgrade()

    owner_column = next(
        args[1]
        for name, args, _kwargs in recorder.calls
        if name == "add_column" and args[0] == "journal_trades"
    )
    assert owner_column.name == "owner_user_id"
    assert owner_column.nullable is True

    indexes = {
        args[0]: (tuple(args[2]), kwargs.get("unique", False))
        for name, args, kwargs in recorder.calls
        if name == "create_index"
    }
    assert indexes["ix_journal_owner_entry"][0][0] == "owner_user_id"
    assert indexes["ix_journal_owner_symbol_entry"][0][0] == "owner_user_id"
    assert indexes["ix_journal_owner_exit_date"][0][0] == "owner_user_id"
    assert indexes["ix_journal_owner_parent_trade"][0][0] == "owner_user_id"
    assert indexes["uq_journal_owner_broker_exec"] == (
        ("owner_user_id", "broker_exec_id"),
        True,
    )
    stop_fk = next(
        (args, kwargs)
        for name, args, kwargs in recorder.calls
        if name == "create_foreign_key"
    )
    assert stop_fk[0][1:5] == (
        "journal_stop_events",
        "journal_trades",
        ["trade_id"],
        ["id"],
    )
    assert stop_fk[1]["ondelete"] == "CASCADE"


def test_contract_migration_validates_before_non_null_and_owner_fk(monkeypatch):
    recorder = _OperationRecorder()
    validations = []
    monkeypatch.setattr(contract, "op", recorder)
    monkeypatch.setattr(
        contract,
        "_abort_if_rows_exist",
        lambda query, message: validations.append((query, message)),
    )

    contract.upgrade()

    assert len(validations) == 2
    alter = next(call for call in recorder.calls if call[0] == "alter_column")
    assert alter[1][:2] == ("journal_trades", "owner_user_id")
    assert alter[2]["nullable"] is False
    owner_fk = next(call for call in recorder.calls if call[0] == "create_foreign_key")
    assert owner_fk[1][1:5] == (
        "journal_trades",
        "users",
        ["owner_user_id"],
        ["id"],
    )
    assert owner_fk[2]["ondelete"] == "RESTRICT"
