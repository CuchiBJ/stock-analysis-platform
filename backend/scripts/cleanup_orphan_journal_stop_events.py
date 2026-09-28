#!/usr/bin/env python3
"""Remove stop-history rows whose parent trade no longer exists.

The ownership expansion migration intentionally refuses to add its foreign key
while orphan rows exist.  This preflight command is dry-run by default, emits
counts only, and deletes only rows that cannot be reached by any journal trade.

Usage:
    python scripts/cleanup_orphan_journal_stop_events.py
    python scripts/cleanup_orphan_journal_stop_events.py --execute
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.deps import AsyncSessionLocal


@dataclass(frozen=True)
class CleanupReport:
    dry_run: bool
    orphan_count_before: int
    deleted_count: int
    orphan_count_after: int


async def count_orphans(db: AsyncSession) -> int:
    return int(
        await db.scalar(
            text(
                """
                SELECT count(*)
                FROM journal_stop_events event
                LEFT JOIN journal_trades trade ON trade.id = event.trade_id
                WHERE trade.id IS NULL
                """
            )
        )
        or 0
    )


async def cleanup_orphans(db: AsyncSession, *, dry_run: bool = True) -> CleanupReport:
    await db.execute(
        text("LOCK TABLE journal_trades, journal_stop_events IN ACCESS EXCLUSIVE MODE")
    )
    before = await count_orphans(db)
    deleted = 0
    if before:
        result = await db.execute(
            text(
                """
                DELETE FROM journal_stop_events event
                WHERE NOT EXISTS (
                    SELECT 1 FROM journal_trades trade WHERE trade.id = event.trade_id
                )
                """
            )
        )
        deleted = int(result.rowcount or 0)
    after = await count_orphans(db)
    if after != 0 or deleted != before:
        raise RuntimeError("orphan stop-event cleanup did not converge")
    return CleanupReport(dry_run=dry_run, orphan_count_before=before, deleted_count=deleted, orphan_count_after=after)


async def run_cleanup(*, dry_run: bool = True) -> CleanupReport:
    async with AsyncSessionLocal() as db:
        try:
            report = await cleanup_orphans(db, dry_run=dry_run)
            if dry_run:
                await db.rollback()
            else:
                await db.commit()
            return report
        except Exception:
            await db.rollback()
            raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Delete only journal stop events whose trade no longer exists."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Commit the cleanup. Without this flag the transaction is rolled back.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = asyncio.run(run_cleanup(dry_run=not args.execute))
    except Exception as exc:
        print(f"Orphan cleanup failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(asdict(report), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
