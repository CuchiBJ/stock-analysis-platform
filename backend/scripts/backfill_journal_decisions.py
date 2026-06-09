#!/usr/bin/env python
"""Backfill parent_trade_id on historical journal_trades so every position
episode is one decision.

Grouping uses overlapping holding periods (see app.services.journal_decisions):
all legs of a symbol held at the same time — including same-day fills at
different prices and their partial sells — collapse into one decision.
Re-entering the symbol after fully liquidating starts a new decision. This is
the same rule the importer applies on ingest, so a re-run is idempotent.

Usage:
    python scripts/backfill_journal_decisions.py [--dry-run]

Exit code: 0 on success.
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select

from app.core.deps import AsyncSessionLocal
from app.models.stock import JournalTrade
from app.services.journal_decisions import assign_decision_links


async def main(dry_run: bool) -> int:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(JournalTrade))).scalars().all()
        rows_updated = assign_decision_links(rows)

        # Report the multi-leg decisions we formed for at-a-glance verification.
        decisions: dict[int, list[JournalTrade]] = {}
        for t in rows:
            decisions.setdefault(t.parent_trade_id or t.id, []).append(t)
        groups_updated = 0
        for rep_id, legs in sorted(decisions.items()):
            if len(legs) <= 1:
                continue
            groups_updated += 1
            child_ids = sorted(t.id for t in legs if t.id != rep_id)
            symbol = legs[0].symbol
            print(f"  [{symbol}] {len(legs)} legs → rep={rep_id} children={child_ids}")

        if dry_run:
            print(f"\nDry-run: rolling back. Would update {groups_updated} multi-leg decisions · {rows_updated} rows.")
            await db.rollback()
        else:
            await db.commit()
            print(f"\nUpdated {groups_updated} multi-leg decisions · {rows_updated} rows.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Compute but do not commit")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(dry_run=args.dry_run)))
