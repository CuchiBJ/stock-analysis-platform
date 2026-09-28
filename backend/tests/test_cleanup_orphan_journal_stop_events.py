from __future__ import annotations

import asyncio
from types import SimpleNamespace

from scripts import cleanup_orphan_journal_stop_events as cleanup


class _CleanupDatabase:
    def __init__(self, counts, rowcount):
        self.counts = iter(counts)
        self.rowcount = rowcount
        self.statements = []

    async def scalar(self, statement):
        self.statements.append(str(statement))
        return next(self.counts)

    async def execute(self, statement):
        self.statements.append(str(statement))
        return SimpleNamespace(rowcount=self.rowcount)


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


def test_cleanup_deletes_only_detected_orphans_after_locking_tables():
    database = _CleanupDatabase(counts=[3, 0], rowcount=3)

    report = asyncio.run(cleanup.cleanup_orphans(database, dry_run=True))

    assert report == cleanup.CleanupReport(
        dry_run=True,
        orphan_count_before=3,
        deleted_count=3,
        orphan_count_after=0,
    )
    assert "LOCK TABLE journal_trades, journal_stop_events" in database.statements[0]
    assert "WHERE NOT EXISTS" in database.statements[2]


def test_run_cleanup_rolls_back_dry_run_and_commits_execute(monkeypatch):
    async def successful_cleanup(_db, *, dry_run):
        return cleanup.CleanupReport(dry_run, 1, 1, 0)

    monkeypatch.setattr(cleanup, "cleanup_orphans", successful_cleanup)

    dry_session = _TransactionSession()
    monkeypatch.setattr(cleanup, "AsyncSessionLocal", lambda: dry_session)
    asyncio.run(cleanup.run_cleanup(dry_run=True))
    assert (dry_session.commits, dry_session.rollbacks) == (0, 1)

    execute_session = _TransactionSession()
    monkeypatch.setattr(cleanup, "AsyncSessionLocal", lambda: execute_session)
    asyncio.run(cleanup.run_cleanup(dry_run=False))
    assert (execute_session.commits, execute_session.rollbacks) == (1, 0)
