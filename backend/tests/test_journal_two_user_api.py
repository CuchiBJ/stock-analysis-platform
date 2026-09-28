"""Adversarial HTTP matrix for the journal tenant boundary.

The test deliberately exercises the complete FastAPI router (including session
and CSRF dependencies) against an isolated relational database.  Market
snapshot calculations are stubbed because they are shared reference data and
not part of the private journal ownership boundary under test.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from typing import Iterator
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Keep collection self-contained when this focused test is invoked from the
# repository root without a developer .env file.  The production engine is
# never contacted because get_db is overridden below.
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test"
)
os.environ.setdefault("POLYGON_API_KEY", "test-key")

from app.api.v1.api import api_router
from app.core.auth import AuthenticatedSession, get_current_session
from app.core.deps import get_db
from app.models.stock import (
    JournalStopEvent,
    JournalTrade,
    StockMetrics,
    TransitionObservation,
)
from app.models.user import AuthSession, User, UserState
from app.services import journal_application
from app.services.auth_service import digest_token


NOW = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
SESSION_A = "A" * 43
SESSION_B = "B" * 43
CSRF_A = "C" * 43
CSRF_B = "D" * 43


class _AsyncSessionAdapter:
    """Expose the AsyncSession surface used by journal code over a real Session."""

    def __init__(self, session: Session):
        self._session = session

    async def execute(self, statement):
        return self._session.execute(statement)

    def add(self, instance) -> None:
        self._session.add(instance)

    async def flush(self) -> None:
        self._session.flush()

    async def commit(self) -> None:
        self._session.commit()

    async def rollback(self) -> None:
        self._session.rollback()

    async def refresh(self, instance) -> None:
        self._session.refresh(instance)


def _user(email: str) -> User:
    return User(
        id=uuid4(),
        email=email,
        password_hash="not-a-real-hash",
        state=UserState.ACTIVE.value,
        email_verified_at=NOW,
    )


def _principal(user: User, session_token: str, csrf_token: str) -> AuthenticatedSession:
    auth_session = AuthSession(
        user_id=user.id,
        token_digest=digest_token(session_token),
        csrf_token_digest=digest_token(csrf_token),
        expires_at=NOW + timedelta(days=1),
    )
    auth_session.user = user
    return AuthenticatedSession(session=auth_session, user=user)


def _trade(
    owner_id: UUID,
    symbol: str,
    *,
    closed: bool,
    broker_exec_id: str | None = None,
) -> JournalTrade:
    return JournalTrade(
        owner_user_id=owner_id,
        symbol=symbol,
        setup="breakout",
        context="favorable",
        entry_date=date(2026, 9, 1),
        entry_price=100.0,
        qty=10.0,
        stop_price=95.0,
        initial_stop_price=95.0,
        exit_date=date(2026, 9, 10) if closed else None,
        exit_price=110.0 if closed else None,
        pnl_dollars=98.0 if closed else None,
        r_multiple=2.0 if closed else None,
        source_row=1,
        broker_exec_id=broker_exec_id,
    )


def _owner_fingerprint(session_factory, owner_id: UUID) -> tuple:
    """Capture every private field that an adversarial request could mutate."""

    with session_factory() as db:
        trades = db.execute(
            select(JournalTrade)
            .where(JournalTrade.owner_user_id == owner_id)
            .order_by(JournalTrade.id)
        ).scalars().all()
        trade_rows = tuple(
            (
                row.id,
                row.owner_user_id,
                row.symbol,
                row.entry_date,
                row.entry_price,
                row.qty,
                row.stop_price,
                row.initial_stop_price,
                row.exit_date,
                row.exit_price,
                row.setup,
                row.context,
                row.regime_at_entry,
                row.parent_trade_id,
                row.broker_exec_id,
            )
            for row in trades
        )
        ids = [row.id for row in trades]
        events = (
            db.execute(
                select(JournalStopEvent)
                .where(JournalStopEvent.trade_id.in_(ids))
                .order_by(JournalStopEvent.id)
            ).scalars().all()
            if ids
            else []
        )
        event_rows = tuple(
            (
                row.id,
                row.trade_id,
                row.old_stop_price,
                row.new_stop_price,
                row.kind,
            )
            for row in events
        )
    return trade_rows, event_rows


@pytest.fixture
def two_user_api(monkeypatch) -> Iterator[dict]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    tables = [
        User.__table__,
        TransitionObservation.__table__,
        StockMetrics.__table__,
        JournalTrade.__table__,
        JournalStopEvent.__table__,
    ]
    for table in tables:
        table.create(engine)

    session_factory = sessionmaker(engine, expire_on_commit=False)
    user_a = _user("api-owner-a@example.com")
    user_b = _user("api-owner-b@example.com")
    with session_factory() as db:
        db.add_all([user_a, user_b])
        db.flush()
        # The same broker execution ID is valid for separate owners.
        a_closed = _trade(
            user_a.id, "ALFA", closed=True, broker_exec_id="SHARED-EXEC"
        )
        b_closed = _trade(
            user_b.id, "BRAV", closed=True, broker_exec_id="SHARED-EXEC"
        )
        a_open = _trade(user_a.id, "AOPEN", closed=False)
        b_open = _trade(user_b.id, "BOPEN", closed=False)
        db.add_all([a_closed, b_closed, a_open, b_open])
        db.flush()
        db.add_all(
            [
                JournalStopEvent(
                    trade_id=a_open.id,
                    old_stop_price=None,
                    new_stop_price=95.0,
                    kind="initial",
                ),
                JournalStopEvent(
                    trade_id=b_open.id,
                    old_stop_price=None,
                    new_stop_price=95.0,
                    kind="initial",
                ),
            ]
        )
        db.add(
            StockMetrics(
                symbol="QUEUE",
                date=date(2026, 9, 22),
                current_price=42.0,
                ema21=39.0,
            )
        )
        db.commit()
        ids = {"a_open": a_open.id, "b_open": b_open.id}

    async def _db_override():
        with session_factory() as session:
            yield _AsyncSessionAdapter(session)

    principals = {
        SESSION_A: _principal(user_a, SESSION_A, CSRF_A),
        SESSION_B: _principal(user_b, SESSION_B, CSRF_B),
    }

    async def _session_override(request: Request) -> AuthenticatedSession:
        token = request.cookies.get("__Host-session")
        principal = principals.get(token)
        if principal is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return principal

    async def _snapshot(_db, _symbol, _entry_date):
        return {
            "regime_at_entry": None,
            "system_score_at_entry": None,
            "group_strength_at_entry": None,
            "leader_health_at_entry": None,
        }

    async def _regime(_db, _entry_date):
        return "healthy/leading"

    monkeypatch.setattr(journal_application, "take_entry_snapshot", _snapshot)
    monkeypatch.setattr(
        journal_application, "reconstruct_regime_at_entry", _regime
    )

    app = FastAPI()
    app.include_router(api_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = _db_override
    app.dependency_overrides[get_current_session] = _session_override

    clients = {
        "a": TestClient(
            app,
            base_url="https://testserver",
            headers={"X-CSRF-Token": CSRF_A},
        ),
        "b": TestClient(
            app,
            base_url="https://testserver",
            headers={"X-CSRF-Token": CSRF_B},
        ),
    }
    clients["a"].cookies.set("__Host-session", SESSION_A, path="/")
    clients["b"].cookies.set("__Host-session", SESSION_B, path="/")

    try:
        yield {
            "clients": clients,
            "users": {"a": user_a, "b": user_b},
            "ids": ids,
            "session_factory": session_factory,
        }
    finally:
        for client in clients.values():
            client.close()
        engine.dispose()


def test_adversarial_two_user_journal_api_matrix(two_user_api):
    clients = two_user_api["clients"]
    users = two_user_api["users"]
    ids = two_user_api["ids"]
    session_factory = two_user_api["session_factory"]

    # Read paths expose only the caller's rows, including stats and CSV.
    expected_symbols = {"a": {"ALFA", "AOPEN"}, "b": {"BRAV", "BOPEN"}}
    for side, client in clients.items():
        other = "b" if side == "a" else "a"
        before_a = _owner_fingerprint(session_factory, users["a"].id)
        before_b = _owner_fingerprint(session_factory, users["b"].id)

        listing = client.get("/api/v1/journal/trades?closed_only=false")
        assert listing.status_code == 200
        assert {trade["symbol"] for trade in listing.json()["trades"]} == (
            expected_symbols[side]
        )

        stats = client.get("/api/v1/journal/stats")
        assert stats.status_code == 200
        assert expected_symbols[other].isdisjoint(str(stats.json()))

        exported = client.get("/api/v1/journal/export.csv")
        assert exported.status_code == 200
        assert all(symbol in exported.text for symbol in expected_symbols[side])
        assert all(symbol not in exported.text for symbol in expected_symbols[other])

        assert _owner_fingerprint(session_factory, users["a"].id) == before_a
        assert _owner_fingerprint(session_factory, users["b"].id) == before_b

    # Both directions receive the same 404 for foreign identifiers, and every
    # rejected attempt leaves both the trade and its stop history byte-for-byte
    # equivalent at the persistence boundary.
    attacks = [
        ("patch", "/api/v1/journal/trades/{id}", {"json": {"qty": 999}}),
        (
            "post",
            "/api/v1/journal/trades/{id}/close",
            {"json": {"exit_date": "2026-09-23", "exit_price": 1}},
        ),
        ("delete", "/api/v1/journal/trades/{id}", {}),
        ("get", "/api/v1/journal/trades/{id}/stop-history", {}),
    ]
    for attacker, victim in (("a", "b"), ("b", "a")):
        victim_id = ids[f"{victim}_open"]
        for method, path, kwargs in attacks:
            before = _owner_fingerprint(session_factory, users[victim].id)
            response = getattr(clients[attacker], method)(
                path.format(id=victim_id), **kwargs
            )
            assert response.status_code == 404
            assert response.json() == {"detail": "trade not found"}
            assert _owner_fingerprint(session_factory, users[victim].id) == before

    # Owner A's replace import is transactional and cannot clear owner B's rows,
    # including B's copy of the shared broker execution ID.
    before_b = _owner_fingerprint(session_factory, users["b"].id)
    csv_text = (
        "Fecha,Ticker,Tipo,Cantidad,Precio Unitario,Stop,Setup,Contexto\n"
        "2026-09-11,IMPA,Compra,3,50,45,Breakout,Favorable\n"
        "2026-09-15,IMPA,Venta,3,55,,Breakout,Favorable\n"
    )
    imported = clients["a"].post(
        "/api/v1/journal/import?replace=true",
        files={"file": ("journal.csv", csv_text, "text/csv")},
    )
    assert imported.status_code == 200
    assert imported.json()["cleared_prior_trades"] == 2
    assert _owner_fingerprint(session_factory, users["b"].id) == before_b
    assert "BRAV" in clients["b"].get("/api/v1/journal/export.csv").text

    # Backfill sees and updates only A's imported row.
    backfilled = clients["a"].post("/api/v1/journal/backfill-regime")
    assert backfilled.status_code == 200
    assert backfilled.json()["updated"] == 1
    with session_factory() as db:
        a_regimes = db.execute(
            select(JournalTrade.regime_at_entry).where(
                JournalTrade.owner_user_id == users["a"].id
            )
        ).scalars().all()
        b_regimes = db.execute(
            select(JournalTrade.regime_at_entry).where(
                JournalTrade.owner_user_id == users["b"].id
            )
        ).scalars().all()
    assert a_regimes == ["healthy/leading"]
    assert b_regimes == [None, None]

    # The queue draft is shared reference data; confirming it creates a private
    # trade owned by the authenticated caller even if a foreign owner is sent.
    before_b = _owner_fingerprint(session_factory, users["b"].id)
    draft = clients["a"].get(
        "/api/v1/journal/trade-draft?symbol=QUEUE&setup=breakout"
    )
    assert draft.status_code == 200
    queue_trade = clients["a"].post(
        "/api/v1/journal/trades",
        json={
            "symbol": draft.json()["symbol"],
            "entry_date": "2026-09-23",
            "entry_price": draft.json()["entry_price"],
            "qty": 4,
            "stop_price": draft.json()["stop_price_suggested"],
            "setup": draft.json()["setup"],
            "from_queue": True,
            "entry_reason": "queue_signal",
            "owner_user_id": str(users["b"].id),
        },
    )
    assert queue_trade.status_code == 201
    queue_id = queue_trade.json()["id"]
    assert queue_trade.json()["symbol"] == "QUEUE"
    assert _owner_fingerprint(session_factory, users["b"].id) == before_b
    with session_factory() as db:
        persisted = db.get(JournalTrade, queue_id)
        assert persisted.owner_user_id == users["a"].id
        assert persisted.from_queue is True

    # Successful owner mutations use the same HTTP paths: edit creates stop
    # history, close changes only A's trade, and delete removes only A's row.
    edited = clients["a"].patch(
        f"/api/v1/journal/trades/{queue_id}", json={"stop_price": 40.0}
    )
    assert edited.status_code == 200
    history = clients["a"].get(
        f"/api/v1/journal/trades/{queue_id}/stop-history"
    )
    assert history.status_code == 200
    assert [event["kind"] for event in history.json()["events"]] == [
        "initial",
        "trailed_up",
    ]

    before_b = _owner_fingerprint(session_factory, users["b"].id)
    closed = clients["a"].post(
        f"/api/v1/journal/trades/{queue_id}/close",
        json={"exit_date": "2026-09-24", "exit_price": 48.0},
    )
    assert closed.status_code == 200
    assert closed.json()["exit_price"] == 48.0
    assert _owner_fingerprint(session_factory, users["b"].id) == before_b

    deleted = clients["a"].delete(f"/api/v1/journal/trades/{queue_id}")
    assert deleted.status_code == 204
    assert _owner_fingerprint(session_factory, users["b"].id) == before_b
    assert clients["a"].get(
        f"/api/v1/journal/trades/{queue_id}/stop-history"
    ).status_code == 404
