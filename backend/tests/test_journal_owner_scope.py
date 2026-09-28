from __future__ import annotations

import asyncio
import inspect
from datetime import date
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints import journal as journal_api
from app.repositories.journal_repository import JournalRepository
from app.services.journal_importer import ImportStats, JournalImporter


class _Scalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _Result:
    def __init__(self, *, rows=(), scalar=None, rowcount=0):
        self._rows = rows
        self._scalar = scalar
        self.rowcount = rowcount

    def scalars(self):
        return _Scalars(self._rows)

    def scalar_one_or_none(self):
        return self._scalar

    def scalar_one(self):
        return self._scalar


class _RecordingDB:
    def __init__(self, results=()):
        self.statements = []
        self._results = iter(results)
        self.commits = 0
        self.rollbacks = 0
        self.flushes = 0

    async def execute(self, statement):
        self.statements.append(statement)
        return next(self._results)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    async def flush(self):
        self.flushes += 1

    async def refresh(self, _instance):
        return None


def _compiled(statement):
    compiled = statement.compile()
    return str(compiled), compiled.params


def test_every_public_repository_operation_requires_owner_user_id():
    public_methods = [
        member
        for name, member in inspect.getmembers(
            JournalRepository, predicate=inspect.iscoroutinefunction
        )
        if not name.startswith("_")
    ]
    assert public_methods
    for method in public_methods:
        parameter = inspect.signature(method).parameters.get("owner_user_id")
        assert parameter is not None, method.__name__
        assert parameter.default is inspect.Parameter.empty, method.__name__


def test_repository_list_get_and_delete_all_bind_the_owner_uuid():
    owner_id = uuid4()
    db = _RecordingDB(
        [_Result(rows=[]), _Result(scalar=None), _Result(rowcount=3)]
    )
    repository = JournalRepository(db)

    asyncio.run(repository.list_trades(owner_user_id=owner_id))
    asyncio.run(
        repository.get_trade(owner_user_id=owner_id, trade_id=99)
    )
    deleted = asyncio.run(
        repository.delete_all_trades(owner_user_id=owner_id)
    )

    assert deleted == 3
    for statement in db.statements:
        sql, params = _compiled(statement)
        assert "owner_user_id" in sql
        assert owner_id in params.values()
    get_sql, get_params = _compiled(db.statements[1])
    assert "journal_trades.id" in get_sql
    assert 99 in get_params.values()


@pytest.mark.parametrize(
    ("operation", "result"),
    [
        ("list", _Result(rows=[])),
        ("get", _Result(scalar=None)),
        ("delete", _Result(rowcount=0)),
        ("replace", _Result(rowcount=0)),
        ("stats", _Result(scalar=0)),
        ("stop_history", _Result(scalar=None)),
    ],
)
def test_two_user_adversarial_repository_matrix_never_crosses_owner(
    operation, result
):
    """Every private read/write emits a different owner predicate per user."""

    owner_a = uuid4()
    owner_b = uuid4()
    statements_by_owner = {}

    for owner in (owner_a, owner_b):
        db = _RecordingDB([result])
        repository = JournalRepository(db)
        if operation == "list":
            asyncio.run(repository.list_trades(owner_user_id=owner))
        elif operation == "get":
            asyncio.run(
                repository.get_trade(owner_user_id=owner, trade_id=404)
            )
        elif operation == "delete":
            asyncio.run(
                repository.delete_trade(owner_user_id=owner, trade_id=404)
            )
        elif operation == "replace":
            asyncio.run(repository.delete_all_trades(owner_user_id=owner))
        elif operation == "stats":
            asyncio.run(
                repository.count_trades(
                    owner_user_id=owner,
                    open_only=True,
                    linked_only=True,
                    marked_from_queue_only=True,
                )
            )
        else:
            assert operation == "stop_history"
            assert asyncio.run(
                repository.list_stop_events(
                    owner_user_id=owner, trade_id=404
                )
            ) is None

        assert len(db.statements) == 1
        sql, params = _compiled(db.statements[0])
        assert "owner_user_id" in sql
        assert owner in params.values()
        statements_by_owner[owner] = params

    assert owner_b not in statements_by_owner[owner_a].values()
    assert owner_a not in statements_by_owner[owner_b].values()


def test_cross_owner_trade_injection_is_rejected_before_database_mutation():
    owner_a = uuid4()
    owner_b = uuid4()
    db = _RecordingDB()
    trade = SimpleNamespace(owner_user_id=owner_a)

    with pytest.raises(ValueError, match="owner"):
        asyncio.run(
            JournalRepository(db).add_trade(
                owner_user_id=owner_b, trade=trade
            )
        )

    assert db.statements == []
    assert db.commits == 0


class _ImporterRepository:
    def __init__(self, deleted=0):
        self.deleted = deleted
        self.delete_owners = []
        self.added = []

    async def delete_all_trades(self, *, owner_user_id):
        self.delete_owners.append(owner_user_id)
        return self.deleted

    async def add_trade(self, *, owner_user_id, trade):
        self.added.append((owner_user_id, trade))
        return trade


def test_importer_assigns_owner_and_commits_replace_as_one_unit(monkeypatch):
    owner_id = uuid4()
    db = _RecordingDB()
    importer = JournalImporter(db, owner_id)
    repository = _ImporterRepository(deleted=4)
    importer.repository = repository

    async def no_observation(_symbol, _entry_date):
        return None

    monkeypatch.setattr(importer, "_find_linked_observation", no_observation)
    csv_text = (
        "Fecha,Ticker,Tipo,Cantidad,Precio Unitario\n"
        "2026-09-01,AAPL,Compra,2,100\n"
    )

    stats = asyncio.run(importer.import_csv(csv_text, replace=True))

    assert stats.cleared_prior_trades == 4
    assert repository.delete_owners == [owner_id]
    assert len(repository.added) == 1
    added_owner, trade = repository.added[0]
    assert added_owner == owner_id
    assert trade.owner_user_id == owner_id
    assert (db.commits, db.rollbacks) == (1, 0)


def test_importer_rolls_back_replace_when_parsing_fails():
    owner_id = uuid4()
    db = _RecordingDB()
    importer = JournalImporter(db, owner_id)
    repository = _ImporterRepository(deleted=2)
    importer.repository = repository

    with pytest.raises(ValueError):
        asyncio.run(importer.import_csv("not,a,journal", replace=True))

    assert repository.delete_owners == [owner_id]
    assert (db.commits, db.rollbacks) == (0, 1)


class _MissingRepository:
    def __init__(self, _db):
        self.deleted = False

    async def get_trade(self, **_kwargs):
        return None

    async def delete_trade(self, **_kwargs):
        return False

    async def list_stop_events(self, **_kwargs):
        return None


def _active_user(user_id: UUID):
    return SimpleNamespace(id=user_id)


def test_foreign_trade_mutations_are_indistinguishable_404(monkeypatch):
    monkeypatch.setattr(journal_api, "JournalRepository", _MissingRepository)
    user = _active_user(uuid4())
    db = _RecordingDB()
    close_payload = journal_api.CloseTradeIn(
        exit_date=date(2026, 9, 2), exit_price=101
    )

    with pytest.raises(HTTPException) as close_error:
        asyncio.run(
            journal_api.close_trade(77, close_payload, db, user)
        )
    with pytest.raises(HTTPException) as patch_error:
        asyncio.run(
            journal_api.patch_trade(77, journal_api.PatchTradeIn(), db, user)
        )
    with pytest.raises(HTTPException) as history_error:
        asyncio.run(journal_api.get_stop_history(77, db, user))
    with pytest.raises(HTTPException) as delete_error:
        asyncio.run(journal_api.delete_trade(77, db, user))

    assert {
        close_error.value.status_code,
        patch_error.value.status_code,
        history_error.value.status_code,
        delete_error.value.status_code,
    } == {404}
    assert db.commits == 0


def test_partial_close_child_inherits_authenticated_owner(monkeypatch):
    owner_id = uuid4()
    source = journal_api.JournalTrade(
        id=8,
        owner_user_id=owner_id,
        symbol="AAPL",
        setup="breakout",
        context="unknown",
        entry_date=date(2026, 9, 1),
        entry_price=100.0,
        qty=10.0,
        stop_price=95.0,
        initial_stop_price=95.0,
        source_row=1,
        entry_reason="other",
        exit_reason="unknown",
    )

    class _PartialRepository:
        added = []

        def __init__(self, _db):
            pass

        async def get_trade(self, *, owner_user_id, trade_id, for_update):
            assert (owner_user_id, trade_id, for_update) == (owner_id, 8, True)
            return source

        async def add_trade(self, *, owner_user_id, trade):
            assert owner_user_id == owner_id
            self.added.append(trade)
            return trade

    monkeypatch.setattr(journal_api, "JournalRepository", _PartialRepository)
    db = _RecordingDB()
    payload = journal_api.CloseTradeIn(
        exit_date=date(2026, 9, 2), exit_price=110.0, qty=4.0
    )

    result = asyncio.run(journal_api.close_trade(8, payload, db, _active_user(owner_id)))

    child = _PartialRepository.added[-1]
    assert child.owner_user_id == owner_id
    assert child.parent_trade_id == source.id
    assert source.qty == 6.0
    assert result["closed"]["qty"] == 4.0


def test_no_direct_journal_trade_queries_outside_repository():
    """Static tripwire for future tenant-boundary regressions in app code."""
    from pathlib import Path
    import re

    backend_root = Path(__file__).parents[1]
    approved = {
        backend_root / "app" / "repositories" / "journal_repository.py",
        # Explicit one-time maintenance path; it locks and validates the
        # complete legacy data set before assigning its initial owner.
        backend_root / "scripts" / "claim_legacy_journal.py",
    }
    query_pattern = re.compile(
        r"(?:select|delete|update)\s*\(\s*JournalTrade|"
        r"\.get\s*\(\s*JournalTrade"
    )
    violations = []
    for source_dir in (backend_root / "app", backend_root / "scripts"):
        paths = source_dir.rglob("*.py")
        for path in paths:
            if path in approved:
                continue
            if query_pattern.search(path.read_text()):
                violations.append(str(path.relative_to(backend_root)))
    assert violations == []


def test_journal_endpoint_is_a_thin_authenticated_boundary():
    from pathlib import Path

    endpoint = (
        Path(__file__).parents[1]
        / "app"
        / "api"
        / "v1"
        / "endpoints"
        / "journal.py"
    )
    source = endpoint.read_text()

    assert len(source.splitlines()) < 100
    assert "Depends(get_current_active_user)" in source
    assert "select(JournalTrade" not in source
