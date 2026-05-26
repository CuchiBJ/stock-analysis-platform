#!/usr/bin/env python3
"""
One-time (idempotent) backfill script: sets stocks.market_group for every stock
that has a non-NULL industry. Safe to re-run — same input always produces same output.

Usage:
    python scripts/populate_market_group.py

Expects DATABASE_URL env var (postgresql+asyncpg://...) or falls back to localhost default.
"""
import asyncio
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from app.services.market_group_mapping import map_industry_to_market_group

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/stock_analysis",
)


async def main() -> None:
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        result = await session.execute(
            text("SELECT symbol, industry, sector FROM stocks WHERE industry IS NOT NULL")
        )
        rows = result.fetchall()

    total_scanned = len(rows)
    groups: dict[str, list[str]] = defaultdict(list)  # group → [symbol, ...]
    unmapped_industries: dict[str, int] = defaultdict(int)

    for row in rows:
        group = map_industry_to_market_group(row.industry, row.sector)
        if group:
            groups[group].append(row.symbol)
        else:
            unmapped_industries[row.industry] += 1

    total_mapped = sum(len(syms) for syms in groups.values())
    total_unmapped = total_scanned - total_mapped

    async with async_session() as session:
        async with session.begin():
            for group, symbols in groups.items():
                await session.execute(
                    text(
                        "UPDATE stocks SET market_group = :group "
                        "WHERE symbol = ANY(:syms)"
                    ),
                    {"group": group, "syms": symbols},
                )
            # Clear market_group for stocks whose industry no longer maps
            # (handles re-runs after mapping changes)
            all_mapped_symbols = [s for syms in groups.values() for s in syms]
            if all_mapped_symbols:
                await session.execute(
                    text(
                        "UPDATE stocks SET market_group = NULL "
                        "WHERE industry IS NOT NULL "
                        "AND symbol != ALL(:syms)"
                    ),
                    {"syms": all_mapped_symbols},
                )

    print(f"\n=== populate_market_group summary ===")
    print(f"Total scanned:  {total_scanned}")
    print(f"Total mapped:   {total_mapped}")
    print(f"Total unmapped: {total_unmapped}")

    if unmapped_industries:
        print(f"\nUnmapped industries ({len(unmapped_industries)} distinct):")
        for industry, count in sorted(unmapped_industries.items(), key=lambda x: -x[1]):
            print(f"  {count:4d}  {industry}")

    print("\nGroups populated:")
    for group, symbols in sorted(groups.items(), key=lambda x: -len(x[1])):
        print(f"  {len(symbols):4d}  {group}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
