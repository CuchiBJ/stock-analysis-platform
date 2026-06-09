#!/usr/bin/env python
"""Backfill system snapshots for journal_trades created before
add-journal-system-snapshots shipped (or imported from CSV).

The MarketContextEngine and LeaderHealthCalculator are market-wide and use the
*latest* StockMetrics — they can't be reconstructed for arbitrary historical
dates. For historical trades we therefore only populate:
  - group_strength_at_entry (uses today's group performance, applied to the
    symbol's market_group — useful proxy when the symbol's classification
    didn't change)
  - system_score_at_entry (uses StockMetrics row at or before entry_date —
    accurate IF the metrics for that date are preserved)

regime_at_entry and leader_health_at_entry are left null for historical rows.
For live trades created from this point on, take_entry_snapshot at POST time
captures all 4 fields properly.

Usage:
    python scripts/backfill_journal_snapshots.py [--dry-run]

Exit code: 0 on success, 1 on uncaught exception.
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select, or_

from app.core.deps import AsyncSessionLocal
from app.models.stock import JournalTrade
from app.services.journal_snapshot_service import (
    _snapshot_group_strength,
    _snapshot_system_score,
)


async def main(dry_run: bool) -> int:
    updated = 0
    missing_all = 0
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(JournalTrade).where(
                or_(
                    JournalTrade.regime_at_entry.is_(None),
                    JournalTrade.system_score_at_entry.is_(None),
                    JournalTrade.group_strength_at_entry.is_(None),
                    JournalTrade.leader_health_at_entry.is_(None),
                )
            )
        )
        rows = list(result.scalars())
        print(f"Candidates: {len(rows)} trades with at least one null snapshot field")

        for trade in rows:
            gs = await _snapshot_group_strength(db, trade.symbol)
            ss = await _snapshot_system_score(db, trade.symbol, trade.entry_date, None)

            populated = []
            if gs is not None and trade.group_strength_at_entry is None:
                trade.group_strength_at_entry = gs
                populated.append(f"group={gs}")
            if ss is not None and trade.system_score_at_entry is None:
                trade.system_score_at_entry = ss
                populated.append(f"score={ss:.2f}")

            if populated:
                updated += 1
                print(f"  [{trade.symbol}] {trade.entry_date.isoformat()} → {', '.join(populated)}")
            else:
                missing_all += 1
                print(f"  [{trade.symbol}] {trade.entry_date.isoformat()} → MISSING (no metrics)")

        if dry_run:
            print(f"\nDry-run: rolling back. Would have updated {updated} trades, {missing_all} missing.")
            await db.rollback()
        else:
            await db.commit()
            print(f"\nUpdated {updated} trades · {missing_all} missing all snapshots")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Compute but do not commit")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(dry_run=args.dry_run)))
